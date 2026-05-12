"""Ingest history — record of files that have been imported."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


HISTORY_PATH = Path.home() / ".gmind" / "taotie-history.json"


@dataclass
class IngestRecord:
    """A single import record."""

    path: str
    slug: str
    status: str  # ok / error / skipped
    timestamp: str
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "slug": self.slug,
            "status": self.status,
            "timestamp": self.timestamp,
            "error": self.error,
        }


class IngestHistory:
    """Manage import history stored locally."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or HISTORY_PATH
        self._records: list[IngestRecord] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                self._records = [IngestRecord(**r) for r in data.get("records", [])]
            except (json.JSONDecodeError, TypeError):
                self._records = []
        else:
            self._records = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump({
                "version": 1,
                "records": [r.to_dict() for r in self._records],
            }, f, indent=2, ensure_ascii=False)

    def record(self, path: str, slug: str, status: str, error: str = "") -> None:
        """Record an import event."""
        self._records.insert(0, IngestRecord(
            path=path,
            slug=slug,
            status=status,
            timestamp=datetime.now().isoformat(),
            error=error,
        ))
        # Keep last 1000 records
        self._records = self._records[:1000]
        self._save()

    def get_records(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[dict]:
        """Get import records with optional filtering."""
        records = self._records
        if status:
            records = [r for r in records if r.status == status]
        return [r.to_dict() for r in records[offset:offset + limit]]

    def is_imported(self, path: str) -> bool:
        """Check if a file has already been imported successfully."""
        for r in self._records:
            if r.path == path and r.status == "ok":
                return True
        return False

    def clear(self) -> None:
        """Clear all history."""
        self._records = []
        self._save()
