from __future__ import annotations

from dataclasses import dataclass

import psycopg
from psycopg.types.json import Jsonb


DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 150


@dataclass(frozen=True)
class IngestResult:
    source_id: int
    chunk_count: int


def split_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    normalized_text = text.strip()
    if not normalized_text:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    text_length = len(normalized_text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = normalized_text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end == text_length:
            break

        start = end - chunk_overlap

    return chunks


def ingest_text_source(
    database_url: str,
    *,
    title: str,
    text: str,
    source_type: str = "text",
    source_path: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> IngestResult:
    chunks = split_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        raise ValueError("Cannot ingest empty text")
    metadata = {}
    if source_path is not None:
        metadata["source_path"] = source_path

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into sources (
                    title,
                    source_type,
                    raw_text,
                    captured_at,
                    metadata_json
                )
                values (%s, %s, %s, now(), %s)
                returning id
                """,
                (title, source_type, text, Jsonb(metadata)),
            )
            source_id = cursor.fetchone()[0]

            cursor.executemany(
                """
                insert into source_chunks (
                    source_id,
                    chunk_index,
                    chunk_text
                )
                values (%s, %s, %s)
                """,
                [
                    (source_id, chunk_index, chunk)
                    for chunk_index, chunk in enumerate(chunks)
                ],
            )

            cursor.execute(
                """
                insert into logs (
                    action,
                    title,
                    summary,
                    actor,
                    object_type,
                    object_id,
                    metadata_json
                )
                values (
                    'source_ingested',
                    %s,
                    %s,
                    'gmind',
                    'source',
                    %s,
                    %s
                )
                """,
                (
                    f"Ingested source: {title}",
                    f"Created {len(chunks)} source chunks.",
                    source_id,
                    Jsonb({"chunk_count": len(chunks), **metadata}),
                ),
            )

    return IngestResult(source_id=source_id, chunk_count=len(chunks))
