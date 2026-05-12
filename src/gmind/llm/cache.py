"""SQLite-based local cache for LLM responses."""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

DEFAULT_CACHE_PATH = Path.home() / ".gmind" / "llm_cache.sqlite"
DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 days


class LLMCache:
    """Simple SQLite cache for LLM responses."""

    def __init__(self, path: Path | None = None, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.path = path or DEFAULT_CACHE_PATH
        self.ttl = ttl_seconds
        self._init_db()

    def _init_db(self) -> None:
        os.makedirs(self.path.parent, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_created ON llm_cache(created_at)"
            )
            conn.commit()

    def get(self, key: str) -> str | None:
        now = int(time.time())
        with sqlite3.connect(self.path) as conn:
            # Clean expired entries occasionally (1% chance)
            if hash(key) % 100 == 0:
                conn.execute("DELETE FROM llm_cache WHERE created_at < ?", (now - self.ttl,))
                conn.commit()

            row = conn.execute(
                "SELECT value FROM llm_cache WHERE key = ? AND created_at > ?",
                (key, now - self.ttl),
            ).fetchone()
            return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        now = int(time.time())
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO llm_cache (key, value, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, created_at=excluded.created_at
                """,
                (key, value, now),
            )
            conn.commit()

    def clear(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM llm_cache")
            conn.commit()

    def stats(self) -> dict:
        with sqlite3.connect(self.path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
            now = int(time.time())
            expired = conn.execute(
                "SELECT COUNT(*) FROM llm_cache WHERE created_at < ?",
                (now - self.ttl,),
            ).fetchone()[0]
            return {"total_entries": total, "expired_entries": expired}
