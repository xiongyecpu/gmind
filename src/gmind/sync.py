"""Synchronize drafts to published state with conflict detection."""

from __future__ import annotations

import uuid

import typer

from gmind import config, db


def run_sync(*, dry_run: bool = False) -> None:
    cfg = config.load_config()
    db.init_pool(cfg.database_url)
    request_id = str(uuid.uuid4())

    with db.get_conn() as conn:
        drafts = conn.execute(
            """
            SELECT id, slug, title, content, page_type, checksum,
                   frontmatter, sources, tags, embedding, version,
                   created_at, updated_at, created_by, updated_by
            FROM pages
            WHERE status = 'draft' AND origin_node = %s
            """,
            (cfg.node_name,),
        ).fetchall()

        if not drafts:
            typer.echo("No local drafts to sync.")
            return

        published_count = 0
        conflict_count = 0

        for draft in drafts:
            (
                draft_id,
                slug,
                title,
                content,
                page_type,
                checksum,
                frontmatter,
                sources,
                tags,
                embedding,
                version,
                created_at,
                updated_at,
                created_by,
                updated_by,
            ) = draft

            pub = conn.execute(
                "SELECT id, content, checksum FROM pages WHERE slug = %s AND status = 'published'",
                (slug,),
            ).fetchone()

            if pub is None:
                if not dry_run:
                    conn.execute(
                        """
                        UPDATE pages
                        SET status = 'published', updated_at = now(), updated_by = %s
                        WHERE id = %s
                        """,
                        (cfg.node_name, draft_id),
                    )
                    _log_sync(conn, request_id, cfg.node_name, "push", slug)
                published_count += 1
                typer.echo(f"{'[DRY-RUN] ' if dry_run else ''}Published [[{slug}]]")

            elif pub[2] == checksum:
                if not dry_run:
                    conn.execute(
                        "UPDATE pages SET status = 'published' WHERE id = %s",
                        (draft_id,),
                    )
                published_count += 1
                typer.echo(f"{'[DRY-RUN] ' if dry_run else ''}Already in sync [[{slug}]]")

            else:
                conflict_count += 1
                typer.echo(
                    f"{'[DRY-RUN] ' if dry_run else ''}Conflict detected: [[{slug}]]"
                )

                if dry_run:
                    continue

                _save_snapshot(conn, draft_id, version, cfg.node_name)
                _save_snapshot(conn, pub[0], None, cfg.node_name)

                conn.execute(
                    "UPDATE pages SET status = 'merge_review' WHERE id = %s",
                    (draft_id,),
                )
                _log_sync(conn, request_id, cfg.node_name, "conflict", slug)

        typer.echo(
            f"\nSync complete: {published_count} published, "
            f"{conflict_count} conflicts pending merge_review"
        )


def _save_snapshot(
    conn, page_id, version, created_by, action: str = "update"
) -> None:
    conn.execute(
        """
        INSERT INTO page_history (page_id, version, snapshot, checksum, action, created_by)
        SELECT id, COALESCE(%s, version), to_jsonb(pages.*), checksum, %s, %s
        FROM pages WHERE id = %s
        """,
        (version, action, created_by, page_id),
    )


def _log_sync(conn, request_id, node, action, slug) -> None:
    conn.execute(
        """
        INSERT INTO sync_log (request_id, node, action, slug)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (request_id, slug) DO NOTHING
        """,
        (request_id, node, action, slug),
    )
