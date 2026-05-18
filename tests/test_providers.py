from gmind.config import ModelConfig
from gmind.providers import (
    FakeEmbeddingProvider,
    FakeLLMProvider,
    SiliconFlowEmbeddingProvider,
    SiliconFlowLLMProvider,
    build_embedding_provider,
    build_llm_provider,
    _normalize_extraction,
)


def test_fake_embedding_provider_returns_configured_dimensions() -> None:
    provider = FakeEmbeddingProvider(dimensions=4)

    embeddings = provider.embed_texts(["hello"])

    assert len(embeddings) == 1
    assert len(embeddings[0]) == 4


def test_build_fake_providers() -> None:
    config = ModelConfig(
        llm_provider="fake",
        llm_model="fake-llm",
        llm_base_url=None,
        llm_api_key_env="FAKE_API_KEY",
        embedding_provider="fake",
        embedding_model="fake-embedding",
        embedding_dim=4,
        embedding_base_url=None,
        embedding_api_key_env="FAKE_API_KEY",
    )

    assert isinstance(build_embedding_provider(config), FakeEmbeddingProvider)
    assert isinstance(build_llm_provider(config), FakeLLMProvider)


def test_build_siliconflow_providers(monkeypatch) -> None:
    monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
    config = ModelConfig(
        llm_provider="siliconflow",
        llm_model="Qwen/Qwen3.6-35B-A3B",
        llm_base_url="https://api.siliconflow.cn/v1",
        llm_api_key_env="SILICONFLOW_API_KEY",
        embedding_provider="siliconflow",
        embedding_model="Qwen/Qwen3-Embedding-4B",
        embedding_dim=1536,
        embedding_base_url="https://api.siliconflow.cn/v1",
        embedding_api_key_env="SILICONFLOW_API_KEY",
    )

    assert isinstance(build_embedding_provider(config), SiliconFlowEmbeddingProvider)
    assert isinstance(build_llm_provider(config), SiliconFlowLLMProvider)


def test_normalize_extraction_fills_optional_fields() -> None:
    normalized = _normalize_extraction(
        {
            "entities": [{"name": "项目 A", "entity_type": "project"}],
            "claims": [{"text": "项目 A 签署合同。"}],
            "events": [{"title": "项目 A 签署合同"}],
            "tasks": [{"title": "确认项目 A 是否验收"}],
        }
    )

    assert normalized["entities"][0]["canonical_name"] == "项目 A"
    assert normalized["claims"][0]["claim_type"] == "fact"
    assert normalized["events"][0]["event_type"] == "other"
    assert normalized["tasks"][0]["task_type"] == "research_question"


def test_normalize_extraction_coerces_priority_and_names() -> None:
    normalized = _normalize_extraction(
        {
            "entities": [{"name": "项目B", "entity_type": "PROJECT"}],
            "claims": [{"text": "项目B 收到首付款", "claim_type": "status", "about_entities": ["项目B"]}],
            "events": [],
            "tasks": [{"title": "确认验收", "priority": "high", "related_entities": ["项目B"]}],
        }
    )

    assert normalized["entities"][0]["name"] == "项目 B"
    assert normalized["entities"][0]["entity_type"] == "project"
    assert normalized["claims"][0]["claim_type"] == "fact"
    assert normalized["claims"][0]["about_entities"] == ["项目 B"]
    assert normalized["tasks"][0]["priority"] == 80
