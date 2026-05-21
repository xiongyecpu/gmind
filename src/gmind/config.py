from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib


DEFAULT_CONFIG_PATH = Path("gmind.toml")
USER_CONFIG_PATH = Path.home() / ".gmind" / "gmind.toml"


@dataclass(frozen=True)
class DatabaseConfig:
    url: str


@dataclass(frozen=True)
class ModelConfig:
    llm_provider: str
    llm_model: str
    llm_base_url: str | None
    llm_api_key_env: str
    embedding_provider: str
    embedding_model: str
    embedding_dim: int
    embedding_base_url: str | None
    embedding_api_key_env: str


@dataclass(frozen=True)
class SoloConfig:
    enabled: bool
    level: int


@dataclass(frozen=True)
class AppConfig:
    database: DatabaseConfig
    models: ModelConfig
    solo: SoloConfig


DEFAULT_CONFIG_TEMPLATE = """# gmind configuration

[database]
url = "postgresql://localhost:5432/gmind"

[models]
llm_provider = "siliconflow"
# Default extraction model. If JSON output is unstable, try:
# deepseek-ai/DeepSeek-V4-Flash
llm_model = "Qwen/Qwen3.6-35B-A3B"
llm_base_url = "https://api.siliconflow.cn/v1"
llm_api_key_env = "SILICONFLOW_API_KEY"
embedding_provider = "siliconflow"
embedding_model = "Qwen/Qwen3-Embedding-4B"
embedding_dim = 1536
embedding_base_url = "https://api.siliconflow.cn/v1"
embedding_api_key_env = "SILICONFLOW_API_KEY"

[solo]
enabled = false
level = 1
"""


def init_config(path: Path = DEFAULT_CONFIG_PATH, overwrite: bool = False) -> Path:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Config already exists: {path}")

    path.write_text(DEFAULT_CONFIG_TEMPLATE, encoding="utf-8")
    return path


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    file_data = _read_config_file(resolve_config_path(path))

    database_data = file_data.get("database", {})
    model_data = file_data.get("models", {})
    solo_data = file_data.get("solo", {})

    database_url = os.getenv("GMIND_DATABASE_URL") or database_data.get("url")
    if not database_url:
        raise ValueError("Missing database.url or GMIND_DATABASE_URL")

    embedding_dim = os.getenv("GMIND_EMBEDDING_DIM") or model_data.get("embedding_dim")
    if embedding_dim is None:
        raise ValueError("Missing models.embedding_dim or GMIND_EMBEDDING_DIM")

    solo_level = os.getenv("GMIND_SOLO_LEVEL") or solo_data.get("level", 1)

    return AppConfig(
        database=DatabaseConfig(url=database_url),
        models=ModelConfig(
            llm_provider=os.getenv("GMIND_LLM_PROVIDER")
            or model_data.get("llm_provider", "siliconflow"),
            llm_model=os.getenv("GMIND_LLM_MODEL")
            or model_data.get("llm_model", "Qwen/Qwen3.6-35B-A3B"),
            llm_base_url=os.getenv("GMIND_LLM_BASE_URL")
            or model_data.get("llm_base_url"),
            llm_api_key_env=os.getenv("GMIND_LLM_API_KEY_ENV")
            or model_data.get("llm_api_key_env", "SILICONFLOW_API_KEY"),
            embedding_provider=os.getenv("GMIND_EMBEDDING_PROVIDER")
            or model_data.get("embedding_provider", "siliconflow"),
            embedding_model=os.getenv("GMIND_EMBEDDING_MODEL")
            or model_data.get("embedding_model", "Qwen/Qwen3-Embedding-4B"),
            embedding_dim=int(embedding_dim),
            embedding_base_url=os.getenv("GMIND_EMBEDDING_BASE_URL")
            or model_data.get("embedding_base_url"),
            embedding_api_key_env=os.getenv("GMIND_EMBEDDING_API_KEY_ENV")
            or model_data.get("embedding_api_key_env", "SILICONFLOW_API_KEY"),
        ),
        solo=SoloConfig(
            enabled=_bool_from_env(
                os.getenv("GMIND_SOLO_ENABLED"),
                default=bool(solo_data.get("enabled", False)),
            ),
            level=int(solo_level),
        ),
    )


def _read_config_file(path: Path) -> dict:
    if not path.exists():
        return {}

    with path.open("rb") as config_file:
        return tomllib.load(config_file)


def resolve_config_path(path: Path = DEFAULT_CONFIG_PATH) -> Path:
    env_path = os.getenv("GMIND_CONFIG")
    if env_path:
        return Path(env_path).expanduser()

    expanded = path.expanduser()
    if expanded != DEFAULT_CONFIG_PATH:
        return expanded
    if expanded.exists():
        return expanded

    for parent in [Path.cwd(), *Path.cwd().parents]:
        candidate = parent / DEFAULT_CONFIG_PATH
        if candidate.exists():
            return candidate

    return USER_CONFIG_PATH


def _bool_from_env(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")
