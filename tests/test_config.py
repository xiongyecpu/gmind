from pathlib import Path

import pytest

from gmind.config import init_config, load_config


def test_init_config_creates_model_config(tmp_path: Path) -> None:
    config_path = tmp_path / "gmind.toml"

    init_config(config_path)
    config = load_config(config_path)

    assert config.models.llm_provider == "siliconflow"
    assert config.models.llm_model == "Qwen/Qwen3.6-35B-A3B"
    assert config.models.llm_base_url == "https://api.siliconflow.cn/v1"
    assert config.models.llm_api_key_env == "SILICONFLOW_API_KEY"
    assert config.models.embedding_provider == "siliconflow"
    assert config.models.embedding_model == "Qwen/Qwen3-Embedding-4B"
    assert config.models.embedding_dim == 1536
    assert config.models.embedding_base_url == "https://api.siliconflow.cn/v1"
    assert config.models.embedding_api_key_env == "SILICONFLOW_API_KEY"


def test_init_config_refuses_to_overwrite(tmp_path: Path) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)

    with pytest.raises(FileExistsError):
        init_config(config_path)


def test_env_overrides_model_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    monkeypatch.setenv("GMIND_LLM_MODEL", "test-llm")
    monkeypatch.setenv("GMIND_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("GMIND_EMBEDDING_DIM", "42")

    config = load_config(config_path)

    assert config.models.llm_model == "test-llm"
    assert config.models.llm_base_url == "https://example.test/v1"
    assert config.models.embedding_dim == 42
