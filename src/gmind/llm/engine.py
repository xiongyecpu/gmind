"""LLM provider abstraction and engine."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from gmind.llm.cache import LLMCache


class LLMProvider(Protocol):
    """Protocol for LLM providers."""

    def chat(self, messages: list[dict], temperature: float = 0.7, timeout: float = 120.0) -> str:
        """Send a chat completion request and return the response text."""
        ...

    def is_available(self) -> bool:
        """Check if the provider is reachable."""
        ...


@dataclass
class OllamaProvider:
    """Local Ollama provider."""

    model: str = "qwen2.5:7b"
    base_url: str = "http://localhost:11434"

    def chat(self, messages: list[dict], temperature: float = 0.7, timeout: float = 120.0) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False


@dataclass
class OpenAIProvider:
    """OpenAI-compatible provider (OpenAI, SiliconFlow, DeepSeek, etc.)."""

    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"

    def chat(self, messages: list[dict], temperature: float = 0.7, timeout: float = 120.0) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False


@dataclass
class LLMEngine:
    """Unified LLM engine with caching and metrics."""

    provider: LLMProvider
    cache: LLMCache = field(default_factory=LLMCache)
    default_temperature: float = 0.3

    def chat(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
        use_cache: bool = True,
        timeout: float = 120.0,
    ) -> str:
        """Chat with optional caching."""
        temp = temperature if temperature is not None else self.default_temperature

        if use_cache:
            cache_key = self._hash_request(messages, temp)
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        result = self.provider.chat(messages, temperature=temp, timeout=timeout)

        if use_cache:
            self.cache.set(cache_key, result)

        return result

    def ask(self, prompt: str, *, temperature: float | None = None, use_cache: bool = True) -> str:
        """Simple single-turn ask."""
        return self.chat(
            [{"role": "user", "content": prompt}],
            temperature=temperature,
            use_cache=use_cache,
        )

    def is_available(self) -> bool:
        return self.provider.is_available()

    @staticmethod
    def _hash_request(messages: list[dict], temperature: float) -> str:
        payload = json.dumps({"messages": messages, "temperature": temperature}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


def load_llm_engine(config_data: dict) -> LLMEngine | None:
    """Build an LLMEngine from config dict (the [llm] section)."""
    provider_name = config_data.get("provider", "ollama")

    if provider_name == "ollama":
        ollama_cfg = config_data.get("ollama", {})
        provider = OllamaProvider(
            model=ollama_cfg.get("model", "qwen2.5:7b"),
            base_url=ollama_cfg.get("base_url", "http://localhost:11434"),
        )
    elif provider_name in ("openai", "siliconflow"):
        api_cfg = config_data.get(provider_name, config_data.get("openai", {}))
        provider = OpenAIProvider(
            api_key=api_cfg.get("api_key", ""),
            model=api_cfg.get("model", "gpt-4o-mini"),
            base_url=api_cfg.get("base_url", "https://api.openai.com/v1"),
        )
    else:
        return None

    return LLMEngine(provider=provider)
