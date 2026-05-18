from __future__ import annotations

from dataclasses import dataclass

import psycopg

from gmind.config import ModelConfig
from gmind.providers import EmbeddingProvider


@dataclass(frozen=True)
class EmbedResult:
    chunks_embedded: int


def embed_source_chunks(
    database_url: str,
    *,
    source_id: int,
    model_config: ModelConfig,
    provider: EmbeddingProvider,
) -> EmbedResult | None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("select id from sources where id = %s", (source_id,))
            if cursor.fetchone() is None:
                return None

            cursor.execute(
                """
                select id, chunk_text
                from source_chunks
                where source_id = %s
                  and embedding is null
                order by chunk_index
                """,
                (source_id,),
            )
            chunks = cursor.fetchall()
            embedded_count = _embed_chunk_rows(cursor, chunks, model_config, provider)

            cursor.execute(
                """
                insert into logs (action, title, summary, actor, object_type, object_id)
                values ('source_embedded', %s, %s, 'gmind', 'source', %s)
                """,
                (
                    f"Embedded source {source_id}",
                    f"Embedded {embedded_count} source chunks.",
                    source_id,
                ),
            )

    return EmbedResult(chunks_embedded=embedded_count)


def embed_pending_chunks(
    database_url: str,
    *,
    limit: int,
    model_config: ModelConfig,
    provider: EmbeddingProvider,
) -> EmbedResult:
    if limit <= 0:
        raise ValueError("limit must be positive")

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id, chunk_text
                from source_chunks
                where embedding is null
                order by id
                limit %s
                """,
                (limit,),
            )
            chunks = cursor.fetchall()
            embedded_count = _embed_chunk_rows(cursor, chunks, model_config, provider)

            cursor.execute(
                """
                insert into logs (action, title, summary, actor)
                values ('chunks_embedded', 'Embedded pending chunks', %s, 'gmind')
                """,
                (f"Embedded {embedded_count} source chunks.",),
            )

    return EmbedResult(chunks_embedded=embedded_count)


def _embed_chunk_rows(
    cursor,
    chunks,
    model_config: ModelConfig,
    provider: EmbeddingProvider,
) -> int:
    if not chunks:
        return 0

    embeddings = provider.embed_texts([row[1] for row in chunks])
    for (chunk_id, _chunk_text), embedding in zip(chunks, embeddings, strict=True):
        if len(embedding) != model_config.embedding_dim:
            raise ValueError(
                "Embedding dimension mismatch: "
                f"expected {model_config.embedding_dim}, got {len(embedding)}"
            )
        cursor.execute(
            """
            update source_chunks
            set embedding_model = %s,
                embedding_dim = %s,
                embedding = %s::vector
            where id = %s
            """,
            (
                model_config.embedding_model,
                model_config.embedding_dim,
                _vector_literal(embedding),
                chunk_id,
            ),
        )

    return len(chunks)


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"
