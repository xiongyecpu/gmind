"""Folder watcher configuration — which folders to monitor and when."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


WATCHER_CONFIG_PATH = Path.home() / ".gmind" / "taotie-watcher.json"


@dataclass
class WatchFolder:
    """A folder being watched for new files."""

    path: str
    enabled: bool = True
    scan_mode: str = "interval"  # interval / daily / weekly / realtime
    interval_hours: int = 1
    daily_time: str = "02:00"    # HH:MM
    weekly_day: int = 0          # 0=Sunday
    weekly_time: str = "02:00"

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "enabled": self.enabled,
            "scan_mode": self.scan_mode,
            "interval_hours": self.interval_hours,
            "daily_time": self.daily_time,
            "weekly_day": self.weekly_day,
            "weekly_time": self.weekly_time,
        }


class WatcherConfig:
    """Manage watched folder configuration."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or WATCHER_CONFIG_PATH
        self._folders: list[WatchFolder] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                self._folders = [WatchFolder(**f) for f in data.get("folders", [])]
            except (json.JSONDecodeError, TypeError):
                self._folders = []
        else:
            self._folders = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump({
                "version": 1,
                "folders": [f.to_dict() for f in self._folders],
            }, f, indent=2, ensure_ascii=False)

    def add(self, path: str, **kwargs) -> None:
        """Add a folder to watch."""
        # Remove if already exists
        self._folders = [f for f in self._folders if f.path != path]
        self._folders.append(WatchFolder(path=path, **kwargs))
        self._save()

    def remove(self, path: str) -> None:
        """Remove a folder from watch list."""
        self._folders = [f for f in self._folders if f.path != path]
        self._save()

    def update(self, path: str, **kwargs) -> None:
        """Update settings for a watched folder."""
        for f in self._folders:
            if f.path == path:
                for key, value in kwargs.items():
                    if hasattr(f, key):
                        setattr(f, key, value)
                break
        self._save()

    def list_all(self) -> list[dict]:
        """List all watched folders."""
        return [f.to_dict() for f in self._folders]

    def get_enabled(self) -> list[WatchFolder]:
        """Get enabled watched folders."""
        return [f for f in self._folders if f.enabled]

    def clear(self) -> None:
        """Remove all watched folders."""
        self._folders = []
        self._save()
