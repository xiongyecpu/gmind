"""Pure vector search (no LLM). JSON output for agent consumption."""

from __future__ import annotations

import json

import typer

from gmind import config, db, embed


def run_search(
    keyword: str,
    *,
    top_k: int = 5,
    json_output: bool = False,
) -> None:
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    vectors = embed.embed_texts([keyword], cfg)
    vector = vectors[0]

    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT slug, title, content, page_type,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM pages
            WHERE (
                status IN ('published', 'merge_review')
                OR (status = 'draft' AND origin_node = %s)
            )
              AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vector, cfg.node_name, vector, top_k),
        ).fetchall()

    results = [
        {
            "slug": slug,
            "title": title,
            "content": content,
            "type": page_type,
            "similarity": round(float(similarity), 4),
        }
        for slug, title, content, page_type, similarity in rows
    ]

    if json_output:
        typer.echo(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        if not rows:
            typer.echo("No results.")
            return
        typer.echo(f"Top {len(rows)} results:\n")
        for r in results:
            typer.echo(
                f"[[{r['slug']}]] {r['title']} ({r['type']}, sim={r['similarity']})"
            )
            # Truncate long content
            content = r["content"]
            if len(content) > 300:
                content = content[:300] + "..."
            typer.echo(f"  {content}\n")
