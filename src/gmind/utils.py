"""Utility helpers."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess

from pypinyin import lazy_pinyin


def notify_macos(title: str, message: str) -> None:
    """Send a macOS notification via osascript."""
    if shutil.which("osascript") is None:
        return
    script = f'display notification "{message}" with title "{title}"'
    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


def make_checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def slugify(text: str) -> str:
    """Convert Chinese/English text to a URL-safe slug."""
    # Convert Chinese to pinyin
    pinyin_list = lazy_pinyin(text)
    slug = "-".join(pinyin_list)
    # Lowercase, keep only alphanumeric and hyphens
    slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower())
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    if not slug:
        slug = "untitled"
    return slug
