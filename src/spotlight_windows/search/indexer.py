from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from spotlight_windows.config import SUPPORTED_EXTENSIONS


class FileIndexer:
    """Build and maintain a local SQLite index of files + text content."""

    def __init__(self, db_path: Path, ignored_folders: list[str]) -> None:
        self.db_path = db_path
        self.ignored_folders = {name.lower() for name in ignored_folders}
        self._observer: Observer | None = None
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Create regular metadata table and FTS5 virtual table."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY,
                    path TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    extension TEXT,
                    modified REAL,
                    size INTEGER,
                    is_dir INTEGER DEFAULT 0,
                    snippet TEXT DEFAULT ''
                )
                """
            )
            # FTS5 gives fast full-text search over name/path/content.
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS file_fts USING fts5(
                    name,
                    path,
                    content,
                    content=''
                )
                """
            )

    def rebuild(self, folders: list[str]) -> None:
        """Clear and rebuild the entire index from configured folders."""
        with self._connect() as conn:
            conn.execute("DELETE FROM files")
            conn.execute("DELETE FROM file_fts")
        for folder in folders:
            self._crawl_folder(Path(folder))

    def _crawl_folder(self, root: Path) -> None:
        if not root.exists():
            return
        for current_root, dirs, files in os.walk(root):
            # Mutate dirs in-place so os.walk skips ignored folders recursively.
            dirs[:] = [d for d in dirs if d.lower() not in self.ignored_folders]
            for file_name in files:
                file_path = Path(current_root) / file_name
                self.upsert_file(file_path)

    def upsert_file(self, file_path: Path) -> None:
        """Insert or update a file's metadata and searchable text."""
        if not file_path.exists() or not file_path.is_file():
            return
        if any(part.lower() in self.ignored_folders for part in file_path.parts):
            return

        stat = file_path.stat()
        extension = file_path.suffix.lower()
        snippet = ""
        content = ""

        # Keep text extraction simple/fast for MVP by limiting size and file types.
        if extension in SUPPORTED_EXTENSIONS:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")[:20000]
                snippet = content[:240].replace("\n", " ")
            except OSError:
                content = ""

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO files(path, name, extension, modified, size, is_dir, snippet)
                VALUES(?, ?, ?, ?, ?, 0, ?)
                ON CONFLICT(path) DO UPDATE SET
                    name=excluded.name,
                    extension=excluded.extension,
                    modified=excluded.modified,
                    size=excluded.size,
                    snippet=excluded.snippet
                """,
                (str(file_path), file_path.name, extension, stat.st_mtime, stat.st_size, snippet),
            )
            row_id = cursor.lastrowid
            if not row_id:
                existing = conn.execute("SELECT id FROM files WHERE path=?", (str(file_path),)).fetchone()
                row_id = int(existing["id"])

            # Keep FTS row in sync with the metadata table row id.
            conn.execute("DELETE FROM file_fts WHERE rowid=?", (row_id,))
            conn.execute(
                "INSERT INTO file_fts(rowid, name, path, content) VALUES (?, ?, ?, ?)",
                (row_id, file_path.name, str(file_path), content),
            )

    def remove_file(self, file_path: Path) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM files WHERE path=?", (str(file_path),)).fetchone()
            if not row:
                return
            row_id = int(row["id"])
            conn.execute("DELETE FROM files WHERE id=?", (row_id,))
            conn.execute("DELETE FROM file_fts WHERE rowid=?", (row_id,))

    def start_watching(self, folders: list[str]) -> None:
        if self._observer:
            return
        handler = _IndexEventHandler(self)
        observer = Observer()
        for folder in folders:
            path = Path(folder)
            if path.exists():
                observer.schedule(handler, str(path), recursive=True)
        observer.daemon = True
        observer.start()
        self._observer = observer

    def stop_watching(self) -> None:
        if not self._observer:
            return
        self._observer.stop()
        self._observer.join(timeout=1)
        self._observer = None


class _IndexEventHandler(FileSystemEventHandler):
    """Translate watchdog events into index updates."""

    def __init__(self, indexer: FileIndexer) -> None:
        self.indexer = indexer

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle_update(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle_update(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        self._handle_remove(Path(event.src_path))
        self._handle_update(event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._handle_remove(Path(event.src_path))

    def _handle_update(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        target = getattr(event, "dest_path", event.src_path)
        self.indexer.upsert_file(Path(target))

    def _handle_remove(self, path: Path) -> None:
        self.indexer.remove_file(path)
