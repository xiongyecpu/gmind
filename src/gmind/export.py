"""Export knowledge base to markdown files."""

from __future__ import annotations

from pathlib import Path

import typer

from gmind import config, db


def run_export(output_dir: str) -> None:
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    with db.get_conn() as conn:
        pages = conn.execute(
            """
            SELECT slug, title, content, page_type, frontmatter, tags, status,
                   origin_node, created_at, updated_at
            FROM pages
            """
        ).fetchall()

    count = 0
    for (
        slug, title, content, page_type, frontmatter,
        tags, status, origin, created, updated,
    ) in pages:
        # Build frontmatter
        fm_lines = ["---"]
        fm_lines.append(f'title: "{title}"')
        fm_lines.append(f"type: {page_type}")
        if tags:
            fm_lines.append(f"tags: {list(tags)}")
        fm_lines.append(f"status: {status}")
        fm_lines.append(f"origin: {origin}")
        if created:
            fm_lines.append(f"created: {created.isoformat()}")
        if updated:
            fm_lines.append(f"updated: {updated.isoformat()}")
        # Add any extra frontmatter from DB
        if frontmatter and isinstance(frontmatter, dict):
            for k, v in frontmatter.items():
                if k not in ("title", "type", "tags", "status", "origin", "created", "updated"):
                    fm_lines.append(f"{k}: {v}")
        fm_lines.append("---")

        full_content = "\n".join(fm_lines) + "\n\n" + content + "\n"

        # Write file
        file_path = out / f"{slug}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(full_content, encoding="utf-8")
        count += 1

    typer.echo(f"✅ Exported {count} page(s) to {out.absolute()}")
