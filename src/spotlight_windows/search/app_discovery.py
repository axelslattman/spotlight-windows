from __future__ import annotations

import os
from pathlib import Path

from .models import ResultType, SearchResult


class AppDiscovery:
    """Discovers launchable app shortcuts from Start Menu folders."""

    def __init__(self) -> None:
        self._app_entries: list[SearchResult] = []

    def refresh(self) -> None:
        start_menu_paths = self._start_menu_paths()
        entries: dict[str, SearchResult] = {}
        for root in start_menu_paths:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.suffix.lower() not in {".lnk", ".exe", ".url"}:
                    continue
                if path.name.startswith("~"):
                    continue
                title = path.stem
                if title.lower() in entries:
                    continue
                entries[title.lower()] = SearchResult(
                    title=title,
                    subtitle=str(path),
                    result_type=ResultType.APPLICATION,
                    target=str(path),
                    score=0.0,
                )
        self._app_entries = list(entries.values())

    def all_apps(self) -> list[SearchResult]:
        return self._app_entries

    @staticmethod
    def _start_menu_paths() -> list[Path]:
        program_data = os.getenv("ProgramData", r"C:\ProgramData")
        app_data = os.getenv("APPDATA", "")
        return [
            Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(app_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        ]
