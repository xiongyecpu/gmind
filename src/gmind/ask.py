from __future__ import annotations

from dataclasses import dataclass

import psycopg

from gmind.config import ModelConfig
from gmind.embed import _vector_literal
from gmind.providers import EmbeddingProvider, LLMProvider


@dataclass(frozen=True)
class EvidenceChunk:
    source_id: int
    chunk_id: int
    title: str
    text: str
    score: float


@dataclass(frozen=True)
class AskResult:
    question: str
    answer: str
    evidence: list[EvidenceChunk]
    followups: list[str]


def answer_question(
    database_url: str,
    *,
    question: str,
    model_config: ModelConfig,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
    limit: int = 5,
) -> AskResult:
    if not question.strip():
        raise ValueError("question must not be empty")
    if limit <= 0:
        raise ValueError("limit must be positive")

    query_embedding = embedding_provider.embed_texts([question])[0]
    if len(query_embedding) != model_config.embedding_dim:
        raise ValueError(
            "Embedding dimension mismatch: "
            f"expected {model_config.embedding_dim}, got {len(query_embedding)}"
        )

    evidence = search_evidence_chunks(
        database_url,
        query_embedding=query_embedding,
        limit=limit,
    )
    if not evidence:
        return AskResult(
            question=question,
            answer="还没有找到相关资料。",
            evidence=[],
            followups=[],
        )

    answer_payload = llm_provider.answer_question(
        question,
        [
            {
                "source_id": item.source_id,
                "chunk_id": item.chunk_id,
                "title": item.title,
                "text": item.text,
                "score": item.score,
            }
            for item in evidence
        ],
    )
    return AskResult(
        question=question,
        answer=answer_payload["answer"],
        evidence=evidence,
        followups=answer_payload["followups"],
    )


def search_evidence_chunks(
    database_url: str,
    *,
    query_embedding: list[float],
    limit: int,
) -> list[EvidenceChunk]:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    s.id,
                    sc.id,
                    s.title,
                    sc.chunk_text,
                    sc.embedding <=> %s::vector as distance
                from source_chunks sc
                join sources s on s.id = sc.source_id
                where sc.embedding is not null
                order by sc.embedding <=> %s::vector
                limit %s
                """,
                (
                    _vector_literal(query_embedding),
                    _vector_literal(query_embedding),
                    limit,
                ),
            )
            return [
                EvidenceChunk(
                    source_id=row[0],
                    chunk_id=row[1],
                    title=row[2],
                    text=row[3],
                    score=max(0.0, 1.0 - float(row[4])),
                )
                for row in cursor.fetchall()
            ]
