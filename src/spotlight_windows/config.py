# config.py – loads and saves the user's config.json settings.
#
# A *dataclass* is a Python class that automatically generates __init__,
# __repr__, and other boilerplate based on the field annotations you declare.
# It's a clean way to represent structured data (like a settings object).

import json
import os
from dataclasses import dataclass, field
from pathlib import Path  # Path is an object-oriented way to work with file paths


# ---------------------------------------------------------------------------
# Default search folders (resolved at import time)
# Path.home() returns the current user's home directory, e.g. C:\Users\YourName
# The / operator on Path objects joins path segments (like os.path.join)
# ---------------------------------------------------------------------------
DEFAULT_INDEX_FOLDERS: list[str] = [
    str(Path.home() / "Documents"),
    str(Path.home() / "Desktop"),
    str(Path.home() / "Downloads"),
]


@dataclass
class Config:
    """All user-configurable settings, loaded from config.json."""

    # The keyboard shortcut to show/hide the launcher.
    # Defaults to ctrl+space — reliable on Windows, doesn't conflict with system shortcuts.
    hotkey: str = "ctrl+space"

    # Additional folders the user wants to include in file search.
    # Uses field(default_factory=list) instead of hotkey: list = []
    # because mutable defaults (lists, dicts) in dataclasses need a factory.
    extra_folders: list[str] = field(default_factory=list)

    # Maximum number of results to display at once.
    max_results: int = 8

    # URL template for web search. {} will be replaced with the search query.
    web_search_url: str = "https://www.google.com/search?q={}"


def _config_path() -> Path:
    """Return the path to config.json, preferring the project root."""
    # __file__ is the path to this source file (config.py).
    # .parent climbs up one directory at a time.
    # We go up 3 levels: config.py → spotlight_windows → src → project root
    project_root = Path(__file__).parent.parent.parent
    candidate = project_root / "config.json"

    if candidate.exists():
        return candidate

    # Fall back to %APPDATA%\SpotlightWindows\config.json so the app still
    # works when installed outside the project directory.
    appdata = Path(os.environ.get("APPDATA", Path.home()))
    fallback = appdata / "SpotlightWindows" / "config.json"
    fallback.parent.mkdir(parents=True, exist_ok=True)  # create folder if needed
    return fallback


def load() -> Config:
    """Read config.json and return a Config object.

    If the file doesn't exist or a key is missing, sensible defaults are used.
    This means adding new config keys in the future won't break old config files.
    """
    path = _config_path()

    if not path.exists():
        # No config file yet – return all defaults and write the file so
        # the user can find and edit it.
        cfg = Config()
        save(cfg)
        return cfg

    # json.loads / json.load parse a JSON string/file into a Python dict.
    with open(path, "r", encoding="utf-8") as f:
        data: dict = json.load(f)

    # **data unpacks the dict as keyword arguments to Config().
    # Unknown keys are ignored; missing keys get their default values.
    # We use .get() with defaults to be safe even if the JSON is incomplete.
    return Config(
        hotkey=data.get("hotkey", "alt+space"),
        extra_folders=data.get("extra_folders", []),
        max_results=data.get("max_results", 8),
        web_search_url=data.get("web_search_url", "https://www.google.com/search?q={}"),
    )


def save(cfg: Config) -> None:
    """Write the Config object back to config.json."""
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # dataclasses.asdict() converts a dataclass instance to a plain dict,
    # which json.dump can serialise.
    import dataclasses

    with open(path, "w", encoding="utf-8") as f:
        json.dump(dataclasses.asdict(cfg), f, indent=2)
