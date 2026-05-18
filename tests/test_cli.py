from pathlib import Path
from unittest.mock import patch

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
