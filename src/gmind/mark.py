"""Mark pages as processed or raw."""

from __future__ import annotations

import typer

from gmind import config, db


def run_mark(slug: str, *, state: str = "processed") -> None:
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    if state not in ("raw", "processed"):
        typer.echo("❌ State must be 'raw' or 'processed'")
        raise typer.Exit(1)

    with db.get_conn() as conn:
        cur = conn.execute(
            "UPDATE pages SET state = %s WHERE slug = %s RETURNING slug, title",
            (state, slug),
        )
        row = cur.fetchone()
        if row:
            typer.echo(f"✅ [[{row[0]}]] marked as {state}")
        else:
            typer.echo(f"❌ Page not found: [[{slug}]]")
            raise typer.Exit(1)
