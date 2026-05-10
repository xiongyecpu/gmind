#!/usr/bin/env python3
"""Re-embed all pages with the current embedding model."""

import sys
sys.path.insert(0, "src")

from gmind.config import load_config
from gmind.db import init_pool, get_conn
from gmind.embed import embed_texts


def main():
    cfg = load_config()
    print(f"Model: {cfg.embedding_model}")
    print(f"Base URL: {cfg.embedding_base_url}")
    init_pool(cfg.database_url)

    with get_conn() as conn:
        cur = conn.execute("SELECT id, slug, title, content FROM pages ORDER BY id")
        pages = cur.fetchall()

    print(f"Found {len(pages)} pages to re-embed")

    for page_id, slug, title, content in pages:
        text = f"{title}\n\n{content}" if title else content
        vectors = embed_texts([text], cfg)
        vector = [float(v) for v in vectors[0]]

        with get_conn() as conn:
            conn.execute(
                "UPDATE pages SET embedding = %s WHERE id = %s",
                (vector, page_id),
            )
        print(f"  ✅ {slug}")

    print("Done.")


if __name__ == "__main__":
    main()
