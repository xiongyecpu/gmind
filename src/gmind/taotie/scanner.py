"""File scanner — discover knowledge files across the computer."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileInfo:
    """A candidate file discovered during scanning."""

    path: str
    size: int
    mtime: float
    ext: str
    # populated by classifier
    should_ingest: bool = True
    reason: str = ""
    privacy_level: str = "safe"
    contains_passwords: bool = False
    contains_pii: bool = False
    is_knowledge: bool = True


# Extensions we consider for ingestion
SUPPORTED_EXTS = {".md", ".txt", ".pdf", ".docx"}

# System directories to skip
SKIP_DIRS = {
    ".git", ".svn", ".hg",
    "node_modules", "vendor", "__pycache__", ".venv", "venv",
    ".cache", "Caches", "Trash", ".Trash",
    "System", "usr", "bin", "sbin", "lib", "libexec",
    "Applications", "Library", "Volumes", "dev", "etc",
    ".ssh", ".gnupg", ".aws", ".docker",
}

# Known agent session directories
AGENT_DIRS = [
    "~/.hermes/sessions",
    "~/.openclaw/agents",
    "~/.claude/projects",
    "~/.kimi/sessions",
    "~/.codex/archived_sessions",
]

# WeChat messages (macOS)
WECHAT_BASE = Path.home() / "Library" / "Containers" / "com.tencent.xinWeChat" / "Data" / "Library" / "Application Support" / "com.tencent.xinWeChat"


def _should_skip_dir(name: str) -> bool:
    """Check if a directory name should be skipped."""
    if name.startswith(".") and name not in {".hermes", ".openclaw", ".claude", ".kimi", ".codex"}:
        return True
    return name in SKIP_DIRS


def _is_supported(file_path: Path) -> bool:
    """Check if file extension is supported."""
    return file_path.suffix.lower() in SUPPORTED_EXTS


def _is_knowledge_text(file_path: Path) -> bool:
    """Heuristic: is this file likely to contain knowledge text?"""
    ext = file_path.suffix.lower()
    if ext == ".txt":
        try:
            size = file_path.stat().st_size
            return 500 <= size <= 10 * 1024 * 1024  # 500B - 10MB
        except OSError:
            return False
    return True


def scan_directory(
    root: str | Path,
    *,
    recursive: bool = True,
    max_depth: int = 8,
    min_size: int = 100,
) -> list[FileInfo]:
    """Scan a single directory for candidate files."""
    root = Path(root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return []

    results: list[FileInfo] = []

    try:
        entries = list(root.iterdir())
    except PermissionError:
        return []

    for entry in entries:
        if _should_skip_dir(entry.name):
            continue
        try:
            if entry.is_dir() and recursive and max_depth > 0:
                results.extend(scan_directory(entry, recursive=recursive, max_depth=max_depth - 1, min_size=min_size))
            elif entry.is_file() and _is_supported(entry) and _is_knowledge_text(entry):
                stat = entry.stat()
                if stat.st_size >= min_size:
                    results.append(FileInfo(
                        path=str(entry),
                        size=stat.st_size,
                        mtime=stat.st_mtime,
                        ext=entry.suffix.lower(),
                    ))
        except (PermissionError, OSError):
            continue

    return results


def scan_computer(
    *,
    extra_dirs: list[str] | None = None,
    skip_patterns: list[str] | None = None,
) -> tuple[list[FileInfo], list[FolderRecommendation]]:
    """Scan the whole computer for knowledge files and recommend folders.

    Returns (files, folder_recommendations).
    """
    home = Path.home()

    # Base directories to scan
    base_dirs = [
        home / "Documents",
        home / "Desktop",
        home / "Downloads",
    ]

    # Add agent session dirs if they exist
    for d in AGENT_DIRS:
        p = Path(d).expanduser()
        if p.exists():
            base_dirs.append(p)

    # Add extra dirs
    if extra_dirs:
        for d in extra_dirs:
            p = Path(d).expanduser()
            if p.exists():
                base_dirs.append(p)

    # Add WeChat if exists
    if WECHAT_BASE.exists():
        for sub in WECHAT_BASE.iterdir():
            msg_dir = sub / "Message"
            if msg_dir.exists():
                base_dirs.append(msg_dir)

    all_files: list[FileInfo] = []
    folder_files: dict[Path, list[FileInfo]] = {}

    for d in base_dirs:
        try:
            files = scan_directory(d, recursive=True, max_depth=8)
            all_files.extend(files)
            # Group by parent folder for recommendations
            for f in files:
                parent = Path(f.path).parent
                folder_files.setdefault(parent, []).append(f)
        except Exception:
            continue

    # Build folder recommendations
    recommendations = _build_recommendations(folder_files)

    return all_files, recommendations


@dataclass
class FolderRecommendation:
    """A recommended folder for watching."""

    path: str
    file_count: int
    knowledge_file_count: int
    total_size: int
    is_agent_session: bool = False
    is_wechat: bool = False
    checked: bool = True  # default checked in UI


def _build_recommendations(
    folder_files: dict[Path, list[FileInfo]],
) -> list[FolderRecommendation]:
    """Build folder recommendations from scanned files."""
    recs: list[FolderRecommendation] = []

    for folder, files in folder_files.items():
        if len(files) < 3:
            continue

        knowledge_count = len(files)
        total_size = sum(f.size for f in files)

        # Skip if mostly non-knowledge
        if knowledge_count < 3:
            continue

        path_str = str(folder)
        is_agent = any(a in path_str for a in [".hermes", ".openclaw", ".claude", ".kimi", ".codex"])
        is_wechat = "com.tencent.xinWeChat" in path_str

        recs.append(FolderRecommendation(
            path=path_str,
            file_count=len(files),
            knowledge_file_count=knowledge_count,
            total_size=total_size,
            is_agent_session=is_agent,
            is_wechat=is_wechat,
            checked=True,
        ))

    # Sort by file count desc
    recs.sort(key=lambda r: r.file_count, reverse=True)
    return recs[:20]  # top 20


def get_folders_for_watching(
    recommendations: list[FolderRecommendation],
) -> list[str]:
    """Get list of folder paths marked for watching (checked=True)."""
    return [r.path for r in recommendations if r.checked]
