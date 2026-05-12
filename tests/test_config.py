from gmind.config import load_config


def test_load_config_reads_legacy_llm_keys(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '\n'.join(
            [
                'database_url = "postgresql://example"',
                'node_name = "home"',
                'embedding_api_key = "embedding-key"',
                'embedding_model = "BAAI/bge-m3"',
                'embedding_base_url = "https://api.siliconflow.cn/v1"',
                'llm_api_key = "llm-key"',
                'llm_base_url = "https://api.example.com/v1"',
                'llm_model = "example-model"',
            ]
        )
        + '\n',
        encoding="utf-8",
    )

    cfg = load_config(config_path)

    assert cfg.llm == {
        "provider": "openai",
        "openai": {
            "api_key": "llm-key",
            "model": "example-model",
            "base_url": "https://api.example.com/v1",
        },
    }


def test_load_config_prefers_structured_llm_section(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '\n'.join(
            [
                'database_url = "postgresql://example"',
                'node_name = "home"',
                'llm_api_key = "legacy-key"',
                'llm_base_url = "https://legacy.example.com/v1"',
                'llm_model = "legacy-model"',
                '',
                '[llm]',
                'provider = "ollama"',
                '',
                '[llm.ollama]',
                'model = "qwen2.5:7b"',
                'base_url = "http://localhost:11434"',
            ]
        )
        + '\n',
        encoding="utf-8",
    )

    cfg = load_config(config_path)

    assert cfg.llm == {
        "provider": "ollama",
        "ollama": {
            "model": "qwen2.5:7b",
            "base_url": "http://localhost:11434",
        },
    }
