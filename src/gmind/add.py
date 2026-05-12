"""Add pages to the knowledge base."""

from __future__ import annotations

import sys

import typer

from gmind import config, db, embed, utils
from gmind.utils import notify_macos

SIMILARITY_THRESHOLD = 0.92


def add_page(
    content: str,
    *,
    page_type: str = "note",
    title: str | None = None,
    slug: str | None = None,
    source: str | None = None,
    on_duplicate: str | None = None,
    state: str | None = None,
    auto_extract: bool = True,
) -> None:
    """Add a page. State defaults to 'raw' for capture/source, 'processed' otherwise."""
    if state is None:
        state = "raw" if page_type in ("capture", "source") else "processed"
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    page_title = title or content[:50]
    page_slug = slug or utils.slugify(page_title)
    checksum = utils.make_checksum(content)

    # 1. Generate embedding
    vectors = embed.embed_texts([content], cfg)
    vector = [float(v) for v in vectors[0]]

    with db.get_conn() as conn:
        # 2. Check for duplicates via vector similarity
        row = conn.execute(
            """
            SELECT slug, title, content,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM pages
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT 1
            """,
            (vector, vector),
        ).fetchone()

        if row and row[3] > SIMILARITY_THRESHOLD:
            typer.echo(
                f"⚠️  Similar page found: [[{row[0]}]] "
                f'(similarity: {row[3]:.3f}, title: "{row[1]}")'
            )
            if on_duplicate is not None:
                action = on_duplicate
            elif sys.stdin.isatty():
                action = typer.prompt(
                    "Action: [a]ppend / [o]verwrite / [i]gnore", default="a"
                )
            else:
                action = "a"
            if action.lower() == "a":
                new_content = row[2] + f"\n\n## Updates\n\n{content}"
                new_checksum = utils.make_checksum(new_content)
                conn.execute(
                    """
                    UPDATE pages
                    SET content = %s,
                        checksum = %s,
                        version = version + 1,
                        updated_at = now(),
                        updated_by = %s
                    WHERE slug = %s
                    """,
                    (new_content, new_checksum, cfg.node_name, row[0]),
                )
                typer.echo(f"✅ Appended to [[{row[0]}]]")
                return
            elif action.lower() == "o":
                conn.execute(
                    """
                    UPDATE pages
                    SET content = %s,
                        title = %s,
                        checksum = %s,
                        embedding = %s::vector,
                        version = version + 1,
                        updated_at = now(),
                        updated_by = %s
                    WHERE slug = %s
                    """,
                    (content, page_title, checksum, vector, cfg.node_name, row[0]),
                )
                typer.echo(f"✅ Overwritten [[{row[0]}]]")
                return
            else:
                typer.echo("❌ Ignored.")
                return

        # 3. Insert new page
        conn.execute(
            """
            INSERT INTO pages (slug, title, content, page_type, checksum,
                               embedding, origin_node, status, state,
                               sources, created_by, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s::vector, %s, 'draft', %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                content = EXCLUDED.content,
                title = EXCLUDED.title,
                page_type = EXCLUDED.page_type,
                checksum = EXCLUDED.checksum,
                embedding = EXCLUDED.embedding,
                state = EXCLUDED.state,
                version = pages.version + 1,
                updated_at = now(),
                updated_by = EXCLUDED.updated_by
            WHERE pages.checksum != EXCLUDED.checksum
              AND pages.status != 'merge_review'
            """,
            (
                page_slug,
                page_title,
                content,
                page_type,
                checksum,
                vector,
                cfg.node_name,
                state,
                [source] if source else [],
                cfg.node_name,
                cfg.node_name,
            ),
        )
        typer.echo(f"✅ Saved as [[{page_slug}]]")
        notify_macos("🧠 GMind", f"笔记已保存：{page_title}")

        # Auto-extract entities and relations via LLM
        if auto_extract:
            from gmind import enrich as enrich_mod
            from gmind.llm import engine as llm_engine_mod

            llm_cfg = cfg.llm
            if llm_cfg and llm_cfg.get("provider"):
                engine = llm_engine_mod.load_llm_engine(llm_cfg)
                if engine and engine.is_available():
                    try:
                        enrich_mod.enrich_page(page_slug, engine=engine, cfg=cfg)
                    except Exception as exc:
                        typer.echo(f"⚠️  Auto-extract failed: {exc}")
                else:
                    typer.echo("⚠️  LLM not available, skipping auto-extract")
            else:
                typer.echo("⚠️  LLM not configured, skipping auto-extract")
