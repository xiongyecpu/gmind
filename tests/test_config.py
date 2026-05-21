from pathlib import Path

import pytest

from gmind.config import init_config, load_config, resolve_config_path


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
    assert config.solo.enabled is False
    assert config.solo.level == 1


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
    monkeypatch.setenv("GMIND_SOLO_ENABLED", "true")
    monkeypatch.setenv("GMIND_SOLO_LEVEL", "2")

    config = load_config(config_path)

    assert config.models.llm_model == "test-llm"
    assert config.models.llm_base_url == "https://example.test/v1"
    assert config.models.embedding_dim == 42
    assert config.solo.enabled is True
    assert config.solo.level == 2


def test_default_config_resolves_from_parent_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "gmind.toml"
    child_dir = tmp_path / "nested" / "child"
    child_dir.mkdir(parents=True)
    init_config(config_path)
    monkeypatch.chdir(child_dir)

    config = load_config()

    assert config.database.url == "postgresql://localhost:5432/gmind"
    assert resolve_config_path() == config_path


def test_gmind_config_env_overrides_default_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "custom.toml"
    init_config(config_path)
    monkeypatch.setenv("GMIND_CONFIG", str(config_path))

    config = load_config()

    assert config.database.url == "postgresql://localhost:5432/gmind"
    assert resolve_config_path() == config_path
