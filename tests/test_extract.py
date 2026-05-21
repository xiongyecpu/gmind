from datetime import date

from gmind.extract import _event_candidate, _find_project, _safe_parse_date, _split_sentences


def test_find_project_normalizes_spaces() -> None:
    assert _find_project("项目   A 在 2026-03-01 签署合同。") == "项目 A"


def test_event_candidate_extracts_contract_signed() -> None:
    event = _event_candidate("项目 A 在 2026-03-01 签署合同。", "项目 A")

    assert event is not None
    assert event.event_type == "contract_signed"
    assert event.title == "项目 A 签署合同"
    assert event.occurred_at == date(2026, 3, 1)


def test_event_candidate_extracts_payment_received() -> None:
    event = _event_candidate("项目 A 在 2026-03-05 收到首付款。", "项目 A")

    assert event is not None
    assert event.event_type == "payment_received"
    assert event.title == "项目 A 收到首付款"
    assert event.occurred_at == date(2026, 3, 5)


def test_split_sentences_handles_chinese_periods() -> None:
    assert _split_sentences("项目 A 签署合同。项目 A 收到首付款。") == [
        "项目 A 签署合同。",
        "项目 A 收到首付款。",
    ]


def test_safe_parse_date_parses_various_formats() -> None:
    assert _safe_parse_date("2024-04-16") == date(2024, 4, 16)
    assert _safe_parse_date("2024-04") == date(2024, 4, 1)
    assert _safe_parse_date("2024") == date(2024, 1, 1)
    assert _safe_parse_date(None) is None
    assert _safe_parse_date("") is None
    assert _safe_parse_date("invalid") is None
