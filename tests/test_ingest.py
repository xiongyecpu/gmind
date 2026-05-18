import pytest

from gmind.ingest import split_text


def test_split_text_returns_overlapping_chunks() -> None:
    chunks = split_text("abcdefghij", chunk_size=4, chunk_overlap=1)

    assert chunks == ["abcd", "defg", "ghij"]


def test_split_text_rejects_empty_text() -> None:
    assert split_text("   ") == []


def test_split_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        split_text("hello", chunk_size=4, chunk_overlap=4)
