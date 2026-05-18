from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files

import psycopg


SCHEMA_RESOURCE = "schema.sql"
REQUIRED_TABLES = [
    "sources",
    "source_chunks",
    "entities",
    "claims",
    "events",
    "relations",
    "tasks",
    "logs",
]
REQUIRED_VIEWS = [
    "entity_claims_view",
    "claim_current_view",
    "claim_conflict_view",
    "claim_lineage_view",
]


@dataclass(frozen=True)
class DatabaseCheck:
    vector_extension: bool
    tables: list[str]
    views: list[str]

    @property
    def missing_tables(self) -> list[str]:
        return [table for table in REQUIRED_TABLES if table not in self.tables]

    @property
    def missing_views(self) -> list[str]:
        return [view for view in REQUIRED_VIEWS if view not in self.views]

    @property
    def ok(self) -> bool:
        return (
            self.vector_extension
            and not self.missing_tables
            and not self.missing_views
        )


def load_schema_sql() -> str:
    return files("gmind").joinpath(SCHEMA_RESOURCE).read_text(encoding="utf-8")


def init_database(database_url: str) -> None:
    schema_sql = load_schema_sql()

    with psycopg.connect(database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_sql)


def check_database(database_url: str) -> DatabaseCheck:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "select exists(select 1 from pg_extension where extname = 'vector')"
            )
            vector_extension = bool(cursor.fetchone()[0])

            cursor.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = 'public'
                  and table_type = 'BASE TABLE'
                order by table_name
                """
            )
            tables = [row[0] for row in cursor.fetchall()]

            cursor.execute(
                """
                select table_name
                from information_schema.views
                where table_schema = 'public'
                order by table_name
                """
            )
            views = [row[0] for row in cursor.fetchall()]

    return DatabaseCheck(
        vector_extension=vector_extension,
        tables=tables,
        views=views,
    )
