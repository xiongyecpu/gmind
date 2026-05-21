from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from gmind.solo import (
    SoloAddDecision,
    judge_solo_add_file,
    record_solo_add_decision,
)


def test_judge_solo_add_file_normalizes_llm_decision(tmp_path: Path) -> None:
    source_path = tmp_path / "source.md"
    provider = SimpleNamespace(
        judge_source_for_ingest=lambda **_: {
            "should_ingest": True,
            "reason": "包含可复用的项目事实。",
            "confidence": 0.86,
        }
    )

    decision = judge_solo_add_file(
        title="项目资料",
        file_path=source_path,
        text="项目 A 已签署合同。",
        provider=provider,
    )

    assert decision.should_ingest is True
    assert decision.reason == "包含可复用的项目事实。"
    assert decision.confidence == 0.86


def test_judge_solo_add_file_rejects_empty_text(tmp_path: Path) -> None:
    source_path = tmp_path / "empty.md"
    provider = SimpleNamespace(judge_source_for_ingest=lambda **_: None)

    decision = judge_solo_add_file(
        title="空文件",
        file_path=source_path,
        text="   ",
        provider=provider,
    )

    assert decision.should_ingest is False
    assert decision.reason == "文件没有可判断的文本内容。"
    assert decision.confidence == 1.0


def test_record_solo_add_decision_writes_rejection_log(tmp_path: Path) -> None:
    source_path = tmp_path / "source.md"
    cursor = MagicMock()
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor

    with patch("gmind.solo.psycopg.connect", return_value=connection):
        record_solo_add_decision(
            "postgresql://example/gmind",
            title="临时草稿",
            file_path=source_path,
            decision=SoloAddDecision(
                should_ingest=False,
                reason="这是临时草稿。",
                confidence=0.91,
            ),
            dry_run=True,
        )

    cursor.execute.assert_called_once()
    args = cursor.execute.call_args.args
    assert "insert into logs" in args[0]
    assert args[1][0] == "solo_add_rejected"
    assert args[1][1] == "Solo rejected: 临时草稿"
    assert args[1][2] == "这是临时草稿。"
    assert args[1][3].obj["dry_run"] is True
