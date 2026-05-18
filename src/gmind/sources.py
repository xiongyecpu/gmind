from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class SourceSummary:
    id: int
    title: str
    source_type: str
    chunk_count: int
    created_at: str


@dataclass(frozen=True)
class SourceChunk:
    id: int
    chunk_index: int
    chunk_text: str


@dataclass(frozen=True)
class SourceDetail:
    id: int
    title: str
    source_type: str
    raw_text: str | None
    created_at: str
    chunks: list[SourceChunk]


def list_sources(database_url: str, *, limit: int = 20) -> list[SourceSummary]:
    if limit <= 0:
        raise ValueError("limit must be positive")

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    s.id,
                    s.title,
                    s.source_type,
                    count(sc.id) as chunk_count,
                    s.created_at::text
                from sources s
                left join source_chunks sc on sc.source_id = s.id
                group by s.id
                order by s.created_at desc, s.id desc
                limit %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()

    return [
        SourceSummary(
            id=row[0],
            title=row[1],
            source_type=row[2],
            chunk_count=row[3],
            created_at=row[4],
        )
        for row in rows
    ]


def get_source(database_url: str, source_id: int) -> SourceDetail | None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id, title, source_type, raw_text, created_at::text
                from sources
                where id = %s
                """,
                (source_id,),
            )
            source_row = cursor.fetchone()
            if source_row is None:
                return None

            cursor.execute(
                """
                select id, chunk_index, chunk_text
                from source_chunks
                where source_id = %s
                order by chunk_index
                """,
                (source_id,),
            )
            chunk_rows = cursor.fetchall()

    return SourceDetail(
        id=source_row[0],
        title=source_row[1],
        source_type=source_row[2],
        raw_text=source_row[3],
        created_at=source_row[4],
        chunks=[
            SourceChunk(
                id=row[0],
                chunk_index=row[1],
                chunk_text=row[2],
            )
            for row in chunk_rows
        ],
    )
