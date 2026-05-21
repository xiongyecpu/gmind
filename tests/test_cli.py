import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gmind.ask import AskResult, EvidenceChunk
from gmind.cli import main
from gmind.config import init_config
from gmind.db import DatabaseCheck, REQUIRED_TABLES, REQUIRED_VIEWS
from gmind.extract import ExtractResult
from gmind.knowledge import (
    ClaimDetail,
    ClaimSummary,
    EntityDetail,
    EntitySummary,
    EventSummary,
    LogSummary,
    RelationSummary,
    TaskDetail,
    TaskSummary,
)
from gmind.sources import SourceChunk, SourceDetail, SourceSummary


def test_help_shows_product_commands_not_database_views(capsys) -> None:
    try:
        main(["--help"])
    except SystemExit as exit:
        assert exit.code == 0

    captured = capsys.readouterr()
    assert "ask" in captured.out
    assert "add" in captured.out
    assert "status" in captured.out
    assert "debug" in captured.out
    assert "entities" not in captured.out
    assert "relations" not in captured.out


def test_add_text_runs_ingest_embed_and_extract(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    source_path = tmp_path / "source.txt"
    init_config(config_path)
    source_path.write_text("项目 A 在 2026-03-01 签署合同。", encoding="utf-8")

    with (
        patch("gmind.cli.ingest_text_source") as ingest_text_source,
        patch("gmind.cli.build_embedding_provider"),
        patch("gmind.cli.embed_source_chunks") as embed_source_chunks,
        patch("gmind.cli.build_llm_provider"),
        patch("gmind.cli.extract_llm_source") as extract_llm_source,
    ):
        ingest_text_source.return_value = SimpleNamespace(source_id=7, chunk_count=1)
        embed_source_chunks.return_value = SimpleNamespace(chunks_embedded=1)
        extract_llm_source.return_value = ExtractResult(
            source_id=7,
            entities_created=1,
            claims_created=1,
            events_created=1,
            relations_created=1,
        )
        exit_code = main(
            [
                "add",
                "text",
                "--title",
                "测试资料",
                "--file",
                str(source_path),
                "--config",
                str(config_path),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Added source 7" in captured.out
    assert "Embedded 1 chunks." in captured.out
    assert "Extracted 1 entities" in captured.out
    ingest_text_source.assert_called_once()
    assert ingest_text_source.call_args.kwargs["source_path"] == str(
        source_path.resolve()
    )
    embed_source_chunks.assert_called_once()
    extract_llm_source.assert_called_once()


def test_add_text_accepts_direct_text(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)

    with (
        patch("gmind.cli.ingest_text_source") as ingest_text_source,
        patch("gmind.cli.build_embedding_provider"),
        patch("gmind.cli.embed_source_chunks") as embed_source_chunks,
        patch("gmind.cli.build_llm_provider"),
        patch("gmind.cli.extract_llm_source") as extract_llm_source,
    ):
        ingest_text_source.return_value = SimpleNamespace(source_id=8, chunk_count=1)
        embed_source_chunks.return_value = SimpleNamespace(chunks_embedded=1)
        extract_llm_source.return_value = ExtractResult(
            source_id=8,
            entities_created=1,
            claims_created=1,
            events_created=0,
            relations_created=1,
        )
        exit_code = main(
            [
                "add",
                "text",
                "--title",
                "直接文本",
                "--text",
                "项目 B 收到首付款。",
                "--config",
                str(config_path),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Added source 8" in captured.out
    assert ingest_text_source.call_args.kwargs["text"] == "项目 B 收到首付款。"
    embed_source_chunks.assert_called_once()
    extract_llm_source.assert_called_once()


def test_add_text_file_uses_llm_title_when_title_is_omitted(
    tmp_path: Path, capsys
) -> None:
    config_path = tmp_path / "gmind.toml"
    source_path = tmp_path / "project-note.txt"
    init_config(config_path)
    source_path.write_text("项目 A 在 2026-03-01 签署合同。", encoding="utf-8")
    provider = SimpleNamespace(suggest_source_title=lambda **_: "项目 A 合同")

    with (
        patch("gmind.cli.ingest_text_source") as ingest_text_source,
        patch("gmind.cli.build_embedding_provider"),
        patch("gmind.cli.embed_source_chunks") as embed_source_chunks,
        patch("gmind.cli.build_llm_provider", return_value=provider),
        patch("gmind.cli.extract_llm_source") as extract_llm_source,
    ):
        ingest_text_source.return_value = SimpleNamespace(source_id=13, chunk_count=1)
        embed_source_chunks.return_value = SimpleNamespace(chunks_embedded=1)
        extract_llm_source.return_value = ExtractResult(
            source_id=13,
            entities_created=1,
            claims_created=1,
            events_created=1,
            relations_created=1,
        )
        exit_code = main(
            [
                "add",
                "text",
                "--file",
                str(source_path),
                "--config",
                str(config_path),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Added source 13" in captured.out
    assert ingest_text_source.call_args.kwargs["title"] == "项目 A 合同"


def test_add_text_direct_text_uses_llm_title_when_title_is_omitted(
    tmp_path: Path, capsys
) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    provider = SimpleNamespace(suggest_source_title=lambda **_: "项目 A 签约")

    with (
        patch("gmind.cli.ingest_text_source") as ingest_text_source,
        patch("gmind.cli.build_embedding_provider"),
        patch("gmind.cli.embed_source_chunks") as embed_source_chunks,
        patch("gmind.cli.build_llm_provider", return_value=provider),
        patch("gmind.cli.extract_llm_source") as extract_llm_source,
    ):
        ingest_text_source.return_value = SimpleNamespace(source_id=14, chunk_count=1)
        embed_source_chunks.return_value = SimpleNamespace(chunks_embedded=1)
        extract_llm_source.return_value = ExtractResult(
            source_id=14,
            entities_created=1,
            claims_created=1,
            events_created=1,
            relations_created=1,
        )
        exit_code = main(
            [
                "add",
                "text",
                "--text",
                "项目 A 已签署合同。",
                "--config",
                str(config_path),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Added source 14" in captured.out
    assert ingest_text_source.call_args.kwargs["title"] == "项目 A 签约"


def test_add_text_accepts_stdin(tmp_path: Path, monkeypatch, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    monkeypatch.setattr("sys.stdin", SimpleNamespace(read=lambda: "项目 C 签署合同。"))

    with (
        patch("gmind.cli.ingest_text_source") as ingest_text_source,
        patch("gmind.cli.build_embedding_provider"),
        patch("gmind.cli.embed_source_chunks") as embed_source_chunks,
        patch("gmind.cli.build_llm_provider"),
        patch("gmind.cli.extract_llm_source") as extract_llm_source,
    ):
        ingest_text_source.return_value = SimpleNamespace(source_id=9, chunk_count=1)
        embed_source_chunks.return_value = SimpleNamespace(chunks_embedded=1)
        extract_llm_source.return_value = ExtractResult(
            source_id=9,
            entities_created=1,
            claims_created=1,
            events_created=1,
            relations_created=1,
        )
        exit_code = main(
            [
                "add",
                "text",
                "--title",
                "stdin 文本",
                "--stdin",
                "--config",
                str(config_path),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Added source 9" in captured.out
    assert ingest_text_source.call_args.kwargs["text"] == "项目 C 签署合同。"
    embed_source_chunks.assert_called_once()
    extract_llm_source.assert_called_once()


def test_add_text_stdin_uses_llm_title_when_title_is_omitted(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    monkeypatch.setattr("sys.stdin", SimpleNamespace(read=lambda: "\n\n项目 C 签署合同。"))
    provider = SimpleNamespace(suggest_source_title=lambda **_: "项目 C 签约")

    with (
        patch("gmind.cli.ingest_text_source") as ingest_text_source,
        patch("gmind.cli.build_embedding_provider"),
        patch("gmind.cli.embed_source_chunks") as embed_source_chunks,
        patch("gmind.cli.build_llm_provider", return_value=provider),
        patch("gmind.cli.extract_llm_source") as extract_llm_source,
    ):
        ingest_text_source.return_value = SimpleNamespace(source_id=15, chunk_count=1)
        embed_source_chunks.return_value = SimpleNamespace(chunks_embedded=1)
        extract_llm_source.return_value = ExtractResult(
            source_id=15,
            entities_created=1,
            claims_created=1,
            events_created=1,
            relations_created=1,
        )
        exit_code = main(
            [
                "add",
                "text",
                "--stdin",
                "--config",
                str(config_path),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Added source 15" in captured.out
    assert ingest_text_source.call_args.kwargs["title"] == "项目 C 签约"


def test_add_text_can_print_json(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)

    with (
        patch("gmind.cli.ingest_text_source") as ingest_text_source,
        patch("gmind.cli.build_embedding_provider"),
        patch("gmind.cli.embed_source_chunks") as embed_source_chunks,
        patch("gmind.cli.build_llm_provider"),
        patch("gmind.cli.extract_llm_source") as extract_llm_source,
    ):
        ingest_text_source.return_value = SimpleNamespace(source_id=10, chunk_count=1)
        embed_source_chunks.return_value = SimpleNamespace(chunks_embedded=1)
        extract_llm_source.return_value = ExtractResult(
            source_id=10,
            entities_created=1,
            claims_created=2,
            events_created=0,
            relations_created=1,
        )
        exit_code = main(
            [
                "add",
                "text",
                "--title",
                "json 文本",
                "--text",
                "项目 D 完成验收。",
                "--json",
                "--config",
                str(config_path),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"source_id": 10' in captured.out
    assert '"claims_created": 2' in captured.out


def test_add_markdown_uses_markdown_source_type(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    source_path = tmp_path / "source.md"
    init_config(config_path)
    source_path.write_text("# 项目 A\n\n已签署合同。", encoding="utf-8")

    with (
        patch("gmind.cli.ingest_text_source") as ingest_text_source,
        patch("gmind.cli.build_embedding_provider"),
        patch("gmind.cli.embed_source_chunks") as embed_source_chunks,
        patch("gmind.cli.build_llm_provider"),
        patch("gmind.cli.extract_llm_source") as extract_llm_source,
    ):
        ingest_text_source.return_value = SimpleNamespace(source_id=11, chunk_count=1)
        embed_source_chunks.return_value = SimpleNamespace(chunks_embedded=1)
        extract_llm_source.return_value = ExtractResult(
            source_id=11,
            entities_created=1,
            claims_created=1,
            events_created=0,
            relations_created=1,
        )
        exit_code = main(
            [
                "add",
                "markdown",
                "--title",
                "Markdown 资料",
                "--file",
                str(source_path),
                "--config",
                str(config_path),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Added source 11" in captured.out
    assert ingest_text_source.call_args.kwargs["text"] == "# 项目 A\n\n已签署合同。"
    assert ingest_text_source.call_args.kwargs["source_type"] == "markdown"
    assert ingest_text_source.call_args.kwargs["source_path"] == str(
        source_path.resolve()
    )
    embed_source_chunks.assert_called_once()
    extract_llm_source.assert_called_once()


def test_add_text_solo_skips_when_llm_rejects_file(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    source_path = tmp_path / "source.txt"
    init_config(config_path)
    source_path.write_text("临时草稿，不需要进入知识库。", encoding="utf-8")
    provider = SimpleNamespace(
        judge_source_for_ingest=lambda **_: {
            "should_ingest": False,
            "reason": "这是临时草稿。",
            "confidence": 0.91,
        }
    )

    with (
        patch("gmind.cli.build_llm_provider", return_value=provider),
        patch("gmind.cli.record_solo_add_decision") as record_solo_add_decision,
        patch("gmind.cli.ingest_text_source") as ingest_text_source,
    ):
        exit_code = main(
            [
                "add",
                "text",
                "--title",
                "临时草稿",
                "--file",
                str(source_path),
                "--solo",
                "--json",
                "--config",
                str(config_path),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"skipped": true' in captured.out
    assert '"reason": "这是临时草稿。"' in captured.out
    record_solo_add_decision.assert_called_once()
    assert record_solo_add_decision.call_args.kwargs["file_path"] == source_path
    ingest_text_source.assert_not_called()


def test_add_text_solo_imports_when_llm_accepts_file(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    source_path = tmp_path / "source.txt"
    init_config(config_path)
    source_path.write_text("项目 A 在 2026-03-01 签署合同。", encoding="utf-8")
    provider = SimpleNamespace(
        judge_source_for_ingest=lambda **_: {
            "should_ingest": True,
            "reason": "包含项目事实。",
            "confidence": 0.88,
        }
    )

    with (
        patch("gmind.cli.build_llm_provider", return_value=provider),
        patch("gmind.cli.record_solo_add_decision") as record_solo_add_decision,
        patch("gmind.cli.ingest_text_source") as ingest_text_source,
        patch("gmind.cli.build_embedding_provider"),
        patch("gmind.cli.embed_source_chunks") as embed_source_chunks,
        patch("gmind.cli.extract_llm_source") as extract_llm_source,
    ):
        ingest_text_source.return_value = SimpleNamespace(source_id=12, chunk_count=1)
        embed_source_chunks.return_value = SimpleNamespace(chunks_embedded=1)
        extract_llm_source.return_value = ExtractResult(
            source_id=12,
            entities_created=1,
            claims_created=1,
            events_created=1,
            relations_created=1,
        )
        exit_code = main(
            [
                "add",
                "text",
                "--title",
                "项目资料",
                "--file",
                str(source_path),
                "--solo",
                "--config",
                str(config_path),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Solo accepted: 包含项目事实。" in captured.out
    assert "Added source 12" in captured.out
    record_solo_add_decision.assert_called_once()
    assert record_solo_add_decision.call_args.kwargs["file_path"] == source_path
    ingest_text_source.assert_called_once()
    extract_llm_source.assert_called_once()


def test_add_text_solo_dry_run_returns_decision_without_import(
    tmp_path: Path, capsys
) -> None:
    config_path = tmp_path / "gmind.toml"
    source_path = tmp_path / "source.txt"
    init_config(config_path)
    source_path.write_text("项目 A 在 2026-03-01 签署合同。", encoding="utf-8")
    provider = SimpleNamespace(
        judge_source_for_ingest=lambda **_: {
            "should_ingest": True,
            "reason": "包含项目事实。",
            "confidence": 0.88,
        }
    )

    with (
        patch("gmind.cli.build_llm_provider", return_value=provider),
        patch("gmind.cli.record_solo_add_decision") as record_solo_add_decision,
        patch("gmind.cli.ingest_text_source") as ingest_text_source,
        patch("gmind.cli.embed_source_chunks") as embed_source_chunks,
        patch("gmind.cli.extract_llm_source") as extract_llm_source,
    ):
        exit_code = main(
            [
                "add",
                "text",
                "--title",
                "项目资料",
                "--file",
                str(source_path),
                "--solo",
                "--dry-run",
                "--json",
                "--config",
                str(config_path),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["dry_run"] is True
    assert payload["source_id"] is None
    assert payload["skipped"] is False
    assert payload["solo_decision"]["should_ingest"] is True
    assert payload["solo_decision"]["reason"] == "包含项目事实。"
    assert payload["title"] == "项目资料"
    assert payload["source_path"] == str(source_path.resolve())
    assert record_solo_add_decision.call_args.kwargs["dry_run"] is True
    ingest_text_source.assert_not_called()
    embed_source_chunks.assert_not_called()
    extract_llm_source.assert_not_called()


def test_add_text_dry_run_requires_solo(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    source_path = tmp_path / "source.txt"
    init_config(config_path)
    source_path.write_text("项目 A 在 2026-03-01 签署合同。", encoding="utf-8")

    exit_code = main(
        [
            "add",
            "text",
            "--title",
            "项目资料",
            "--file",
            str(source_path),
            "--dry-run",
            "--config",
            str(config_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--dry-run requires --solo" in captured.err


def test_add_text_solo_requires_file_input(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)

    exit_code = main(
        [
            "add",
            "text",
            "--title",
            "直接文本",
            "--text",
            "项目 A 已签署合同。",
            "--solo",
            "--config",
            str(config_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--solo requires --file input" in captured.err


def test_ask_prints_synthesized_answer(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    result = AskResult(
        question="项目 A 当前进展如何？",
        answer="项目 A 已签署合同。",
        evidence=[
            EvidenceChunk(
                source_id=1,
                chunk_id=2,
                title="测试资料",
                text="项目 A 在 2026-03-01 签署合同。",
                score=0.82,
            )
        ],
        followups=["确认验收状态"],
    )

    with (
        patch("gmind.cli.build_embedding_provider"),
        patch("gmind.cli.build_llm_provider"),
        patch("gmind.cli.answer_question", return_value=result),
    ):
        exit_code = main(["ask", "项目 A 当前进展如何？", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "项目 A 已签署合同" in captured.out
    assert "evidence" in captured.out
    assert "followups" in captured.out


def test_ask_can_print_json(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    result = AskResult(
        question="项目 A 当前进展如何？",
        answer="项目 A 已签署合同。",
        evidence=[
            EvidenceChunk(
                source_id=1,
                chunk_id=2,
                title="测试资料",
                text="项目 A 在 2026-03-01 签署合同。",
                score=0.82,
            )
        ],
        followups=[],
    )

    with (
        patch("gmind.cli.build_embedding_provider"),
        patch("gmind.cli.build_llm_provider"),
        patch("gmind.cli.answer_question", return_value=result),
    ):
        exit_code = main(
            ["ask", "项目 A 当前进展如何？", "--json", "--config", str(config_path)]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"answer": "项目 A 已签署合同。"' in captured.out
    assert '"score": 0.82' in captured.out


def test_status_prints_readiness(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    check = DatabaseCheck(
        vector_extension=True,
        tables=REQUIRED_TABLES,
        views=REQUIRED_VIEWS,
    )
    entities = [
        EntitySummary(
            id=1,
            name="项目 A",
            entity_type="project",
            status="active",
            claim_count=2,
            event_count=1,
        )
    ]

    with (
        patch("gmind.cli.check_database", return_value=check),
        patch("gmind.cli.list_entities", return_value=entities),
    ):
        exit_code = main(["status", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "gmind: ready" in captured.out
    assert "1 knowledge points, 2 facts, 1 events" in captured.out


def test_doctor_can_print_json(tmp_path: Path, monkeypatch, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
    check = DatabaseCheck(
        vector_extension=True,
        tables=REQUIRED_TABLES,
        views=REQUIRED_VIEWS,
    )

    with (
        patch("gmind.cli.check_database", return_value=check),
        patch("gmind.cli.list_entities", return_value=[]),
    ):
        exit_code = main(["doctor", "--json", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"ok": true' in captured.out
    assert '"name": "api_key"' in captured.out


def test_db_init_uses_configured_database_url(tmp_path: Path) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)

    with patch("gmind.cli.init_database") as init_database:
        exit_code = main(["db", "init", "--config", str(config_path)])

    assert exit_code == 0
    init_database.assert_called_once_with("postgresql://localhost:5432/gmind")


def test_db_init_reports_missing_config(capsys) -> None:
    exit_code = main(["db", "init", "--config", "/missing/gmind.toml"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Config error" in captured.err


def test_db_check_reports_success(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    check = DatabaseCheck(
        vector_extension=True,
        tables=REQUIRED_TABLES,
        views=REQUIRED_VIEWS,
    )

    with patch("gmind.cli.check_database", return_value=check):
        exit_code = main(["db", "check", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Database check passed." in captured.out


def test_db_check_reports_missing_schema(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    check = DatabaseCheck(
        vector_extension=True,
        tables=["sources"],
        views=[],
    )

    with patch("gmind.cli.check_database", return_value=check):
        exit_code = main(["db", "check", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "missing tables" in captured.out
    assert "missing views" in captured.out


def test_ingest_text_uses_config_and_file(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    source_path = tmp_path / "source.txt"
    init_config(config_path)
    source_path.write_text("hello gmind", encoding="utf-8")

    with patch("gmind.cli.ingest_text_source") as ingest_text_source:
        ingest_text_source.return_value.source_id = 123
        ingest_text_source.return_value.chunk_count = 1
        exit_code = main(
            [
                "ingest",
                "text",
                "--config",
                str(config_path),
                "--title",
                "Test Source",
                "--file",
                str(source_path),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Ingested source 123" in captured.out
    ingest_text_source.assert_called_once()
    assert ingest_text_source.call_args.kwargs["title"] == "Test Source"
    assert ingest_text_source.call_args.kwargs["text"] == "hello gmind"
    assert ingest_text_source.call_args.kwargs["source_path"] == str(
        source_path.resolve()
    )


def test_ingest_text_reports_missing_file(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)

    exit_code = main(
        [
            "ingest",
            "text",
            "--config",
            str(config_path),
            "--title",
            "Missing Source",
            "--file",
            str(tmp_path / "missing.txt"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "file not found" in captured.err


def test_sources_list_prints_sources(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    sources = [
        SourceSummary(
            id=1,
            title="Project note",
            source_type="text",
            chunk_count=2,
            created_at="2026-05-18 12:00:00+00",
        )
    ]

    with patch("gmind.cli.list_sources", return_value=sources):
        exit_code = main(["sources", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Project note" in captured.out
    assert "chunks" in captured.out


def test_source_show_prints_chunks(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    source = SourceDetail(
        id=1,
        title="Project note",
        source_type="text",
        raw_text="hello gmind",
        created_at="2026-05-18 12:00:00+00",
        chunks=[SourceChunk(id=10, chunk_index=0, chunk_text="hello gmind")],
    )

    with patch("gmind.cli.get_source", return_value=source):
        exit_code = main(["source", "show", "1", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "title: Project note" in captured.out
    assert "chunk 0 [10]" in captured.out


def test_source_show_reports_missing_source(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)

    with patch("gmind.cli.get_source", return_value=None):
        exit_code = main(["source", "show", "404", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Source not found: 404" in captured.err


def test_extract_stub_prints_counts(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    result = ExtractResult(
        source_id=1,
        entities_created=1,
        claims_created=2,
        events_created=2,
        relations_created=6,
    )

    with patch("gmind.cli.extract_stub_source", return_value=result):
        exit_code = main(["extract", "stub", "1", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Extracted source 1." in captured.out
    assert "events_created: 2" in captured.out


def test_extract_stub_reports_missing_source(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)

    with patch("gmind.cli.extract_stub_source", return_value=None):
        exit_code = main(["extract", "stub", "404", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Source not found: 404" in captured.err


def test_extract_llm_prints_counts(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    result = ExtractResult(
        source_id=1,
        entities_created=1,
        claims_created=1,
        events_created=1,
        relations_created=3,
    )

    with (
        patch("gmind.cli.build_llm_provider"),
        patch("gmind.cli.extract_llm_source", return_value=result),
    ):
        exit_code = main(["extract", "llm", "1", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "claims_created: 1" in captured.out


def test_embed_source_prints_count(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)

    with (
        patch("gmind.cli.build_embedding_provider"),
        patch("gmind.cli.embed_source_chunks") as embed_source_chunks,
    ):
        embed_source_chunks.return_value.chunks_embedded = 2
        exit_code = main(["embed", "source", "1", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Embedded 2 chunks for source 1." in captured.out


def test_embed_pending_prints_count(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)

    with (
        patch("gmind.cli.build_embedding_provider"),
        patch("gmind.cli.embed_pending_chunks") as embed_pending_chunks,
    ):
        embed_pending_chunks.return_value.chunks_embedded = 3
        exit_code = main(["embed", "pending", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Embedded 3 pending chunks." in captured.out


def test_entities_list_prints_entities(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    entities = [
        EntitySummary(
            id=1,
            name="项目 A",
            entity_type="project",
            status="active",
            claim_count=2,
            event_count=2,
        )
    ]

    with patch("gmind.cli.list_entities", return_value=entities):
        exit_code = main(["entities", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "项目 A" in captured.out


def test_entities_list_can_print_json(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    entities = [
        EntitySummary(
            id=1,
            name="项目 A",
            entity_type="project",
            status="active",
            claim_count=2,
            event_count=2,
        )
    ]

    with patch("gmind.cli.list_entities", return_value=entities):
        exit_code = main(["entities", "--json", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"name": "项目 A"' in captured.out


def test_entity_show_prints_entity_page(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    entity = EntityDetail(
        id=1,
        name="项目 A",
        entity_type="project",
        description=None,
        status="active",
        claims=[
            ClaimSummary(
                id=1,
                text="项目 A 已签署合同。",
                claim_type="fact",
                origin="extracted",
                status="active",
                confidence=0.6,
            )
        ],
        events=[],
        tasks=[],
        relations=[],
    )

    with patch("gmind.cli.get_entity", return_value=entity):
        exit_code = main(["entity", "show", "项目 A", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "name: 项目 A" in captured.out
    assert "项目 A 已签署合同" in captured.out


def test_entity_show_can_print_json(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    entity = EntityDetail(
        id=1,
        name="项目 A",
        entity_type="project",
        description=None,
        status="active",
        claims=[
            ClaimSummary(
                id=1,
                text="项目 A 已签署合同。",
                claim_type="fact",
                origin="extracted",
                status="active",
                confidence=0.6,
            )
        ],
        events=[],
        tasks=[],
        relations=[],
    )

    with patch("gmind.cli.get_entity", return_value=entity):
        exit_code = main(
            ["entity", "show", "项目 A", "--json", "--config", str(config_path)]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"claims":' in captured.out
    assert '"text": "项目 A 已签署合同。"' in captured.out


def test_claim_show_prints_evidence(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    claim = ClaimDetail(
        id=1,
        text="项目 A 已签署合同。",
        claim_type="fact",
        origin="extracted",
        status="active",
        confidence=0.6,
        source_id=1,
        source_chunk_id=1,
        source_chunk_text="项目 A 在 2026-03-01 签署合同。",
        entities=[],
        relations=[],
    )

    with patch("gmind.cli.get_claim", return_value=claim):
        exit_code = main(["claim", "show", "1", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "evidence:" in captured.out
    assert "项目 A 已签署合同" in captured.out


def test_events_timeline_prints_events(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    events = [
        EventSummary(
            id=1,
            event_type="contract_signed",
            title="项目 A 签署合同",
            occurred_at="2026-03-01 00:00:00+00",
            confidence=0.6,
        )
    ]

    with patch("gmind.cli.list_events", return_value=events):
        exit_code = main(
            ["events", "timeline", "--entity", "项目 A", "--config", str(config_path)]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "timeline: 项目 A" in captured.out
    assert "contract_signed" in captured.out


def test_relations_for_prints_relations(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    relations = [
        RelationSummary(
            id=1,
            subject_type="claim",
            subject_id=1,
            predicate="about",
            object_type="entity",
            object_id=1,
            confidence=0.6,
        )
    ]

    with patch("gmind.cli.list_relations", return_value=relations):
        exit_code = main(
            ["relations", "for", "claim", "1", "--config", str(config_path)]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "claim:1 --about--> entity:1" in captured.out


def test_task_show_prints_task(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    task = TaskDetail(
        id=1,
        task_type="verify_claim",
        title="验证 claim",
        description=None,
        status="open",
        priority=1,
        related_entity_id=1,
        source_id=None,
        claim_id=1,
        event_id=None,
        next_run_at=None,
        last_error=None,
    )

    with patch("gmind.cli.get_task", return_value=task):
        exit_code = main(["task", "show", "1", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "title: 验证 claim" in captured.out


def test_tasks_list_prints_tasks(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    tasks = [
        TaskSummary(
            id=1,
            task_type="verify_claim",
            title="验证 claim",
            status="open",
            priority=1,
            next_run_at=None,
        )
    ]

    with patch("gmind.cli.list_tasks", return_value=tasks):
        exit_code = main(["tasks", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "验证 claim" in captured.out


def test_logs_list_prints_logs(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "gmind.toml"
    init_config(config_path)
    logs = [
        LogSummary(
            id=1,
            action="source_ingested",
            title="Ingested source",
            object_type="source",
            object_id=1,
            created_at="2026-05-19 12:00:00+00",
        )
    ]

    with patch("gmind.cli.list_logs", return_value=logs):
        exit_code = main(["logs", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "source_ingested" in captured.out
