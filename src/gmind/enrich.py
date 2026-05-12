"""Knowledge enrichment: auto-extract entities, relations, summary, tags."""

from __future__ import annotations

import json

import typer

from gmind import config, db
from gmind.llm import engine as llm_engine
from gmind.llm import extract as llm_extract


def enrich_page(
    slug: str,
    engine: llm_engine.LLMEngine | None = None,
    cfg: config.Config | None = None,
) -> dict:
    """Enrich a single page with LLM-extracted metadata."""
    if cfg is None:
        cfg = config.load_config()
    db.init_pool(cfg.database_url)

    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id, title, content, page_type FROM pages WHERE slug = %s",
            (slug,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Page [[{slug}]] not found.")

        page_id, title, content, page_type = row

    # Initialize engine if not provided
    if engine is None:
        llm_cfg = cfg.llm
        if not llm_cfg or not llm_cfg.get("provider"):
            raise RuntimeError("LLM not configured")
        engine = llm_engine.load_llm_engine(llm_cfg)
        if engine is None or not engine.is_available():
            raise RuntimeError("LLM provider not available")

    typer.echo(f"🔬 Enriching [[{slug}]] ...")

    # 1. Extract entities
    entities = llm_extract.extract_entities(content, engine)
    typer.echo(f"   Found {len(entities)} entities")

    # 2. Extract relations
    entity_names = [e.get("name", "") for e in entities if e.get("name")]
    relations = llm_extract.extract_relations(content, entity_names, engine) if entity_names else []
    typer.echo(f"   Found {len(relations)} relations")

    # 3. Summarize & tag
    summary_data = llm_extract.auto_summarize(content, engine)
    typer.echo(f"   Summary: {summary_data.get('summary', '')[:60]}...")

    # 4. Persist to database
    with db.get_conn() as conn:
        conn.execute(
            """
            UPDATE pages
            SET summary = %s,
                tags = %s,
                entities = %s,
                llm_enriched = TRUE,
                updated_at = now()
            WHERE slug = %s
            """,
            (
                summary_data.get("summary", ""),
                summary_data.get("tags", []),
                json.dumps(entities),
                slug,
            ),
        )

        # 5. Create entity pages and edges
        for entity in entities:
            name = entity.get("name", "")
            etype = entity.get("type", "other")
            description = entity.get("description", "")
            if not name:
                continue

            entity_slug = _slugify_entity(name)

            # Upsert entity page
            conn.execute(
                """
                INSERT INTO pages (slug, title, content, page_type, checksum,
                                   origin_node, status, state, auto_extracted,
                                   created_by, updated_by)
                VALUES (%s, %s, %s, 'entity', %s, %s, 'draft', 'processed', TRUE,
                        %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    content = EXCLUDED.content,
                    updated_at = now(),
                    updated_by = EXCLUDED.updated_by
                WHERE pages.checksum != EXCLUDED.checksum
                """,
                (
                    entity_slug,
                    name,
                    f"Type: {etype}\n\n{description}",
                    f"entity-{entity_slug}-{description}",  # simple checksum
                    cfg.node_name,
                    cfg.node_name,
                    cfg.node_name,
                ),
            )

            # Create edge from original page to entity
            entity_row = conn.execute(
                "SELECT id FROM pages WHERE slug = %s", (entity_slug,)
            ).fetchone()
            if entity_row:
                conn.execute(
                    """
                    INSERT INTO edges (from_page, to_page, from_slug, to_slug, link_type, source)
                    VALUES (%s, %s, %s, %s, 'mentions', 'llm_extract')
                    ON CONFLICT (from_page, to_page, link_type) DO NOTHING
                    """,
                    (page_id, entity_row[0], slug, entity_slug),
                )

        # 6. Create edges from extracted relations
        for rel in relations:
            from_name = rel.get("from", "")
            to_name = rel.get("to", "")
            rel_type = rel.get("relation", "related")
            if not from_name or not to_name:
                continue

            from_slug = _slugify_entity(from_name)
            to_slug = _slugify_entity(to_name)

            from_row = conn.execute(
                "SELECT id FROM pages WHERE slug = %s", (from_slug,)
            ).fetchone()
            to_row = conn.execute(
                "SELECT id FROM pages WHERE slug = %s", (to_slug,)
            ).fetchone()

            if from_row and to_row:
                conn.execute(
                    """
                    INSERT INTO edges (from_page, to_page, from_slug, to_slug, link_type, source)
                    VALUES (%s, %s, %s, %s, %s, 'llm_extract')
                    ON CONFLICT (from_page, to_page, link_type) DO NOTHING
                    """,
                    (from_row[0], to_row[0], from_slug, to_slug, rel_type),
                )

    return {
        "slug": slug,
        "entities": entities,
        "relations": relations,
        "summary": summary_data.get("summary", ""),
        "tags": summary_data.get("tags", []),
        "key_points": summary_data.get("key_points", []),
    }


def _slugify_entity(name: str) -> str:
    """Convert entity name to a slug-safe string."""
    from gmind import utils
    return utils.slugify(name)


def run_enrich(slug: str) -> None:
    """CLI entry point for enrich command."""
    cfg = config.load_config()
    result = enrich_page(slug, cfg=cfg)
    typer.echo(f"\n✅ Enriched [[{result['slug']}]]")
    typer.echo(f"   Tags: {', '.join(result['tags'])}")
    typer.echo(f"   Entities: {', '.join(e.get('name', '') for e in result['entities'])}")
    notify_macos("🧠 GMind", f"知识增强完成：{result['slug']}")


def run_enrich_all() -> None:
    """Enrich all pages that haven't been LLM-enriched yet."""
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    llm_cfg = cfg.llm
    if not llm_cfg or not llm_cfg.get("provider"):
        typer.echo("❌ LLM not configured. Add [llm] section to ~/.gmind/config.toml")
        raise typer.Exit(1)

    engine = llm_engine.load_llm_engine(llm_cfg)
    if engine is None or not engine.is_available():
        typer.echo("❌ LLM provider not available")
        raise typer.Exit(1)

    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT slug, title
            FROM pages
            WHERE llm_enriched = FALSE OR llm_enriched IS NULL
            ORDER BY updated_at DESC
            """
        ).fetchall()

    if not rows:
        typer.echo("✅ All pages are already enriched.")
        return

    typer.echo(f"🔬 Found {len(rows)} page(s) to enrich\n")
    success = 0
    failed = 0

    for slug, title in rows:
        try:
            result = enrich_page(slug, engine=engine, cfg=cfg)
            typer.echo(f"  ✅ [[{slug}]] — {len(result['entities'])} entities, {len(result['relations'])} relations")
            success += 1
        except Exception as exc:
            typer.echo(f"  ❌ [[{slug}]] — {exc}")
            failed += 1

    typer.echo(f"\nDone: {success} enriched, {failed} failed")
    notify_macos("🧠 GMind", f"批量知识增强完成：{success} 个笔记")
