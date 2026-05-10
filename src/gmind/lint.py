"""Health check and diagnostics."""

from __future__ import annotations

import re

import typer

from gmind import config, db

LINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def run_lint() -> None:
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    issues: list[tuple[str, str]] = []

    with db.get_conn() as conn:
        # 1. Orphan pages
        orphans = conn.execute(
            """
            SELECT slug FROM pages p
            WHERE NOT EXISTS (
                SELECT 1 FROM edges e
                WHERE e.from_page = p.id OR e.to_page = p.id
            )
            """
        ).fetchall()
        for (slug,) in orphans:
            issues.append(("orphan", slug))

        # 2. Broken links
        pages = conn.execute("SELECT slug, content FROM pages").fetchall()
        all_slugs = {row[0] for row in conn.execute("SELECT slug FROM pages").fetchall()}
        for slug, content in pages:
            for target in LINK_PATTERN.findall(content):
                if target not in all_slugs:
                    issues.append(("broken-link", f"[[{target}]] in [[{slug}]]"))

        # 3. Pending merges
        pending = conn.execute(
            "SELECT slug FROM pages WHERE status = 'merge_review'"
        ).fetchall()
        for (slug,) in pending:
            issues.append(("merge-review", slug))

        # 4. Missing embeddings
        no_embed = conn.execute(
            "SELECT slug FROM pages WHERE embedding IS NULL"
        ).fetchall()
        for (slug,) in no_embed:
            issues.append(("no-embedding", slug))

    if not issues:
        typer.echo("✅ All checks passed. No issues found.")
        return

    typer.echo(f"\n⚠️  Found {len(issues)} issue(s):\n")
    for kind, detail in issues:
        typer.echo(f"  [{kind}] {detail}")
    typer.echo("")
