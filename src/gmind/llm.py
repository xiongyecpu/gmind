"""Generic LLM client wrapper."""

from __future__ import annotations

from openai import OpenAI

from gmind.config import Config


def get_client(cfg: Config) -> OpenAI:
    return OpenAI(
        api_key=cfg.llm_api_key,
        base_url=cfg.llm_base_url,
    )


def chat(
    prompt: str,
    cfg: Config,
    *,
    system: str = "You are a helpful assistant.",
    temperature: float = 0.3,
) -> str:
    client = get_client(cfg)
    resp = client.chat.completions.create(
        model=cfg.llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""
