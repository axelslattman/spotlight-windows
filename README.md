# Spotlight Windows (MVP)

A Windows desktop launcher that recreates key Spotlight behaviors:

- Global hotkey (`Win+Space`, fallback `Alt+Space`)
- Fast centered search overlay with keyboard-first UX
- Search apps, files, and indexed file contents
- Inline safe calculator (`2+2`, `(25+5)*2`, etc.)
- System tray app with rebuild-index and settings access

## Recommended stack (and why)

- **Python 3.11+**: rapid MVP iteration and straightforward packaging.
- **PySide6 (Qt)**: polished desktop UI with smooth rendering, tray integration, and native-feeling controls.
- **SQLite + FTS5**: practical local full-text indexing/search with no external services.
- **watchdog**: incremental index updates when files change.
- **rapidfuzz**: fuzzy ranking for apps and filenames.
- **pywin32/Win32 APIs via ctypes**: global hotkey registration (`RegisterHotKey`).

### Hotkey tradeoffs on Windows

`Win+Space` is preferred for Spotlight feel, but Windows often reserves or intercepts it (input language/IME switching). This app:

1. tries `Win+Space` first,
2. automatically falls back to `Alt+Space` if registration fails.

This ensures a reliable launcher even on systems where `Win+Space` cannot be captured.

## Project structure

```text
spotlight-windows/
├── pyproject.toml
├── requirements.txt
├── README.md
└── src/
    └── spotlight_windows/
        ├── app.py
        ├── calculator.py
        ├── config.py
        ├── hotkey.py
        ├── main.py
        ├── ui/
        │   └── launcher_window.py
        └── search/
            ├── app_discovery.py
            ├── indexer.py
            ├── models.py
            └── service.py
```

## Getting started if you found this repo

### 1) Download the project

If this is your first time:

```powershell
git clone <REPO_URL>
cd spotlight-windows
```

If you already cloned it before and want the latest updates:

```powershell
git pull
```

### 2) Create a Python virtual environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) Install dependencies

```powershell
pip install -r requirements.txt
pip install -e .
```

### 4) Run the launcher

```powershell
spotlight-windows
```

After launch, the app sits in the system tray. Trigger the launcher with `Win+Space` (or `Alt+Space` fallback if Windows blocks `Win+Space`).

## Setup

1. Install Python 3.11+ on Windows.
2. Create and activate a virtual env.
3. Install deps:

```powershell
pip install -r requirements.txt
pip install -e .
```

4. Run:

```powershell
spotlight-windows
```

## Configuration

Settings are stored at:

- `%APPDATA%\SpotlightWindows\settings.json`

Editable fields:

- `indexed_folders`: folders to crawl/index.
- `ignored_folders`: folder names excluded everywhere.
- `hotkey_preference`: `win+space` or `alt+space`.
- `max_results`: number of results shown.

Defaults include ignores for `.git`, `node_modules`, `venv`, etc.

## Search behavior

- **Applications**: Start Menu shortcut/executable discovery.
- **Files**: filename/path/content indexed into SQLite FTS.
- **Recent items**: shown when query is empty.
- **Calculator**: safe AST parser (no `eval`) result appears at top and `Enter` copies it.

## Packaging for Windows

### Option A: PyInstaller (single-folder)

```powershell
pip install pyinstaller
pyinstaller --name SpotlightWindows --noconfirm --windowed --onedir -m spotlight_windows.main
```

Generated app: `dist\SpotlightWindows\SpotlightWindows.exe`

### Option B: Auto-start integration

Create a shortcut of the generated `.exe` in:

- `shell:startup`

So the launcher starts with Windows and stays in tray.

## MVP limitations

- Start Menu `.lnk` targets are launched directly; deep metadata extraction is minimal.
- Binary formats (PDF/Office) are not indexed yet.
- UI icons/result context actions are basic in MVP.

## Future enhancements

- PDF/Office extractors (e.g., `pypdf`, `python-docx`) behind pluggable index adapters.
- Better ranking signals (recency/frequency weights, path depth, typed-command history).
- Context actions: open containing folder, copy path, run as admin.
- Rich result rows with per-type icons and matched text highlighting.
- Optional preview pane and plugin system.
