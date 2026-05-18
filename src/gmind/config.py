from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib


DEFAULT_CONFIG_PATH = Path("gmind.toml")


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
class AppConfig:
    database: DatabaseConfig
    models: ModelConfig


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
"""


def init_config(path: Path = DEFAULT_CONFIG_PATH, overwrite: bool = False) -> Path:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Config already exists: {path}")

    path.write_text(DEFAULT_CONFIG_TEMPLATE, encoding="utf-8")
    return path


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    file_data = _read_config_file(path)

    database_data = file_data.get("database", {})
    model_data = file_data.get("models", {})

    database_url = os.getenv("GMIND_DATABASE_URL") or database_data.get("url")
    if not database_url:
        raise ValueError("Missing database.url or GMIND_DATABASE_URL")

    embedding_dim = os.getenv("GMIND_EMBEDDING_DIM") or model_data.get("embedding_dim")
    if embedding_dim is None:
        raise ValueError("Missing models.embedding_dim or GMIND_EMBEDDING_DIM")

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
    )


def _read_config_file(path: Path) -> dict:
    if not path.exists():
        return {}

    with path.open("rb") as config_file:
        return tomllib.load(config_file)
