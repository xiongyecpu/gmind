create extension if not exists vector;

create table if not exists sources (
    id bigserial primary key,
    title text not null,
    source_type text not null,
    url text,
    author text,
    published_at timestamptz,
    captured_at timestamptz,
    raw_text text,
    trust_score double precision,
    metadata_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists source_chunks (
    id bigserial primary key,
    source_id bigint not null references sources(id) on delete cascade,
    chunk_index integer not null,
    chunk_text text not null,
    embedding_model text,
    embedding_dim integer,
    embedding vector(1536),
    metadata_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (source_id, chunk_index)
);

create table if not exists entities (
    id bigserial primary key,
    name text not null,
    entity_type text not null,
    description text,
    canonical_name text,
    aliases_json jsonb not null default '[]'::jsonb,
    status text not null default 'active',
    dedupe_key text,
    external_ids_json jsonb not null default '{}'::jsonb,
    merge_status text not null default 'canonical',
    merged_into_entity_id bigint references entities(id),
    metadata_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists claims (
    id bigserial primary key,
    text text not null,
    claim_type text not null,
    origin text not null,
    status text not null default 'active',
    confidence double precision,
    as_of timestamptz,
    valid_from timestamptz,
    valid_to timestamptz,
    source_id bigint references sources(id),
    source_chunk_id bigint references source_chunks(id),
    metadata_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists events (
    id bigserial primary key,
    event_type text not null,
    title text not null,
    description text,
    occurred_at timestamptz,
    occurred_at_precision text,
    subject_entity_id bigint references entities(id),
    object_entity_id bigint references entities(id),
    related_entity_id bigint references entities(id),
    source_id bigint references sources(id),
    source_chunk_id bigint references source_chunks(id),
    confidence double precision,
    metadata_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists relations (
    id bigserial primary key,
    subject_type text not null,
    subject_id bigint not null,
    predicate text not null,
    object_type text not null,
    object_id bigint not null,
    source_id bigint references sources(id),
    confidence double precision,
    metadata_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (subject_type, subject_id, predicate, object_type, object_id)
);

create table if not exists tasks (
    id bigserial primary key,
    task_type text not null,
    title text not null,
    description text,
    status text not null default 'open',
    priority integer not null default 0,
    related_entity_id bigint references entities(id),
    source_id bigint references sources(id),
    claim_id bigint references claims(id),
    event_id bigint references events(id),
    scheduled_at timestamptz,
    next_run_at timestamptz,
    locked_at timestamptz,
    locked_by text,
    attempt_count integer not null default 0,
    last_error text,
    metadata_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    due_at timestamptz,
    completed_at timestamptz
);

create table if not exists logs (
    id bigserial primary key,
    action text not null,
    title text not null,
    summary text,
    actor text,
    object_type text,
    object_id bigint,
    metadata_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_source_chunks_source_id
    on source_chunks(source_id);

create index if not exists idx_source_chunks_embedding_hnsw
    on source_chunks using hnsw (embedding vector_cosine_ops)
    where embedding is not null;

create index if not exists idx_entities_canonical_name
    on entities(canonical_name);

create index if not exists idx_entities_dedupe_key
    on entities(dedupe_key);

create index if not exists idx_claims_status_origin_type
    on claims(status, origin, claim_type);

create index if not exists idx_claims_source_chunk_id
    on claims(source_chunk_id);

create index if not exists idx_events_related_entity_time
    on events(related_entity_id, occurred_at);

create index if not exists idx_events_occurred_at
    on events(occurred_at);

create index if not exists idx_relations_subject
    on relations(subject_type, subject_id);

create index if not exists idx_relations_object
    on relations(object_type, object_id);

create index if not exists idx_relations_predicate
    on relations(predicate);

create index if not exists idx_tasks_status_schedule
    on tasks(status, next_run_at, priority desc, created_at);

create or replace view entity_claims_view as
select
    r.object_id as entity_id,
    r.predicate,
    c.*
from relations r
join claims c on c.id = r.subject_id
where r.subject_type = 'claim'
  and r.object_type = 'entity'
  and r.predicate in ('about', 'mentions');

create or replace view claim_current_view as
select *
from claims
where status in ('active', 'disputed', 'stale');

create or replace view claim_conflict_view as
select
    r.id as relation_id,
    left_claim.id as left_claim_id,
    left_claim.text as left_claim_text,
    left_claim.status as left_claim_status,
    right_claim.id as right_claim_id,
    right_claim.text as right_claim_text,
    right_claim.status as right_claim_status,
    r.confidence,
    r.created_at
from relations r
join claims left_claim on left_claim.id = r.subject_id
join claims right_claim on right_claim.id = r.object_id
where r.subject_type = 'claim'
  and r.object_type = 'claim'
  and r.predicate = 'contradicts';

create or replace view claim_lineage_view as
select
    r.subject_id as claim_id,
    r.predicate,
    r.object_type,
    r.object_id,
    r.source_id,
    r.confidence,
    r.created_at
from relations r
where r.subject_type = 'claim'
  and r.predicate in ('supported_by', 'derived_from', 'contradicts', 'supersedes');
