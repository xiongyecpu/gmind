"""Knowledge base statistics dashboard."""

from __future__ import annotations

import typer

from gmind import config, db


def run_stats() -> None:
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    with db.get_conn() as conn:
        # Total pages
        total = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]

        # By type
        type_rows = conn.execute(
            "SELECT page_type, COUNT(*) FROM pages GROUP BY page_type ORDER BY COUNT(*) DESC"
        ).fetchall()

        # Embedding coverage
        embedded = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE embedding IS NOT NULL"
        ).fetchone()[0]

        # Orphan pages (no edges)
        orphans = conn.execute(
            """
            SELECT COUNT(*) FROM pages p
            WHERE NOT EXISTS (
                SELECT 1 FROM edges e WHERE e.from_page = p.id OR e.to_page = p.id
            )
            """
        ).fetchone()[0]

        # Edges count
        edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

        # Recent 7 days
        recent = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE created_at > now() - interval '7 days'"
        ).fetchone()[0]

        # Last sync
        last_sync = conn.execute(
            "SELECT MAX(created_at) FROM sync_log WHERE action IN ('push', 'merge')"
        ).fetchone()[0]

        # Pending merges
        pending = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE status = 'merge_review'"
        ).fetchone()[0]

    # Output
    typer.echo("")
    typer.echo("📊 GMind 知识库概览")
    typer.echo("")
    typer.echo(f"页面总数:        {total}")
    for pt, count in type_rows:
        typer.echo(f"├── {pt}:{' ' * (12 - len(pt))}{count}")
    typer.echo("")
    cov = f"{embedded / total * 100:.1f}% ({embedded}/{total})" if total else "N/A"
    typer.echo(f"向量覆盖率:      {cov}")
    orphan_pct = f"({orphans / total * 100:.1f}%)" if total else ""
    typer.echo(f"孤立页面:        {orphans} {orphan_pct}")
    typer.echo(f"图谱关系:        {edges} 条")
    typer.echo("")
    typer.echo(f"最近 7 天写入:    {recent} 页")
    if last_sync:
        typer.echo(f"最近一次 sync:    {last_sync}")
    typer.echo(f"待确认合并:       {pending} 页")
    typer.echo("")
