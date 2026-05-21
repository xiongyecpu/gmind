from unittest.mock import patch

from gmind.config import ModelConfig
from gmind.providers import (
    FakeEmbeddingProvider,
    FakeLLMProvider,
    SiliconFlowEmbeddingProvider,
    SiliconFlowLLMProvider,
    _api_key,
    _read_keychain,
    build_embedding_provider,
    build_llm_provider,
    _normalize_extraction,
    _normalize_solo_decision,
    _normalize_title,
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


def test_fake_llm_suggests_title_from_text_preview() -> None:
    provider = FakeLLMProvider()

    title = provider.suggest_source_title(
        source_path=None,
        text_preview="# 项目 A 合同\n\n项目 A 已签署合同。",
    )

    assert title == "项目 A 合同"


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


def test_normalize_solo_decision_clamps_confidence() -> None:
    normalized = _normalize_solo_decision(
        {
            "should_ingest": True,
            "reason": "包含项目事实。",
            "confidence": 1.4,
        }
    )

    assert normalized["should_ingest"] is True
    assert normalized["reason"] == "包含项目事实。"
    assert normalized["confidence"] == 1.0


def test_normalize_title_strips_quotes_and_collapses_spaces() -> None:
    assert _normalize_title('  "项目   A   合同"  ') == "项目 A 合同"


def test_api_key_prefers_env_variable(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "env-key")
    assert _api_key("TEST_API_KEY") == "env-key"


def test_api_key_raises_when_missing() -> None:
    import sys

    with patch.object(sys, "platform", "linux"):
        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "gmind.providers._read_keychain", return_value=None
            ) as mock_keychain:
                try:
                    _api_key("MISSING_KEY")
                except ValueError as e:
                    assert "MISSING_KEY" in str(e)
                mock_keychain.assert_not_called()


def test_api_key_falls_back_to_keychain_on_macos(monkeypatch) -> None:
    import sys

    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    with patch.object(sys, "platform", "darwin"):
        with patch(
            "gmind.providers._read_keychain", return_value="keychain-key"
        ) as mock_keychain:
            key = _api_key("SILICONFLOW_API_KEY")
            assert key == "keychain-key"
            mock_keychain.assert_called_once_with(
                service="gmind", account="SILICONFLOW_API_KEY"
            )


def test_read_keychain_returns_none_on_failure() -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert _read_keychain("gmind", "TEST_KEY") is None
