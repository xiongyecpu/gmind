"""LLM-enhanced query: retrieve + reason + cite."""

from __future__ import annotations

import textwrap

from gmind import config, db, embed
from gmind.llm.engine import LLMEngine


def retrieve_relevant_pages(question: str, cfg: config.Config, top_k: int = 8) -> list[dict]:
    """Vector search for pages relevant to the question."""
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

    results = []
    for slug, title, content, similarity in rows:
        # Truncate content for context window
        truncated = content[:3000] if len(content) > 3000 else content
        results.append({
            "slug": slug,
            "title": title,
            "content": truncated,
            "similarity": float(similarity),
        })
    return results


def _format_context(pages: list[dict]) -> str:
    lines = []
    for i, p in enumerate(pages, 1):
        lines.append(f"[{i}] [[{p['slug']}]] {p['title']} (relevance: {p['similarity']:.2f})")
        # Indent content for clarity
        wrapped = textwrap.fill(p["content"], width=80, initial_indent="    ", subsequent_indent="    ")
        lines.append(wrapped)
        lines.append("")
    return "\n".join(lines)


def reasoned_query(
    question: str,
    engine: LLMEngine,
    cfg: config.Config,
    top_k: int = 8,
    temperature: float = 0.3,
) -> dict:
    """
    1. Retrieve relevant pages via vector search.
    2. Build context from page contents.
    3. Ask LLM to answer with citations.
    4. Return answer + sources.
    """
    pages = retrieve_relevant_pages(question, cfg, top_k=top_k)

    if not pages:
        return {
            "answer": "No relevant pages found in your knowledge base.",
            "sources": [],
        }

    context = _format_context(pages)

    prompt = f"""You are a helpful knowledge assistant. Answer the user's question based on the provided knowledge base content.

Instructions:
- Cite relevant pages using [[slug]] format.
- If the knowledge base does not contain enough information, say so clearly.
- Be concise but thorough.
- Answer in the same language as the user's question.

Knowledge base content:
{context}

User question: {question}

Answer:"""

    answer = engine.chat(
        [{"role": "user", "content": prompt}],
        temperature=temperature,
    )

    return {
        "answer": answer.strip(),
        "sources": [
            {"slug": p["slug"], "title": p["title"], "relevance": round(p["similarity"], 3)}
            for p in pages
        ],
    }
