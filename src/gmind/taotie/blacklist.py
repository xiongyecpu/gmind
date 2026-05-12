"""Blacklist management for files and folders that should never be ingested."""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path


DEFAULT_BLACKLIST_PATH = Path.home() / ".gmind" / "taotie-blacklist.json"

DEFAULT_BLACKLIST = {
    "version": 1,
    "files": [],
    "patterns": [
        "*/.ssh/*",
        "*/.env",
        "*/.env.*",
        "*/password*",
        "*/secret*",
        "*/credential*",
        "*/token*",
        "*/api_key*",
        "*/private_key*",
        "*/id_rsa*",
        "*/id_ed25519*",
        "*/.gnupg/*",
        "*/.aws/*",
        "*/.docker/*",
        "*/node_modules/*",
        "*/.git/*",
        "*/__pycache__/*",
        "*/.venv/*",
        "*/venv/*",
        "*/Cache*/*",
        "*/.cache/*",
        "*/Trash/*",
        "*/.Trash/*",
    ],
    "folders": [
        "/System",
        "/usr",
        "/bin",
        "/sbin",
        "/lib",
        "/libexec",
        "/dev",
        "/Volumes",
    ],
}


class Blacklist:
    """Manage the blacklist of files/folders to skip during scanning."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_BLACKLIST_PATH
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = DEFAULT_BLACKLIST.copy()
        else:
            self._data = DEFAULT_BLACKLIST.copy()
            self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def is_blacklisted(self, file_path: str) -> bool:
        """Check if a file path is blacklisted."""
        path = Path(file_path).resolve()
        path_str = str(path)

        # Check exact file match
        if path_str in self._data.get("files", []):
            return True

        # Check pattern match
        for pattern in self._data.get("patterns", []):
            if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(path.name, pattern):
                return True

        # Check parent folder match
        for folder in self._data.get("folders", []):
            folder_path = Path(folder).resolve()
            try:
                path.relative_to(folder_path)
                return True
            except ValueError:
                continue

        return False

    def add_file(self, file_path: str) -> None:
        """Add a file to the blacklist."""
        files = self._data.setdefault("files", [])
        resolved = str(Path(file_path).resolve())
        if resolved not in files:
            files.append(resolved)
            self._save()

    def remove_file(self, file_path: str) -> None:
        """Remove a file from the blacklist."""
        files = self._data.get("files", [])
        resolved = str(Path(file_path).resolve())
        if resolved in files:
            files.remove(resolved)
            self._save()

    def add_pattern(self, pattern: str) -> None:
        """Add a glob pattern to the blacklist."""
        patterns = self._data.setdefault("patterns", [])
        if pattern not in patterns:
            patterns.append(pattern)
            self._save()

    def remove_pattern(self, pattern: str) -> None:
        """Remove a glob pattern from the blacklist."""
        patterns = self._data.get("patterns", [])
        if pattern in patterns:
            patterns.remove(pattern)
            self._save()

    def add_folder(self, folder_path: str) -> None:
        """Add a folder to the blacklist."""
        folders = self._data.setdefault("folders", [])
        resolved = str(Path(folder_path).resolve())
        if resolved not in folders:
            folders.append(resolved)
            self._save()

    def remove_folder(self, folder_path: str) -> None:
        """Remove a folder from the blacklist."""
        folders = self._data.get("folders", [])
        resolved = str(Path(folder_path).resolve())
        if resolved in folders:
            folders.remove(resolved)
            self._save()

    def list_all(self) -> dict:
        """Return the full blacklist data."""
        return self._data.copy()

    def clear(self) -> None:
        """Reset to defaults (keep patterns, clear files)."""
        self._data["files"] = []
        self._save()
