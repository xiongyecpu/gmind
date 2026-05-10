"""Knowledge graph operations: link extraction, graph queries."""

from __future__ import annotations

import re

import typer

from gmind import config, db

LINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def run_graph(
    slug: str | None = None,
    *,
    depth: int = 1,
    orphans: bool = False,
    hubs: bool = False,
) -> None:
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    if orphans:
        _list_orphans()
        return
    if hubs:
        _list_hubs()
        return
    if slug is None:
        typer.echo("Provide a slug or use --orphans / --hubs")
        raise typer.Exit(1)

    _show_graph(slug, depth=depth)


def _show_graph(slug: str, depth: int) -> None:
    with db.get_conn() as conn:
        page = conn.execute(
            "SELECT id, title, content FROM pages WHERE slug = %s", (slug,)
        ).fetchone()
        if page is None:
            typer.echo(f"Page [[{slug}]] not found.")
            raise typer.Exit(1)

        page_id, title, content = page
        typer.echo(f"\n🔗 Graph for [[{slug}]] {title}\n")

        # Direct links from content
        local_links = LINK_PATTERN.findall(content)
        if local_links:
            typer.echo("Linked from content:")
            for ls in set(local_links):
                typer.echo(f"  → [[{ls}]]")
            typer.echo("")

        # Edges from database
        edges = conn.execute(
            """
            SELECT e.link_type, e.to_slug, p.title
            FROM edges e
            JOIN pages p ON p.slug = e.to_slug
            WHERE e.from_slug = %s
            UNION
            SELECT e.link_type, e.from_slug, p.title
            FROM edges e
            JOIN pages p ON p.slug = e.from_slug
            WHERE e.to_slug = %s
            """,
            (slug, slug),
        ).fetchall()

        if edges:
            typer.echo("Graph edges:")
            for link_type, other_slug, other_title in edges:
                typer.echo(f"  {link_type}: [[{other_slug}]] {other_title}")
        else:
            typer.echo("No graph edges yet. Run `gmind graph --rebuild` to extract links.")

        # Depth 2: neighbors of neighbors
        if depth >= 2:
            typer.echo("\nDepth 2 neighbors:")
            for _, other_slug, _ in edges:
                sub = conn.execute(
                    """
                    SELECT e.to_slug, p.title
                    FROM edges e
                    JOIN pages p ON p.slug = e.to_slug
                    WHERE e.from_slug = %s AND e.to_slug != %s
                    """,
                    (other_slug, slug),
                ).fetchall()
                for sub_slug, sub_title in sub:
                    typer.echo(f"  [[{other_slug}]] → [[{sub_slug}]] {sub_title}")


def _list_orphans() -> None:
    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT slug, title, page_type
            FROM pages p
            WHERE NOT EXISTS (
                SELECT 1 FROM edges e
                WHERE e.from_page = p.id OR e.to_page = p.id
            )
            ORDER BY updated_at DESC
            """
        ).fetchall()

    if not rows:
        typer.echo("No orphan pages found.")
        return

    typer.echo(f"\n🌑 {len(rows)} orphan page(s):\n")
    for slug, title, page_type in rows:
        typer.echo(f"  [[{slug}]] {title} ({page_type})")


def _list_hubs() -> None:
    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT p.slug, p.title, COUNT(*) AS degree
            FROM pages p
            JOIN edges e ON e.from_page = p.id OR e.to_page = p.id
            GROUP BY p.id, p.slug, p.title
            ORDER BY degree DESC
            LIMIT 10
            """
        ).fetchall()

    if not rows:
        typer.echo("No hubs found.")
        return

    typer.echo("\n🌟 Top hub pages:\n")
    for slug, title, degree in rows:
        typer.echo(f"  [[{slug}]] {title} — {degree} connections")


def run_rebuild() -> None:
    """Scan all pages and rebuild edges from [[link]] syntax."""
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    with db.get_conn() as conn:
        pages = conn.execute(
            "SELECT id, slug, content FROM pages"
        ).fetchall()

        created = 0
        for page_id, slug, content in pages:
            links = LINK_PATTERN.findall(content)
            for target_slug in set(links):
                # Skip self-links
                if target_slug == slug:
                    continue
                # Ensure target exists
                target = conn.execute(
                    "SELECT id FROM pages WHERE slug = %s", (target_slug,)
                ).fetchone()
                if target is None:
                    continue

                target_id = target[0]
                conn.execute(
                    """
                    INSERT INTO edges (from_page, to_page, from_slug, to_slug, link_type)
                    VALUES (%s, %s, %s, %s, 'related')
                    ON CONFLICT (from_page, to_page, link_type) DO NOTHING
                    """,
                    (page_id, target_id, slug, target_slug),
                )
                created += 1

        typer.echo(f"Graph rebuilt: {created} edge(s) created/updated.")
