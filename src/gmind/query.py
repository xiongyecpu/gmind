"""Query the knowledge base (retrieval only, no LLM)."""

from __future__ import annotations

import typer

from gmind import config, db, embed


def run_query(question: str, top_k: int = 5) -> None:
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    vectors = embed.embed_texts([question], cfg)
    vector = vectors[0]

    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT slug, title, content,
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

    if not rows:
        typer.echo("No relevant pages found.")
        return

    typer.echo(f"\n🔍 Top {len(rows)} results for: {question}\n")
    for i, (slug, title, content, similarity) in enumerate(rows, 1):
        typer.echo(f"[{i}] [[{slug}]] {title} (similarity: {similarity:.3f})")
        # Truncate long content
        preview = content.replace("\n", " ")
        if len(preview) > 300:
            preview = preview[:300] + "..."
        typer.echo(f"    {preview}\n")
