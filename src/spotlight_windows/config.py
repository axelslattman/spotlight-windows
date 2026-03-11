from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_DIR_NAME = "SpotlightWindows"

DEFAULT_IGNORES = [
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".idea",
    ".vscode",
    "$Recycle.Bin",
]

SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".log",
    ".py",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".xml",
    ".yaml",
    ".yml",
}


@dataclass
class AppSettings:
    indexed_folders: list[str] = field(default_factory=list)
    ignored_folders: list[str] = field(default_factory=lambda: DEFAULT_IGNORES.copy())
    hotkey_preference: str = "win+space"
    max_results: int = 12
    recent_items: list[str] = field(default_factory=list)


class ConfigManager:
    def __init__(self) -> None:
        self.base_dir = self._resolve_base_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.base_dir / "settings.json"
        self.db_path = self.base_dir / "index.db"

    def _resolve_base_dir(self) -> Path:
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / APP_DIR_NAME
        return Path.home() / ".spotlight-windows"

    def load_settings(self) -> AppSettings:
        if not self.settings_path.exists():
            settings = AppSettings(indexed_folders=self._default_index_folders())
            self.save_settings(settings)
            return settings

        payload: dict[str, Any] = json.loads(self.settings_path.read_text(encoding="utf-8"))
        return AppSettings(
            indexed_folders=payload.get("indexed_folders", self._default_index_folders()),
            ignored_folders=payload.get("ignored_folders", DEFAULT_IGNORES.copy()),
            hotkey_preference=payload.get("hotkey_preference", "win+space"),
            max_results=int(payload.get("max_results", 12)),
            recent_items=payload.get("recent_items", []),
        )

    def save_settings(self, settings: AppSettings) -> None:
        serializable = {
            "indexed_folders": settings.indexed_folders,
            "ignored_folders": settings.ignored_folders,
            "hotkey_preference": settings.hotkey_preference,
            "max_results": settings.max_results,
            "recent_items": settings.recent_items[-100:],
        }
        self.settings_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")

    def add_recent_item(self, settings: AppSettings, item: str) -> AppSettings:
        recent = [entry for entry in settings.recent_items if entry != item]
        recent.insert(0, item)
        settings.recent_items = recent[:50]
        self.save_settings(settings)
        return settings

    @staticmethod
    def _default_index_folders() -> list[str]:
        home = Path.home()
        candidates = [home / "Documents", home / "Desktop", home / "Downloads"]
        return [str(path) for path in candidates if path.exists()]
