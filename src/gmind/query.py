"""Query the knowledge base."""

from __future__ import annotations

import textwrap

import typer
from openai import OpenAI

from gmind import config, db, embed


def run_query(question: str, top_k: int = 5) -> None:
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    # 1. Embed question
    vectors = embed.embed_texts([question], cfg)
    vector = vectors[0]

    # 2. Vector search
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

    # 3. Build context for LLM
    context_parts = []
    for i, (slug, title, content, similarity) in enumerate(rows, 1):
        context_parts.append(
            f"[{i}] {title} (slug: {slug}, similarity: {similarity:.3f})\n{content}\n"
        )
    context = "\n".join(context_parts)

    prompt = textwrap.dedent(
        f"""\
        You are a knowledge assistant. Answer the user's question based on the retrieved notes.
        Cite sources using [[slug]] format.

        Retrieved notes:
        {context}

        Question: {question}

        Answer:"""
    )

    # 4. Call LLM
    client = OpenAI(
        api_key=cfg.llm_api_key,
        base_url=cfg.llm_base_url,
    )
    resp = client.chat.completions.create(
        model=cfg.llm_model,
        messages=[
            {"role": "system", "content": "You are a helpful knowledge assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    answer = resp.choices[0].message.content or ""

    typer.echo("\n🧠 Answer:\n")
    typer.echo(answer)
    typer.echo("\n📚 Sources:")
    for slug, title, _, similarity in rows:
        typer.echo(f"  - [[{slug}]] {title} (similarity: {similarity:.3f})")
