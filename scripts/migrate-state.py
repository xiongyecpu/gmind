#!/usr/bin/env python3
"""Migration: add state column and set defaults for existing rows."""

import sys
sys.path.insert(0, "src")

from gmind.config import load_config
from gmind.db import init_pool, get_conn


def main():
    cfg = load_config()
    init_pool(cfg.database_url)

    with get_conn() as conn:
        # 1. Add column if not exists
        conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'pages' AND column_name = 'state'
                ) THEN
                    ALTER TABLE pages ADD COLUMN state TEXT DEFAULT 'processed';
                END IF;
            END $$;
        """)
        print("✅ state column added (or already exists)")

        # 2. Create index
        conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE indexname = 'idx_pages_state'
                ) THEN
                    CREATE INDEX idx_pages_state ON pages(state);
                END IF;
            END $$;
        """)
        print("✅ idx_pages_state created (or already exists)")

        # 3. Set existing rows: capture/source → raw, others → processed
        cur = conn.execute("""
            UPDATE pages
            SET state = CASE
                WHEN page_type IN ('capture', 'source') THEN 'raw'
                ELSE 'processed'
            END
            WHERE state IS NULL
            RETURNING slug, page_type, state
        """)
        rows = cur.fetchall()
        print(f"✅ Migrated {len(rows)} rows")
        for slug, pt, st in rows:
            print(f"   {slug}: {pt} → {st}")


if __name__ == "__main__":
    main()
