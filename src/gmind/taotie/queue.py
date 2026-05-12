"""Ingest queue — manage the pipeline of files waiting to be ingested."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from gmind import add, config, db, ingest, utils
from gmind.taotie.history import IngestHistory
from gmind.utils import notify_macos


@dataclass
class IngestTask:
    """A single file waiting to be ingested."""

    path: str
    size: int
    ext: str
    selected: bool = True
    status: str = "pending"
    progress: float = 0.0
    slug: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "size": self.size,
            "ext": self.ext,
            "selected": self.selected,
            "status": self.status,
            "progress": self.progress,
            "slug": self.slug,
            "error": self.error,
        }


QUEUE_STATE_PATH = Path.home() / ".gmind" / "taotie-queue.json"


class IngestQueue:
    """Thread-safe ingest queue with persistence."""

    _instance: IngestQueue | None = None
    _lock = threading.Lock()

    def __new__(cls) -> IngestQueue:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self.tasks: list[IngestTask] = []
        self.current_index: int = -1
        self.paused: bool = False
        self._running: bool = False
        self._thread: threading.Thread | None = None
        self._callbacks: list[Callable] = []
        self._task_lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if QUEUE_STATE_PATH.exists():
            try:
                with QUEUE_STATE_PATH.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                self.tasks = [IngestTask(**t) for t in data.get("tasks", [])]
                self.current_index = data.get("current_index", -1)
                self.paused = data.get("paused", False)
            except (json.JSONDecodeError, TypeError):
                self.tasks = []
                self.current_index = -1
                self.paused = False

    def _save(self) -> None:
        QUEUE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with QUEUE_STATE_PATH.open("w", encoding="utf-8") as f:
            json.dump({
                "tasks": [t.to_dict() for t in self.tasks],
                "current_index": self.current_index,
                "paused": self.paused,
            }, f, indent=2, ensure_ascii=False)

    def add_tasks(self, tasks: list[IngestTask]) -> None:
        with self._task_lock:
            self.tasks.extend(tasks)
            self._save()
        self._notify()

    def set_selected(self, path: str, selected: bool) -> None:
        with self._task_lock:
            for t in self.tasks:
                if t.path == path:
                    t.selected = selected
                    break
            self._save()
        self._notify()

    def remove_task(self, path: str) -> None:
        with self._task_lock:
            self.tasks = [t for t in self.tasks if t.path != path]
            self._save()
        self._notify()

    def clear(self) -> None:
        with self._task_lock:
            self.tasks = []
            self.current_index = -1
            self.paused = False
            self._save()
        self._notify()

    def get_pending(self) -> list[IngestTask]:
        with self._task_lock:
            return [t for t in self.tasks if t.selected and t.status in ("pending", "error")]

    def get_state(self) -> dict:
        with self._task_lock:
            current = None
            if 0 <= self.current_index < len(self.tasks):
                current = self.tasks[self.current_index].to_dict()
            return {
                "current": current,
                "pending": [t.to_dict() for t in self.tasks if t.status == "pending"],
                "done": [t.to_dict() for t in self.tasks if t.status == "done"],
                "error": [t.to_dict() for t in self.tasks if t.status == "error"],
                "skipped": [t.to_dict() for t in self.tasks if t.status == "skipped"],
                "paused": self.paused,
                "total": len(self.tasks),
            }

    def start(self) -> None:
        if self._running:
            return
        self.paused = False
        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        self.paused = True
        with self._task_lock:
            self._save()
        self._notify()

    def resume(self) -> None:
        self.paused = False
        if not self._running:
            self.start()
        self._notify()

    def stop(self) -> None:
        self._running = False
        self.paused = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _process_loop(self) -> None:
        cfg = config.load_config()
        db.init_pool(cfg.database_url)
        history = IngestHistory()

        while self._running:
            if self.paused:
                time.sleep(0.5)
                continue

            pending = self.get_pending()
            if not pending:
                self._running = False
                break

            task = pending[0]
            with self._task_lock:
                for i, t in enumerate(self.tasks):
                    if t.path == task.path:
                        self.current_index = i
                        t.status = "ingesting"
                        t.progress = 0.0
                        break
                self._save()
            self._notify()

            try:
                slug = self._ingest_one(task.path, cfg)
                with self._task_lock:
                    for t in self.tasks:
                        if t.path == task.path:
                            t.status = "done"
                            t.progress = 1.0
                            t.slug = slug
                            break
                    self._save()
                history.record(task.path, slug, "ok")
            except Exception as exc:
                with self._task_lock:
                    for t in self.tasks:
                        if t.path == task.path:
                            t.status = "error"
                            t.error = str(exc)
                            break
                    self._save()
                history.record(task.path, "", f"error: {exc}")

            self._notify()
            time.sleep(0.1)

        self._running = False
        self.current_index = -1
        with self._task_lock:
            self._save()
        self._notify()
        notify_macos("GMind", "饕餮盛宴入库完成")

    def _ingest_one(self, path: str, cfg: config.Config) -> str:
        from pathlib import Path as P
        file_path = P(path)
        content = ingest._extract_text(file_path)
        if not content or not content.strip():
            raise ValueError("Empty content")

        title = ingest._extract_title_heuristic(content, file_path.stem)
        full_content = f"# {title}\n\n{content}"
        page_type = ingest._infer_type(title, content)
        slug = utils.slugify(title)

        # Check for duplicate by checksum
        checksum = utils.make_checksum(full_content)
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT slug FROM pages WHERE checksum = %s LIMIT 1",
                (checksum,),
            ).fetchone()
            if row:
                return row[0]

        add.add_page(
            full_content,
            page_type=page_type,
            title=title,
            slug=slug,
            source=f"taotie:{path}",
            on_duplicate="a",
        )
        return slug

    def register_callback(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def _notify(self) -> None:
        for cb in self._callbacks:
            try:
                cb()
            except Exception:
                pass
