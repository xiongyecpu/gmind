"""Manual merge and conflict resolution."""

from __future__ import annotations

import typer

from gmind import config, db


def run_manual_merge(
    slug: str,
    *,
    list_versions: bool = False,
    pick_version: int | None = None,
    edit: bool = False,
    revert_version: int | None = None,
) -> None:
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    with db.get_conn() as conn:
        page = conn.execute(
            "SELECT id, content, status FROM pages WHERE slug = %s",
            (slug,),
        ).fetchone()
        if page is None:
            typer.echo(f"Page [[{slug}]] not found.")
            raise typer.Exit(1)

        page_id, current_content, status = page

        if list_versions:
            rows = conn.execute(
                """
                SELECT version, action, created_at, created_by
                FROM page_history
                WHERE page_id = %s
                ORDER BY version DESC, created_at DESC
                """,
                (page_id,),
            ).fetchall()
            if not rows:
                typer.echo("No history found.")
                return
            typer.echo(f"History for [[{slug}]]:")
            for ver, action, ts, by in rows:
                typer.echo(f"  version {ver} ({action}, {by}, {ts})")
            return

        if pick_version is not None:
            hist = conn.execute(
                "SELECT snapshot->>'content' FROM page_history WHERE page_id = %s AND version = %s",
                (page_id, pick_version),
            ).fetchone()
            if hist is None:
                typer.echo(f"Version {pick_version} not found.")
                raise typer.Exit(1)
            conn.execute(
                """
                UPDATE pages
                SET content = %s,
                    status = 'published',
                    version = version + 1,
                    updated_at = now(),
                    updated_by = %s
                WHERE id = %s
                """,
                (hist[0], cfg.node_name, page_id),
            )
            _save_snapshot(conn, page_id, cfg.node_name)
            typer.echo(f"✅ Reverted [[{slug}]] to version {pick_version}")
            return

        if edit:
            # Simple editor fallback: dump to temp file and open
            import os
            import subprocess
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w+", suffix=".md", delete=False) as f:
                f.write(current_content)
                tmp = f.name

            editor = os.environ.get("EDITOR", "vim")
            subprocess.call([editor, tmp])

            with open(tmp) as f:
                new_content = f.read()
            os.unlink(tmp)

            conn.execute(
                """
                UPDATE pages
                SET content = %s,
                    status = 'published',
                    version = version + 1,
                    updated_at = now(),
                    updated_by = %s
                WHERE id = %s
                """,
                (new_content, cfg.node_name, page_id),
            )
            _save_snapshot(conn, page_id, cfg.node_name)
            typer.echo(f"✅ Edited and published [[{slug}]]")
            return

        typer.echo(f"Current status: {status}")
        typer.echo("Use --list, --pick, or --edit")


def _save_snapshot(conn, page_id, created_by) -> None:
    conn.execute(
        """
        INSERT INTO page_history (page_id, version, snapshot, checksum, action, created_by)
        SELECT id, version, to_jsonb(pages.*), checksum, 'manual_resolve', %s
        FROM pages WHERE id = %s
        """,
        (created_by, page_id),
    )
