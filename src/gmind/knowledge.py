from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class EntitySummary:
    id: int
    name: str
    entity_type: str
    status: str
    claim_count: int
    event_count: int


@dataclass(frozen=True)
class ClaimSummary:
    id: int
    text: str
    claim_type: str
    origin: str
    status: str
    confidence: float | None


@dataclass(frozen=True)
class EventSummary:
    id: int
    event_type: str
    title: str
    occurred_at: str | None
    confidence: float | None


@dataclass(frozen=True)
class TaskSummary:
    id: int
    task_type: str
    title: str
    status: str
    priority: int
    next_run_at: str | None


@dataclass(frozen=True)
class RelationSummary:
    id: int
    subject_type: str
    subject_id: int
    predicate: str
    object_type: str
    object_id: int
    confidence: float | None


@dataclass(frozen=True)
class LogSummary:
    id: int
    action: str
    title: str
    object_type: str | None
    object_id: int | None
    created_at: str


@dataclass(frozen=True)
class EntityDetail:
    id: int
    name: str
    entity_type: str
    description: str | None
    status: str
    claims: list[ClaimSummary]
    events: list[EventSummary]
    tasks: list[TaskSummary]
    relations: list[RelationSummary]


@dataclass(frozen=True)
class ClaimDetail:
    id: int
    text: str
    claim_type: str
    origin: str
    status: str
    confidence: float | None
    source_id: int | None
    source_chunk_id: int | None
    source_chunk_text: str | None
    entities: list[EntitySummary]
    relations: list[RelationSummary]


@dataclass(frozen=True)
class TaskDetail:
    id: int
    task_type: str
    title: str
    description: str | None
    status: str
    priority: int
    related_entity_id: int | None
    source_id: int | None
    claim_id: int | None
    event_id: int | None
    next_run_at: str | None
    last_error: str | None


def list_entities(database_url: str, *, limit: int = 20) -> list[EntitySummary]:
    _validate_limit(limit)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    e.id,
                    e.name,
                    e.entity_type,
                    e.status,
                    count(distinct ec.id) as claim_count,
                    count(distinct ev.id) as event_count
                from entities e
                left join entity_claims_view ec on ec.entity_id = e.id
                left join events ev on ev.related_entity_id = e.id
                group by e.id
                order by e.updated_at desc, e.id desc
                limit %s
                """,
                (limit,),
            )
            return [_entity_summary(row) for row in cursor.fetchall()]


def get_entity(database_url: str, identifier: str) -> EntityDetail | None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            entity_row = _fetch_entity_row(cursor, identifier)
            if entity_row is None:
                return None
            entity_id = entity_row[0]

            cursor.execute(
                """
                select distinct id, text, claim_type, origin, status, confidence
                from entity_claims_view
                where entity_id = %s
                order by id
                """,
                (entity_id,),
            )
            claims = [_claim_summary(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                select id, event_type, title, occurred_at::text, confidence
                from events
                where related_entity_id = %s
                   or subject_entity_id = %s
                   or object_entity_id = %s
                order by occurred_at nulls last, id
                """,
                (entity_id, entity_id, entity_id),
            )
            events = [_event_summary(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                select id, task_type, title, status, priority, next_run_at::text
                from tasks
                where related_entity_id = %s
                order by priority desc, created_at desc
                """,
                (entity_id,),
            )
            tasks = [_task_summary(row) for row in cursor.fetchall()]

            relations = _relations_touching(cursor, "entity", entity_id)

    return EntityDetail(
        id=entity_row[0],
        name=entity_row[1],
        entity_type=entity_row[2],
        description=entity_row[3],
        status=entity_row[4],
        claims=claims,
        events=events,
        tasks=tasks,
        relations=relations,
    )


def list_claims(
    database_url: str,
    *,
    limit: int = 20,
    status: str | None = None,
    entity: str | None = None,
) -> list[ClaimSummary]:
    _validate_limit(limit)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            params: list[object] = []
            where = []
            join = ""

            if entity:
                entity_id = _resolve_entity_id(cursor, entity)
                if entity_id is None:
                    return []
                join = "join entity_claims_view ec on ec.id = c.id"
                where.append("ec.entity_id = %s")
                params.append(entity_id)

            if status:
                where.append("c.status = %s")
                params.append(status)

            where_sql = "where " + " and ".join(where) if where else ""
            params.append(limit)
            cursor.execute(
                f"""
                select distinct c.id, c.text, c.claim_type, c.origin, c.status, c.confidence
                from claims c
                {join}
                {where_sql}
                order by c.id desc
                limit %s
                """,
                params,
            )
            return [_claim_summary(row) for row in cursor.fetchall()]


def get_claim(database_url: str, claim_id: int) -> ClaimDetail | None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    c.id,
                    c.text,
                    c.claim_type,
                    c.origin,
                    c.status,
                    c.confidence,
                    c.source_id,
                    c.source_chunk_id,
                    sc.chunk_text
                from claims c
                left join source_chunks sc on sc.id = c.source_chunk_id
                where c.id = %s
                """,
                (claim_id,),
            )
            claim_row = cursor.fetchone()
            if claim_row is None:
                return None

            cursor.execute(
                """
                select e.id, e.name, e.entity_type, e.status, 0, 0
                from relations r
                join entities e on e.id = r.object_id
                where r.subject_type = 'claim'
                  and r.subject_id = %s
                  and r.object_type = 'entity'
                  and r.predicate in ('about', 'mentions')
                order by e.id
                """,
                (claim_id,),
            )
            entities = [_entity_summary(row) for row in cursor.fetchall()]
            relations = _relations_for(cursor, "claim", claim_id)

    return ClaimDetail(
        id=claim_row[0],
        text=claim_row[1],
        claim_type=claim_row[2],
        origin=claim_row[3],
        status=claim_row[4],
        confidence=claim_row[5],
        source_id=claim_row[6],
        source_chunk_id=claim_row[7],
        source_chunk_text=claim_row[8],
        entities=entities,
        relations=relations,
    )


def list_events(
    database_url: str,
    *,
    limit: int = 20,
    entity: str | None = None,
) -> list[EventSummary]:
    _validate_limit(limit)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            params: list[object] = []
            where = ""
            if entity:
                entity_id = _resolve_entity_id(cursor, entity)
                if entity_id is None:
                    return []
                where = """
                where related_entity_id = %s
                   or subject_entity_id = %s
                   or object_entity_id = %s
                """
                params.extend([entity_id, entity_id, entity_id])

            params.append(limit)
            cursor.execute(
                f"""
                select id, event_type, title, occurred_at::text, confidence
                from events
                {where}
                order by occurred_at nulls last, id
                limit %s
                """,
                params,
            )
            return [_event_summary(row) for row in cursor.fetchall()]


def list_relations(
    database_url: str,
    *,
    limit: int = 20,
    subject_type: str | None = None,
    subject_id: int | None = None,
) -> list[RelationSummary]:
    _validate_limit(limit)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            params: list[object] = []
            where = []
            if subject_type is not None:
                where.append("subject_type = %s")
                params.append(subject_type)
            if subject_id is not None:
                where.append("subject_id = %s")
                params.append(subject_id)

            where_sql = "where " + " and ".join(where) if where else ""
            params.append(limit)
            cursor.execute(
                f"""
                select id, subject_type, subject_id, predicate, object_type, object_id, confidence
                from relations
                {where_sql}
                order by id desc
                limit %s
                """,
                params,
            )
            return [_relation_summary(row) for row in cursor.fetchall()]


def list_tasks(database_url: str, *, limit: int = 20) -> list[TaskSummary]:
    _validate_limit(limit)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id, task_type, title, status, priority, next_run_at::text
                from tasks
                order by priority desc, created_at desc
                limit %s
                """,
                (limit,),
            )
            return [_task_summary(row) for row in cursor.fetchall()]


def get_task(database_url: str, task_id: int) -> TaskDetail | None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    id,
                    task_type,
                    title,
                    description,
                    status,
                    priority,
                    related_entity_id,
                    source_id,
                    claim_id,
                    event_id,
                    next_run_at::text,
                    last_error
                from tasks
                where id = %s
                """,
                (task_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None

    return TaskDetail(
        id=row[0],
        task_type=row[1],
        title=row[2],
        description=row[3],
        status=row[4],
        priority=row[5],
        related_entity_id=row[6],
        source_id=row[7],
        claim_id=row[8],
        event_id=row[9],
        next_run_at=row[10],
        last_error=row[11],
    )


def list_logs(database_url: str, *, limit: int = 20) -> list[LogSummary]:
    _validate_limit(limit)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id, action, title, object_type, object_id, created_at::text
                from logs
                order by created_at desc, id desc
                limit %s
                """,
                (limit,),
            )
            return [
                LogSummary(
                    id=row[0],
                    action=row[1],
                    title=row[2],
                    object_type=row[3],
                    object_id=row[4],
                    created_at=row[5],
                )
                for row in cursor.fetchall()
            ]


def _fetch_entity_row(cursor, identifier: str):
    if identifier.isdigit():
        cursor.execute(
            """
            select id, name, entity_type, description, status
            from entities
            where id = %s
            """,
            (int(identifier),),
        )
    else:
        cursor.execute(
            """
            select id, name, entity_type, description, status
            from entities
            where name = %s
               or canonical_name = %s
               or aliases_json ? %s
            order by id
            limit 1
            """,
            (identifier, identifier, identifier),
        )
    return cursor.fetchone()


def _resolve_entity_id(cursor, identifier: str) -> int | None:
    row = _fetch_entity_row(cursor, identifier)
    if row is None:
        return None
    return row[0]


def _relations_for(cursor, subject_type: str, subject_id: int) -> list[RelationSummary]:
    cursor.execute(
        """
        select id, subject_type, subject_id, predicate, object_type, object_id, confidence
        from relations
        where subject_type = %s
          and subject_id = %s
        order by id
        """,
        (subject_type, subject_id),
    )
    return [_relation_summary(row) for row in cursor.fetchall()]


def _relations_touching(cursor, object_type: str, object_id: int) -> list[RelationSummary]:
    cursor.execute(
        """
        select id, subject_type, subject_id, predicate, object_type, object_id, confidence
        from relations
        where (subject_type = %s and subject_id = %s)
           or (object_type = %s and object_id = %s)
        order by id
        """,
        (object_type, object_id, object_type, object_id),
    )
    return [_relation_summary(row) for row in cursor.fetchall()]


def _validate_limit(limit: int) -> None:
    if limit <= 0:
        raise ValueError("limit must be positive")


def _entity_summary(row) -> EntitySummary:
    return EntitySummary(
        id=row[0],
        name=row[1],
        entity_type=row[2],
        status=row[3],
        claim_count=row[4],
        event_count=row[5],
    )


def _claim_summary(row) -> ClaimSummary:
    return ClaimSummary(
        id=row[0],
        text=row[1],
        claim_type=row[2],
        origin=row[3],
        status=row[4],
        confidence=row[5],
    )


def _event_summary(row) -> EventSummary:
    return EventSummary(
        id=row[0],
        event_type=row[1],
        title=row[2],
        occurred_at=row[3],
        confidence=row[4],
    )


def _task_summary(row) -> TaskSummary:
    return TaskSummary(
        id=row[0],
        task_type=row[1],
        title=row[2],
        status=row[3],
        priority=row[4],
        next_run_at=row[5],
    )


def _relation_summary(row) -> RelationSummary:
    return RelationSummary(
        id=row[0],
        subject_type=row[1],
        subject_id=row[2],
        predicate=row[3],
        object_type=row[4],
        object_id=row[5],
        confidence=row[6],
    )
