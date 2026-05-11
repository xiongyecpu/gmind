"""Database connection and schema management."""

from __future__ import annotations

import atexit
from contextlib import contextmanager
from typing import TYPE_CHECKING

import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

if TYPE_CHECKING:

    pass


_pool: ConnectionPool | None = None
_pool_url: str | None = None

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pages (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          TEXT UNIQUE NOT NULL,
    title         TEXT NOT NULL,
    aliases       TEXT[] DEFAULT '{}',
    content       TEXT NOT NULL,
    page_type     TEXT NOT NULL DEFAULT 'note',
    frontmatter   JSONB DEFAULT '{}',
    sources       TEXT[] DEFAULT '{}',
    tags          TEXT[] DEFAULT '{}',
    embedding     vector(1024),
    origin_node   TEXT NOT NULL DEFAULT 'default',
    status        TEXT NOT NULL DEFAULT 'draft',
    state         TEXT DEFAULT 'processed',
    checksum      TEXT NOT NULL,
    version       INTEGER DEFAULT 1,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now(),
    created_by    TEXT,
    updated_by    TEXT
);

CREATE INDEX IF NOT EXISTS idx_pages_embedding ON pages
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);
CREATE INDEX IF NOT EXISTS idx_pages_node ON pages(origin_node);
CREATE INDEX IF NOT EXISTS idx_pages_type ON pages(page_type);
CREATE INDEX IF NOT EXISTS idx_pages_state ON pages(state);
CREATE INDEX IF NOT EXISTS idx_pages_tags ON pages USING gin(tags);

CREATE TABLE IF NOT EXISTS page_history (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id     UUID REFERENCES pages(id),
    version     INTEGER NOT NULL,
    snapshot    JSONB NOT NULL,
    checksum    TEXT NOT NULL,
    action      TEXT DEFAULT 'update',
    created_at  TIMESTAMPTZ DEFAULT now(),
    created_by  TEXT
);

CREATE TABLE IF NOT EXISTS edges (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_page   UUID REFERENCES pages(id) ON DELETE CASCADE,
    to_page     UUID REFERENCES pages(id) ON DELETE CASCADE,
    from_slug   TEXT NOT NULL,
    to_slug     TEXT NOT NULL,
    link_type   TEXT NOT NULL DEFAULT 'related',
    weight      REAL DEFAULT 1.0,
    confidence  REAL,
    evidence    TEXT,
    created_by  TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(from_page, to_page, link_type)
);

CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_page);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_page);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(link_type);

CREATE TABLE IF NOT EXISTS sync_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id  TEXT NOT NULL,
    node        TEXT NOT NULL,
    action      TEXT NOT NULL,
    slug        TEXT,
    detail      JSONB,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sync_log_request ON sync_log(request_id, slug);
"""


def init_pool(database_url: str) -> None:
    global _pool, _pool_url
    if _pool is not None and _pool_url == database_url:
        return
    if _pool is not None:
        _pool.close()
    _pool = ConnectionPool(
        conninfo=database_url,
        min_size=1,
        max_size=10,
    )
    _pool_url = database_url
    atexit.register(close_pool)


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_conn():
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    with _pool.connection() as conn:
        register_vector(conn)
        yield conn


def init_db(database_url: str) -> None:
    """Create extensions and tables."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        register_vector(conn)
        conn.execute(SCHEMA_SQL)
