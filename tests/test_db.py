from gmind.db import DatabaseCheck, load_schema_sql


def test_schema_contains_core_tables() -> None:
    schema_sql = load_schema_sql()

    for table_name in [
        "sources",
        "source_chunks",
        "entities",
        "claims",
        "events",
        "relations",
        "tasks",
        "logs",
    ]:
        assert f"create table if not exists {table_name}" in schema_sql


def test_schema_contains_pgvector_and_read_views() -> None:
    schema_sql = load_schema_sql()

    assert "create extension if not exists vector" in schema_sql
    assert "embedding vector(1536)" in schema_sql
    assert "create or replace view entity_claims_view" in schema_sql
    assert "create or replace view claim_current_view" in schema_sql
    assert "create or replace view claim_conflict_view" in schema_sql
    assert "create or replace view claim_lineage_view" in schema_sql


def test_database_check_reports_missing_objects() -> None:
    check = DatabaseCheck(
        vector_extension=False,
        tables=["sources"],
        views=["entity_claims_view"],
    )

    assert not check.ok
    assert "claims" in check.missing_tables
    assert "claim_current_view" in check.missing_views
