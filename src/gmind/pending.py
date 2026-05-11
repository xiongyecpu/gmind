"""List pending (unprocessed) raw materials."""

from __future__ import annotations

import json

import typer

from gmind import config, db


def run_pending(
    *,
    limit: int = 1,
    offset: int = 0,
    json_output: bool = False,
    count_only: bool = False,
) -> None:
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    with db.get_conn() as conn:
        if count_only:
            row = conn.execute(
                """
                SELECT COUNT(*) FROM pages
                WHERE state = 'raw' AND page_type IN ('capture', 'source')
                """
            ).fetchone()
            print(row[0])
            return

        rows = conn.execute(
            """
            SELECT slug, title, content, page_type, sources, created_at
            FROM pages
            WHERE state = 'raw' AND page_type IN ('capture', 'source')
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        ).fetchall()

        if json_output:
            results = [
                {
                    "slug": r[0],
                    "title": r[1],
                    "content": r[2],
                    "type": r[3],
                    "sources": r[4],
                    "created_at": r[5].isoformat() if r[5] else None,
                }
                for r in rows
            ]
            typer.echo(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            typer.echo(f"Pending raw materials: {len(rows)}\n")
            for r in rows:
                typer.echo(f"[[{r[0]}]] {r[1]} ({r[3]}, {r[5]})")
