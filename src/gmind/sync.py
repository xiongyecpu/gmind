"""Synchronize drafts to published state with conflict detection and LLM merge."""

from __future__ import annotations

import uuid

import typer

from gmind import config, db, llm


def run_sync(*, dry_run: bool = False, auto_merge: bool = False) -> None:
    cfg = config.load_config()
    db.init_pool(cfg.database_url)
    request_id = str(uuid.uuid4())

    with db.get_conn() as conn:
        # 1. PUBLISH phase: scan local drafts
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
        merged_count = 0

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

            # Check for published version with same slug
            pub = conn.execute(
                "SELECT id, content, checksum FROM pages WHERE slug = %s AND status = 'published'",
                (slug,),
            ).fetchone()

            if pub is None:
                # No published version → publish directly
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
                # Same checksum → already in sync, just mark published
                if not dry_run:
                    conn.execute(
                        "UPDATE pages SET status = 'published' WHERE id = %s",
                        (draft_id,),
                    )
                published_count += 1
                typer.echo(f"{'[DRY-RUN] ' if dry_run else ''}Already in sync [[{slug}]]")

            else:
                # Conflict: checksum differs
                conflict_count += 1
                typer.echo(
                    f"{'[DRY-RUN] ' if dry_run else ''}Conflict detected: [[{slug}]]"
                )

                if dry_run:
                    continue

                # Save both versions to page_history
                _save_snapshot(conn, draft_id, version, cfg.node_name)
                _save_snapshot(conn, pub[0], None, cfg.node_name)

                # Mark draft as merge_review
                conn.execute(
                    "UPDATE pages SET status = 'merge_review' WHERE id = %s",
                    (draft_id,),
                )
                _log_sync(conn, request_id, cfg.node_name, "conflict", slug)

        # 2. MERGE phase: auto-merge merge_review pages (only if --auto-merge)
        if not dry_run and auto_merge:
            if not cfg.llm_api_key:
                typer.echo("Warning: --auto-merge requires llm_api_key, skipping merge phase")
            else:
                merge_reviews = conn.execute(
                    """
                    SELECT id, slug, title, content
                    FROM pages
                    WHERE status = 'merge_review' AND origin_node = %s
                    """,
                    (cfg.node_name,),
                ).fetchall()

                for mr_id, mr_slug, mr_title, mr_content in merge_reviews:
                    pub_row = conn.execute(
                        "SELECT content FROM pages WHERE slug = %s AND status = 'published'",
                        (mr_slug,),
                    ).fetchone()
                    if pub_row is None:
                        continue

                    pub_content = pub_row[0]
                    merged = _llm_merge(mr_title, pub_content, mr_content, cfg)

                    if merged:
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
                            (merged, cfg.node_name, mr_id),
                        )
                        _save_snapshot(conn, mr_id, None, cfg.node_name, action="merge")
                        _log_sync(conn, request_id, cfg.node_name, "merge", mr_slug)
                        merged_count += 1
                        typer.echo(f"Auto-merged [[{mr_slug}]]")
                    else:
                        typer.echo(f"Merge failed for [[{mr_slug}]], kept merge_review")

        # Summary
        if auto_merge:
            typer.echo(
                f"\nSync complete: {published_count} published, "
                f"{conflict_count} conflicts, {merged_count} auto-merged"
            )
        else:
            typer.echo(
                f"\nSync complete: {published_count} published, "
                f"{conflict_count} conflicts pending merge_review"
            )


def _save_snapshot(
    conn, page_id, version, created_by, action: str = "update"
) -> None:
    """Save current page state to page_history."""
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


def _llm_merge(title: str, published: str, draft: str, cfg: config.Config) -> str | None:
    prompt = (
        f"You are a knowledge base merge assistant. Merge two versions of the same note.\n\n"
        f"Title: {title}\n\n"
        f"Published version:\n---\n{published}\n---\n\n"
        f"Draft version:\n---\n{draft}\n---\n\n"
        f"Instructions:\n"
        f"1. Preserve all unique information from both versions\n"
        f"2. Remove exact duplicates\n"
        f"3. Keep the structure clean and coherent\n"
        f"4. Output ONLY the merged content, no extra explanation\n\n"
        f"Merged content:"
    )
    try:
        return llm.chat(prompt, cfg, temperature=0.2)
    except Exception as exc:
        typer.echo(f"LLM merge error: {exc}")
        return None
