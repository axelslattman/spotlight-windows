# indexer.py – builds and maintains an in-memory index of apps and files.
#
# Why pre-index?
# Scanning the filesystem on every keystroke would be too slow. Instead we
# scan once at startup, store the results in a list, and search that list
# (which is very fast). We also refresh the list every 10 minutes in the
# background so new installs and files are picked up without a restart.
#
# Threading basics:
# Python can run code concurrently using *threads*. Each thread shares the
# same memory but runs independently. We use one background thread that loops
# forever: sleep 10 minutes → rebuild index → repeat.
#
# The *daemon=True* flag means: "kill this thread automatically when the main
# program exits." Without it, the app would hang at exit waiting for the thread.

import os
import threading  # Standard library module for working with threads
import time       # For time.sleep()
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config  # Relative import: the config module in this same package


@dataclass
class IndexedEntry:
    """Represents one item in the search index (an app or a file)."""
    name: str          # Display name shown in results (e.g. "Visual Studio Code")
    path: str          # Full filesystem path (e.g. "C:\Users\...\VSCode.lnk")
    is_app: bool       # True for Start Menu shortcuts, False for plain files


def _find_start_menu_shortcuts() -> list[IndexedEntry]:
    """Find all .lnk and .url shortcuts in the Windows Start Menu.

    Windows keeps Start Menu shortcuts in two locations:
    - Per-user:   %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs
    - System-wide: %ProgramData%\\Microsoft\\Windows\\Start Menu\\Programs
    """
    entries: list[IndexedEntry] = []

    # os.environ is a dict-like object holding environment variables.
    # We use .get() with a fallback path in case a variable isn't set.
    program_data = os.environ.get("ProgramData", r"C:\ProgramData")
    app_data = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))

    start_menu_roots = [
        Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(app_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]

    for root in start_menu_roots:
        if not root.exists():
            continue  # Skip if this path doesn't exist on this machine

        # rglob("*.lnk") recursively finds all files ending in .lnk.
        # .lnk files are Windows shortcut files.
        for lnk_path in root.rglob("*.lnk"):
            # path.stem is the filename without its extension.
            # E.g. "Visual Studio Code.lnk" → "Visual Studio Code"
            entries.append(IndexedEntry(
                name=lnk_path.stem,
                path=str(lnk_path),
                is_app=True,
            ))

        # .url files are internet shortcuts that open a URL in a browser.
        for url_path in root.rglob("*.url"):
            entries.append(IndexedEntry(
                name=url_path.stem,
                path=str(url_path),
                is_app=True,
            ))

    return entries


def _find_files(folders: list[str]) -> list[IndexedEntry]:
    """Walk the given folders and return an IndexedEntry for every file found.

    We deliberately skip hidden folders (starting with '.') and some known
    large/noisy directories to keep the index lean and fast.
    """
    entries: list[IndexedEntry] = []

    # Folder names to skip entirely – indexing these would add thousands of
    # irrelevant results (build artifacts, package managers, etc.)
    SKIP_DIRS: set[str] = {
        "node_modules", ".git", "__pycache__", ".venv", "venv",
        "env", ".env", "dist", "build", "target",
    }

    for folder_str in folders:
        folder = Path(folder_str)
        if not folder.exists():
            continue

        # os.walk() is a generator that yields (dirpath, dirnames, filenames)
        # for every directory it visits. We can modify dirnames in-place to
        # prevent os.walk from descending into directories we want to skip.
        for dirpath, dirnames, filenames in os.walk(folder):
            # Modify dirnames in-place: remove entries we want to skip.
            # [:] is required to modify the list in-place (not replace it).
            dirnames[:] = [
                d for d in dirnames
                if d not in SKIP_DIRS and not d.startswith(".")
            ]

            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                # Path(filename).stem strips the extension for the display name.
                entries.append(IndexedEntry(
                    name=Path(filename).stem,
                    path=full_path,
                    is_app=False,
                ))

    return entries


class FileIndexer:
    """Maintains an in-memory index of apps and files.

    Usage:
        indexer = FileIndexer(cfg)
        indexer.start()   # blocks briefly for initial scan, then runs in background
        results = indexer.entries  # always safe to call from any thread
    """

    # How often to rebuild the index, in seconds (10 minutes = 600 seconds)
    REFRESH_INTERVAL_SECONDS: int = 600

    def __init__(self, cfg: config.Config) -> None:
        self._cfg = cfg

        # The actual index data – a list of IndexedEntry objects.
        # We initialise it as empty; it's populated in _build().
        self._entries: list[IndexedEntry] = []

        # A Lock is a synchronisation primitive. Only one thread can "hold"
        # the lock at a time. We use it to protect _entries from being
        # simultaneously read and written by different threads.
        self._lock = threading.Lock()

        # Create the background thread. target= is the function it will run.
        # daemon=True means the thread will die when the main program exits.
        self._thread = threading.Thread(
            target=self._refresh_loop,
            name="FileIndexer",
            daemon=True,
        )

    def start(self) -> None:
        """Build the index immediately, then start the background refresh loop."""
        # We build synchronously first so results are ready before the user
        # types anything. This usually takes well under a second.
        self._build()
        # Then start the daemon thread for periodic refreshes.
        self._thread.start()

    @property
    def entries(self) -> list[IndexedEntry]:
        """Return a snapshot of the current index (thread-safe).

        We return a copy (list(...)) so the caller holds a stable reference
        even if the background thread rebuilds _entries mid-search.
        """
        with self._lock:  # "with lock" acquires the lock, runs the block, then releases
            return list(self._entries)

    def _build(self) -> None:
        """Scan apps and files and update the in-memory index."""
        # Build into a local list first, outside the lock, so we hold the
        # lock for the shortest possible time (just the final swap).
        new_entries: list[IndexedEntry] = []

        # 1. Start Menu shortcuts (apps)
        new_entries.extend(_find_start_menu_shortcuts())

        # 2. Files from default and user-configured folders
        all_folders = config.DEFAULT_INDEX_FOLDERS + self._cfg.extra_folders
        new_entries.extend(_find_files(all_folders))

        # Swap the old index for the new one atomically.
        # The "with self._lock" block ensures no other thread reads _entries
        # while we're replacing it.
        with self._lock:
            self._entries = new_entries

    def _refresh_loop(self) -> None:
        """Run forever: sleep 10 minutes, then rebuild the index."""
        while True:
            # Sleep releases the GIL (Global Interpreter Lock), so the main
            # thread can run the Qt event loop freely during this time.
            time.sleep(self.REFRESH_INTERVAL_SECONDS)
            self._build()
