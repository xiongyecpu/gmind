from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import json
import os
import subprocess
import sys
from typing import Any

from gmind.config import ModelConfig


EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "entity_type": {"type": "string"},
                    "canonical_name": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                },
                "required": [
                    "name",
                    "entity_type",
                    "canonical_name",
                    "aliases",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "claim_type": {
                        "type": "string",
                        "enum": ["fact", "opinion", "hypothesis", "conclusion", "summary"],
                    },
                    "confidence": {"type": "number"},
                    "about_entities": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "claim_type", "confidence", "about_entities"],
                "additionalProperties": False,
            },
        },
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "enum": [
                            "contract_signed",
                            "payment_received",
                            "payment_sent",
                            "meeting_held",
                            "requirement_changed",
                            "project_started",
                            "project_paused",
                            "project_accepted",
                            "invoice_issued",
                            "approval_passed",
                            "other",
                        ],
                    },
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "occurred_at": {"type": "string"},
                    "occurred_at_precision": {"type": "string"},
                    "related_entities": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                },
                "required": [
                    "event_type",
                    "title",
                    "description",
                    "occurred_at",
                    "occurred_at_precision",
                    "related_entities",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_type": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "integer"},
                    "related_entities": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "task_type",
                    "title",
                    "description",
                    "priority",
                    "related_entities",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["entities", "claims", "events", "tasks"],
    "additionalProperties": False,
}


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class LLMProvider(ABC):
    @abstractmethod
    def extract_chunk(self, chunk_text: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def answer_question(self, question: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def judge_source_for_ingest(
        self,
        *,
        title: str,
        source_path: str,
        text_preview: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def suggest_source_title(
        self,
        *,
        source_path: str | None,
        text_preview: str,
    ) -> str:
        raise NotImplementedError


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_fake_embedding(text, self.dimensions) for text in texts]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        model: str,
        dimensions: int,
        *,
        base_url: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        from openai import OpenAI

        self.client = OpenAI(
            api_key=_api_key(api_key_env),
            base_url=base_url,
            timeout=60,
        )
        self.model = model
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(
            input=texts,
            model=self.model,
            dimensions=self.dimensions,
        )
        return [item.embedding for item in response.data]


class FakeLLMProvider(LLMProvider):
    def extract_chunk(self, chunk_text: str) -> dict[str, Any]:
        return {"entities": [], "claims": [], "events": [], "tasks": []}

    def answer_question(self, question: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        if not evidence:
            return {"answer": "还没有找到相关资料。", "followups": []}
        first = evidence[0]["text"]
        return {
            "answer": f"基于已有资料：{first}",
            "followups": [],
        }

    def judge_source_for_ingest(
        self,
        *,
        title: str,
        source_path: str,
        text_preview: str,
    ) -> dict[str, Any]:
        if "skip" in title.lower() or "跳过" in text_preview:
            return {
                "should_ingest": False,
                "reason": "Fake provider judged this file should be skipped.",
                "confidence": 0.8,
            }
        return {
            "should_ingest": True,
            "reason": "Fake provider judged this file has useful knowledge.",
            "confidence": 0.8,
        }

    def suggest_source_title(
        self,
        *,
        source_path: str | None,
        text_preview: str,
    ) -> str:
        first_line = next(
            (line.strip("# \t") for line in text_preview.splitlines() if line.strip()),
            "",
        )
        return _normalize_title(first_line or "Untitled")


class OpenAILLMProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        *,
        base_url: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        from openai import OpenAI

        self.client = OpenAI(
            api_key=_api_key(api_key_env),
            base_url=base_url,
            timeout=60,
        )
        self.model = model

    def extract_chunk(self, chunk_text: str) -> dict[str, Any]:
        if _use_json_object_mode(self.model):
            return self._extract_chunk_json_object(chunk_text)

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _extraction_system_prompt()},
                {"role": "user", "content": chunk_text},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "gmind_chunk_extraction",
                    "schema": EXTRACTION_SCHEMA,
                    "strict": True,
                },
            },
        )
        content = completion.choices[0].message.content
        if content is None:
            raise ValueError("LLM returned empty extraction content")
        return _normalize_extraction(json.loads(content))

    def _extract_chunk_json_object(self, chunk_text: str) -> dict[str, Any]:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _extraction_system_prompt()},
                {
                    "role": "user",
                    "content": (
                        "Extract knowledge from this chunk. Return JSON with exactly "
                        "these top-level keys: entities, claims, events, tasks.\n\n"
                        "Entity fields: name, entity_type, canonical_name, aliases, confidence.\n"
                        "Claim fields: text, claim_type, confidence, about_entities.\n"
                        "Event fields: event_type, title, description, occurred_at, "
                        "occurred_at_precision, related_entities, confidence.\n"
                        "Task fields: task_type, title, description, priority, related_entities.\n\n"
                        f"Chunk:\n{chunk_text}"
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        if content is None:
            raise ValueError("LLM returned empty extraction content")
        return _normalize_extraction(json.loads(content))

    def answer_question(self, question: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        evidence_text = "\n\n".join(
            (
                f"[{index + 1}] source_id={item.get('source_id')} "
                f"chunk_id={item.get('chunk_id')} title={item.get('title')}\n"
                f"{item.get('text')}"
            )
            for index, item in enumerate(evidence)
        )
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You answer questions for gmind using only the provided evidence. "
                        "Do not invent facts. If the evidence is insufficient, say what is missing. "
                        "Return JSON with keys: answer, followups. followups is an array of short strings."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question:\n{question}\n\n"
                        f"Evidence:\n{evidence_text}\n\n"
                        "Return only JSON."
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        if content is None:
            raise ValueError("LLM returned empty answer content")
        return _normalize_answer(json.loads(content))

    def judge_source_for_ingest(
        self,
        *,
        title: str,
        source_path: str,
        text_preview: str,
    ) -> dict[str, Any]:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你负责判断一个文件是否应当加入 gmind（个人 AI 知识库）。"
                        "应当入库的文件包含持久、可复用的知识：项目事实、会议纪要、"
                        "调研资料、决策记录、需求文档、计划方案、总结归纳或领域素材。"
                        "应当跳过的文件包括：空文件、模板/样板文本、依赖文档、凭据/密钥、"
                        "日志、临时便签，或未来几乎不会被检索的内容。"
                        "返回 JSON，包含以下键：should_ingest（布尔值，是否入库）、"
                        "reason（简短中文理由）、confidence（0 到 1 之间的置信度）。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"标题：{title}\n"
                        f"路径：{source_path}\n\n"
                        f"文件预览：\n{text_preview}\n\n"
                        "只返回 JSON。"
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        if content is None:
            raise ValueError("LLM returned empty solo decision content")
        return _normalize_solo_decision(json.loads(content))

    def suggest_source_title(
        self,
        *,
        source_path: str | None,
        text_preview: str,
    ) -> str:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate concise titles for material added to gmind. "
                        "Return JSON with one key: title. The title should be short, "
                        "specific, human-readable, and no more than 24 Chinese "
                        "characters or 8 English words. Do not include quotes."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Path: {source_path or '-'}\n\n"
                        f"File/text preview:\n{text_preview}\n\n"
                        "Return only JSON."
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        if content is None:
            raise ValueError("LLM returned empty title content")
        return _normalize_title(json.loads(content).get("title", ""))


class SiliconFlowEmbeddingProvider(OpenAIEmbeddingProvider):
    pass


class SiliconFlowLLMProvider(OpenAILLMProvider):
    pass


def build_embedding_provider(config: ModelConfig) -> EmbeddingProvider:
    if config.embedding_provider == "fake":
        return FakeEmbeddingProvider(config.embedding_dim)
    if config.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(
            model=config.embedding_model,
            dimensions=config.embedding_dim,
            base_url=config.embedding_base_url,
            api_key_env=config.embedding_api_key_env,
        )
    if config.embedding_provider == "siliconflow":
        return SiliconFlowEmbeddingProvider(
            model=config.embedding_model,
            dimensions=config.embedding_dim,
            base_url=config.embedding_base_url or "https://api.siliconflow.cn/v1",
            api_key_env=config.embedding_api_key_env,
        )
    raise ValueError(f"Unsupported embedding provider: {config.embedding_provider}")


def build_llm_provider(config: ModelConfig) -> LLMProvider:
    if config.llm_provider == "fake":
        return FakeLLMProvider()
    if config.llm_provider == "openai":
        return OpenAILLMProvider(
            model=config.llm_model,
            base_url=config.llm_base_url,
            api_key_env=config.llm_api_key_env,
        )
    if config.llm_provider == "siliconflow":
        return SiliconFlowLLMProvider(
            model=config.llm_model,
            base_url=config.llm_base_url or "https://api.siliconflow.cn/v1",
            api_key_env=config.llm_api_key_env,
        )
    raise ValueError(f"Unsupported LLM provider: {config.llm_provider}")


def _api_key(env_name: str) -> str:
    api_key = os.getenv(env_name)
    if api_key:
        return api_key
    if sys.platform == "darwin":
        keychain_key = _read_keychain(service="gmind", account=env_name)
        if keychain_key:
            return keychain_key
    raise ValueError(f"Missing API key environment variable: {env_name}")


def _read_keychain(service: str, account: str) -> str | None:
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                service,
                "-a",
                account,
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _extraction_system_prompt() -> str:
    return (
        "You extract structured knowledge for gmind. "
        "Return only JSON. Extract entities, claims, real-world events, and useful tasks. "
        "Do not invent facts not supported by the chunk. "
        "Use precise event_type values when possible, for example "
        "contract_signed for 签署合同, payment_received for 收到付款, "
        "and requirement_changed for 需求变更. "
        "Every entity mentioned by a claim or event must be included in entities. "
        "Every explicit factual sentence should produce a fact claim, even when it also "
        "produces an event. For every event you output, also output one corresponding "
        "fact claim in claims."
    )


def _use_json_object_mode(model: str) -> bool:
    return "Qwen3.6" in model


def _normalize_extraction(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "entities": [
            {
                "name": _normalize_name(entity.get("name", "")),
                "entity_type": _normalize_entity_type(entity.get("entity_type")),
                "canonical_name": _normalize_name(
                    entity.get("canonical_name") or entity.get("name", "")
                ),
                "aliases": entity.get("aliases", []),
                "confidence": entity.get("confidence", 0.5),
            }
            for entity in data.get("entities", [])
            if entity.get("name")
        ],
        "claims": [
            {
                "text": claim.get("text", "").strip(),
                "claim_type": _normalize_claim_type(claim.get("claim_type")),
                "confidence": claim.get("confidence", 0.5),
                "about_entities": [
                    _normalize_name(entity_name)
                    for entity_name in claim.get("about_entities", [])
                ],
            }
            for claim in data.get("claims", [])
            if claim.get("text")
        ],
        "events": [
            {
                "event_type": event.get("event_type", "other"),
                "title": event.get("title", "").strip(),
                "description": event.get("description", "").strip(),
                "occurred_at": event.get("occurred_at", ""),
                "occurred_at_precision": event.get("occurred_at_precision", "unknown"),
                "related_entities": [
                    _normalize_name(entity_name)
                    for entity_name in event.get("related_entities", [])
                ],
                "confidence": event.get("confidence", 0.5),
            }
            for event in data.get("events", [])
            if event.get("title")
        ],
        "tasks": [
            {
                "task_type": task.get("task_type", "research_question"),
                "title": task.get("title", "").strip(),
                "description": task.get("description", "").strip(),
                "priority": _normalize_priority(task.get("priority", 0)),
                "related_entities": [
                    _normalize_name(entity_name)
                    for entity_name in task.get("related_entities", [])
                ],
            }
            for task in data.get("tasks", [])
            if task.get("title")
        ],
    }


def _normalize_answer(data: dict[str, Any]) -> dict[str, Any]:
    answer = str(data.get("answer", "")).strip()
    followups = data.get("followups", [])
    if not isinstance(followups, list):
        followups = []
    return {
        "answer": answer or "没有足够资料回答这个问题。",
        "followups": [str(item).strip() for item in followups if str(item).strip()],
    }


def _normalize_solo_decision(data: dict[str, Any]) -> dict[str, Any]:
    reason = str(data.get("reason", "")).strip()
    confidence = data.get("confidence", 0.5)
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.5
    return {
        "should_ingest": bool(data.get("should_ingest", False)),
        "reason": reason or "模型没有给出明确原因。",
        "confidence": max(0.0, min(1.0, confidence_value)),
    }


def _normalize_title(title: object) -> str:
    normalized = " ".join(str(title).strip().strip("\"'").split())
    return normalized[:80] or "untitled"


def _normalize_name(name: str) -> str:
    stripped = str(name).strip()
    stripped = stripped.replace("项目A", "项目 A")
    stripped = stripped.replace("项目B", "项目 B")
    return " ".join(stripped.split())


def _normalize_entity_type(entity_type: Any) -> str:
    value = str(entity_type or "unknown").strip().lower()
    if value == "project":
        return "project"
    if value in {"person", "role", "company", "contract", "document", "topic"}:
        return value
    return "unknown"


def _normalize_claim_type(claim_type: Any) -> str:
    value = str(claim_type or "fact").strip().lower()
    if value in {"fact", "opinion", "hypothesis", "conclusion", "summary"}:
        return value
    if value in {"status", "state"}:
        return "fact"
    return "fact"


def _normalize_priority(priority: Any) -> int:
    if isinstance(priority, int):
        return priority
    if isinstance(priority, float):
        return int(priority)

    value = str(priority).strip().lower()
    if value in {"high", "高", "urgent"}:
        return 80
    if value in {"medium", "中", "normal"}:
        return 50
    if value in {"low", "低"}:
        return 20
    try:
        return int(value)
    except ValueError:
        return 0


def _fake_embedding(text: str, dimensions: int) -> list[float]:
    if dimensions <= 0:
        raise ValueError("dimensions must be positive")

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    for index in range(dimensions):
        byte = digest[index % len(digest)]
        values.append((byte / 255.0) * 2.0 - 1.0)
    return values
