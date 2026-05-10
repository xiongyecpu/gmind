"""Configuration management for gmind."""

from __future__ import annotations

import os
import stat
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".gmind" / "config.toml"


@dataclass
class Config:
    database_url: str
    node_name: str = "default"
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"
    embedding_base_url: str = "https://api.siliconflow.cn/v1"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.siliconflow.cn/v1"
    llm_model: str = "deepseek-ai/DeepSeek-V3"


def load_config(path: Path | None = None) -> Config:
    cfg_path = path or DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {cfg_path}\nRun `gmind init` to create one."
        )
    with cfg_path.open("rb") as f:
        data = tomllib.load(f)
    return Config(
        database_url=data["database_url"],
        node_name=data.get("node_name", "default"),
        embedding_api_key=data.get("embedding_api_key", ""),
        embedding_model=data.get("embedding_model", "BAAI/bge-m3"),
        embedding_base_url=data.get(
            "embedding_base_url", "https://api.siliconflow.cn/v1"
        ),
        llm_api_key=data.get("llm_api_key", ""),
        llm_base_url=data.get("llm_base_url", "https://api.siliconflow.cn/v1"),
        llm_model=data.get("llm_model", "deepseek-ai/DeepSeek-V3"),
    )


def save_config(cfg: Config, path: Path | None = None) -> None:
    cfg_path = path or DEFAULT_CONFIG_PATH
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f'database_url = "{cfg.database_url}"',
        f'node_name = "{cfg.node_name}"',
        f'embedding_api_key = "{cfg.embedding_api_key}"',
        f'embedding_model = "{cfg.embedding_model}"',
        f'embedding_base_url = "{cfg.embedding_base_url}"',
        f'llm_api_key = "{cfg.llm_api_key}"',
        f'llm_base_url = "{cfg.llm_base_url}"',
        f'llm_model = "{cfg.llm_model}"',
    ]
    cfg_path.write_text("\n".join(lines) + "\n")
    os.chmod(cfg_path, stat.S_IRUSR | stat.S_IWUSR)
