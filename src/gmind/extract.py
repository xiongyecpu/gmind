from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Any

import psycopg

from gmind.providers import LLMProvider


SENTENCE_RE = re.compile(r"[^。！？!?\n]+[。！？!?]?")
PROJECT_RE = re.compile(r"项目\s*[A-Za-z0-9]+")
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


@dataclass(frozen=True)
class ExtractResult:
    source_id: int
    entities_created: int
    claims_created: int
    events_created: int
    relations_created: int


@dataclass(frozen=True)
class ChunkRow:
    id: int
    chunk_text: str


@dataclass(frozen=True)
class EventCandidate:
    event_type: str
    title: str
    occurred_at: date
    entity_name: str


def extract_stub_source(database_url: str, source_id: int) -> ExtractResult | None:
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
                order by chunk_index
                """,
                (source_id,),
            )
            chunks = [ChunkRow(id=row[0], chunk_text=row[1]) for row in cursor.fetchall()]

            entities_created = 0
            claims_created = 0
            events_created = 0
            relations_created = 0
            entity_ids: dict[str, int] = {}

            for chunk in chunks:
                for sentence in _split_sentences(chunk.chunk_text):
                    entity_name = _find_project(sentence)
                    if entity_name is None:
                        continue

                    entity_id, created = _get_or_create_entity(cursor, entity_name)
                    entity_ids[entity_name] = entity_id
                    entities_created += int(created)

                    claim_id, created = _get_or_create_claim(
                        cursor,
                        text=sentence,
                        source_id=source_id,
                        source_chunk_id=chunk.id,
                    )
                    claims_created += int(created)
                    relations_created += _insert_relation(
                        cursor,
                        subject_type="claim",
                        subject_id=claim_id,
                        predicate="about",
                        object_type="entity",
                        object_id=entity_id,
                        source_id=source_id,
                    )
                    relations_created += _insert_relation(
                        cursor,
                        subject_type="claim",
                        subject_id=claim_id,
                        predicate="supported_by",
                        object_type="source_chunk",
                        object_id=chunk.id,
                        source_id=source_id,
                    )

                    event = _event_candidate(sentence, entity_name)
                    if event is None:
                        continue

                    event_id, created = _get_or_create_event(
                        cursor,
                        event=event,
                        entity_id=entity_id,
                        source_id=source_id,
                        source_chunk_id=chunk.id,
                    )
                    events_created += int(created)
                    relations_created += _insert_relation(
                        cursor,
                        subject_type="event",
                        subject_id=event_id,
                        predicate="involves",
                        object_type="entity",
                        object_id=entity_id,
                        source_id=source_id,
                    )
                    relations_created += _insert_relation(
                        cursor,
                        subject_type="claim",
                        subject_id=claim_id,
                        predicate="derived_from",
                        object_type="event",
                        object_id=event_id,
                        source_id=source_id,
                    )

            cursor.execute(
                """
                insert into logs (action, title, summary, actor, object_type, object_id)
                values ('source_extracted_stub', %s, %s, 'gmind', 'source', %s)
                """,
                (
                    f"Stub extracted source {source_id}",
                    (
                        f"Created {entities_created} entities, {claims_created} claims, "
                        f"{events_created} events, and {relations_created} relations."
                    ),
                    source_id,
                ),
            )

    return ExtractResult(
        source_id=source_id,
        entities_created=entities_created,
        claims_created=claims_created,
        events_created=events_created,
        relations_created=relations_created,
    )


def extract_llm_source(
    database_url: str,
    source_id: int,
    provider: LLMProvider,
) -> ExtractResult | None:
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
                order by chunk_index
                """,
                (source_id,),
            )
            chunks = [ChunkRow(id=row[0], chunk_text=row[1]) for row in cursor.fetchall()]

            totals = ExtractResult(
                source_id=source_id,
                entities_created=0,
                claims_created=0,
                events_created=0,
                relations_created=0,
            )

            extractions = _extract_all_chunks(chunks, provider)
            for chunk, extraction in zip(chunks, extractions, strict=True):
                chunk_result = _write_llm_extraction(
                    cursor,
                    source_id=source_id,
                    source_chunk_id=chunk.id,
                    extraction=extraction,
                )
                totals = ExtractResult(
                    source_id=source_id,
                    entities_created=totals.entities_created
                    + chunk_result.entities_created,
                    claims_created=totals.claims_created + chunk_result.claims_created,
                    events_created=totals.events_created + chunk_result.events_created,
                    relations_created=totals.relations_created
                    + chunk_result.relations_created,
                )

            cursor.execute(
                """
                insert into logs (action, title, summary, actor, object_type, object_id)
                values ('source_extracted_llm', %s, %s, 'gmind', 'source', %s)
                """,
                (
                    f"LLM extracted source {source_id}",
                    (
                        f"Created {totals.entities_created} entities, "
                        f"{totals.claims_created} claims, {totals.events_created} "
                        f"events, and {totals.relations_created} relations."
                    ),
                    source_id,
                ),
            )

    return totals


def _extract_all_chunks(
    chunks: list[ChunkRow],
    provider: LLMProvider,
    max_workers: int = 5,
) -> list[dict[str, Any]]:
    if not chunks:
        return []
    workers = min(max_workers, len(chunks))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(lambda c: provider.extract_chunk(c.chunk_text), chunks))


def _safe_parse_date(value: object) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt == "%Y":
                return date(parsed.year, 1, 1)
            if fmt == "%Y-%m":
                return date(parsed.year, parsed.month, 1)
            return date(parsed.year, parsed.month, parsed.day)
        except ValueError:
            continue
    return None


def _split_sentences(text: str) -> list[str]:
    return [match.group(0).strip() for match in SENTENCE_RE.finditer(text) if match.group(0).strip()]


def _find_project(text: str) -> str | None:
    match = PROJECT_RE.search(text)
    if match is None:
        return None
    return " ".join(match.group(0).split())


def _event_candidate(sentence: str, entity_name: str) -> EventCandidate | None:
    date_match = DATE_RE.search(sentence)
    if date_match is None:
        return None

    occurred_at = date(
        int(date_match.group(1)),
        int(date_match.group(2)),
        int(date_match.group(3)),
    )

    if "签署合同" in sentence or "签合同" in sentence:
        return EventCandidate(
            event_type="contract_signed",
            title=f"{entity_name} 签署合同",
            occurred_at=occurred_at,
            entity_name=entity_name,
        )

    if "收到首付款" in sentence or "收到付款" in sentence:
        return EventCandidate(
            event_type="payment_received",
            title=f"{entity_name} 收到首付款",
            occurred_at=occurred_at,
            entity_name=entity_name,
        )

    return None


def _write_llm_extraction(
    cursor,
    *,
    source_id: int,
    source_chunk_id: int,
    extraction: dict[str, Any],
) -> ExtractResult:
    entities_created = 0
    claims_created = 0
    events_created = 0
    relations_created = 0
    entity_ids: dict[str, int] = {}

    for entity in extraction.get("entities", []):
        canonical_name = entity["canonical_name"]
        entity_id, created = _get_or_create_entity(
            cursor,
            entity_name=entity["name"],
            entity_type=entity.get("entity_type", "unknown"),
            canonical_name=canonical_name,
        )
        entity_ids[canonical_name] = entity_id
        entity_ids[entity["name"]] = entity_id
        entities_created += int(created)

    for claim in extraction.get("claims", []):
        claim_id, created = _get_or_create_claim(
            cursor,
            text=claim["text"],
            source_id=source_id,
            source_chunk_id=source_chunk_id,
            claim_type=claim.get("claim_type", "fact"),
            confidence=claim.get("confidence", 0.5),
        )
        claims_created += int(created)
        relations_created += _insert_relation(
            cursor,
            subject_type="claim",
            subject_id=claim_id,
            predicate="supported_by",
            object_type="source_chunk",
            object_id=source_chunk_id,
            source_id=source_id,
        )
        for entity_name in claim.get("about_entities", []):
            entity_id = entity_ids.get(entity_name)
            if entity_id is None:
                entity_id, created = _get_or_create_entity(
                    cursor,
                    entity_name=entity_name,
                    entity_type="unknown",
                    canonical_name=entity_name,
                )
                entities_created += int(created)
                entity_ids[entity_name] = entity_id
            relations_created += _insert_relation(
                cursor,
                subject_type="claim",
                subject_id=claim_id,
                predicate="about",
                object_type="entity",
                object_id=entity_id,
                source_id=source_id,
            )

    for event in extraction.get("events", []):
        related_entity_ids = []
        for entity_name in event.get("related_entities", []):
            entity_id = entity_ids.get(entity_name)
            if entity_id is None:
                entity_id, created = _get_or_create_entity(
                    cursor,
                    entity_name=entity_name,
                    entity_type="unknown",
                    canonical_name=entity_name,
                )
                entities_created += int(created)
                entity_ids[entity_name] = entity_id
            related_entity_ids.append(entity_id)

        primary_entity_id = _primary_related_entity_id(entity_ids, related_entity_ids)
        event_id, created = _get_or_create_llm_event(
            cursor,
            event=event,
            related_entity_id=primary_entity_id,
            source_id=source_id,
            source_chunk_id=source_chunk_id,
        )
        events_created += int(created)
        for entity_id in related_entity_ids:
            relations_created += _insert_relation(
                cursor,
                subject_type="event",
                subject_id=event_id,
                predicate="involves",
                object_type="entity",
                object_id=entity_id,
                source_id=source_id,
            )

    for task in extraction.get("tasks", []):
        related_entity_id = None
        related_entities = task.get("related_entities", [])
        if related_entities:
            related_entity_id = entity_ids.get(related_entities[0])
        cursor.execute(
            """
            insert into tasks (
                task_type,
                title,
                description,
                priority,
                related_entity_id,
                source_id
            )
            values (%s, %s, %s, %s, %s, %s)
            """,
            (
                task.get("task_type", "research_question"),
                task["title"],
                task.get("description"),
                task.get("priority", 0),
                related_entity_id,
                source_id,
            ),
        )

    return ExtractResult(
        source_id=source_id,
        entities_created=entities_created,
        claims_created=claims_created,
        events_created=events_created,
        relations_created=relations_created,
    )


def _get_or_create_entity(
    cursor,
    entity_name: str,
    entity_type: str = "project",
    canonical_name: str | None = None,
) -> tuple[int, bool]:
    canonical_name = canonical_name or entity_name
    cursor.execute(
        """
        select id
        from entities
        where canonical_name = %s
        order by id
        limit 1
        """,
        (canonical_name,),
    )
    row = cursor.fetchone()
    if row is not None:
        return row[0], False

    cursor.execute(
        """
        insert into entities (
            name,
            entity_type,
            canonical_name,
            status,
            merge_status
        )
        values (%s, %s, %s, 'active', 'canonical')
        returning id
        """,
        (entity_name, entity_type, canonical_name),
    )
    return cursor.fetchone()[0], True


def _get_or_create_claim(
    cursor,
    *,
    text: str,
    source_id: int,
    source_chunk_id: int,
    claim_type: str = "fact",
    confidence: float = 0.6,
) -> tuple[int, bool]:
    cursor.execute(
        """
        select id
        from claims
        where text = %s
          and source_chunk_id = %s
        order by id
        limit 1
        """,
        (text, source_chunk_id),
    )
    row = cursor.fetchone()
    if row is not None:
        return row[0], False

    cursor.execute(
        """
        insert into claims (
            text,
            claim_type,
            origin,
            status,
            confidence,
            source_id,
            source_chunk_id
        )
        values (%s, %s, 'extracted', 'active', %s, %s, %s)
        returning id
        """,
        (text, claim_type, confidence, source_id, source_chunk_id),
    )
    return cursor.fetchone()[0], True


def _get_or_create_llm_event(
    cursor,
    *,
    event: dict[str, Any],
    related_entity_id: int | None,
    source_id: int,
    source_chunk_id: int,
) -> tuple[int, bool]:
    cursor.execute(
        """
        select id
        from events
        where event_type = %s
          and title = %s
          and source_chunk_id = %s
        order by id
        limit 1
        """,
        (event["event_type"], event["title"], source_chunk_id),
    )
    row = cursor.fetchone()
    if row is not None:
        return row[0], False

    occurred_at = _safe_parse_date(event.get("occurred_at"))
    cursor.execute(
        """
        insert into events (
            event_type,
            title,
            description,
            occurred_at,
            occurred_at_precision,
            related_entity_id,
            source_id,
            source_chunk_id,
            confidence
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning id
        """,
        (
            event["event_type"],
            event["title"],
            event.get("description"),
            occurred_at,
            event.get("occurred_at_precision", "unknown"),
            related_entity_id,
            source_id,
            source_chunk_id,
            event.get("confidence", 0.5),
        ),
    )
    return cursor.fetchone()[0], True


def _primary_related_entity_id(
    entity_ids: dict[str, int],
    related_entity_ids: list[int],
) -> int | None:
    if not related_entity_ids:
        return None
    for entity_name, entity_id in entity_ids.items():
        if entity_id in related_entity_ids and entity_name.startswith("项目 "):
            return entity_id
    return related_entity_ids[0]


def _get_or_create_event(
    cursor,
    *,
    event: EventCandidate,
    entity_id: int,
    source_id: int,
    source_chunk_id: int,
) -> tuple[int, bool]:
    cursor.execute(
        """
        select id
        from events
        where event_type = %s
          and title = %s
          and source_chunk_id = %s
        order by id
        limit 1
        """,
        (event.event_type, event.title, source_chunk_id),
    )
    row = cursor.fetchone()
    if row is not None:
        return row[0], False

    cursor.execute(
        """
        insert into events (
            event_type,
            title,
            occurred_at,
            occurred_at_precision,
            subject_entity_id,
            related_entity_id,
            source_id,
            source_chunk_id,
            confidence
        )
        values (%s, %s, %s, 'day', %s, %s, %s, %s, 0.6)
        returning id
        """,
        (
            event.event_type,
            event.title,
            event.occurred_at,
            entity_id,
            entity_id,
            source_id,
            source_chunk_id,
        ),
    )
    return cursor.fetchone()[0], True


def _insert_relation(
    cursor,
    *,
    subject_type: str,
    subject_id: int,
    predicate: str,
    object_type: str,
    object_id: int,
    source_id: int,
) -> int:
    cursor.execute(
        """
        insert into relations (
            subject_type,
            subject_id,
            predicate,
            object_type,
            object_id,
            source_id,
            confidence
        )
        values (%s, %s, %s, %s, %s, %s, 0.6)
        on conflict do nothing
        returning id
        """,
        (subject_type, subject_id, predicate, object_type, object_id, source_id),
    )
    return int(cursor.fetchone() is not None)
