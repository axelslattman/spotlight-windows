# Spotlight Launcher for Windows

A Spotlight-style app launcher for Windows, built with Python and PyQt6.

Press **Alt+Space** (configurable) from anywhere on your desktop to instantly search apps, files, or evaluate math expressions.

---

## Requirements

- Windows 10 or 11
- Python 3.10 or newer — [download](https://www.python.org/downloads/)

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/yourname/spotlight-windows.git
cd spotlight-windows

# 2. Create a virtual environment (isolates dependencies from your system Python)
python -m venv .venv

# 3. Activate it
.venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt
```

---

## Running

```bash
# Make sure your virtual environment is active first:
.venv\Scripts\activate

# Run the app (it starts in the background, no window appears until you press the hotkey)
python -m spotlight_windows
```

Press **Ctrl+Space** to open the launcher. Press **Escape** to hide it.

> **Note:** The launcher runs as a background process. You'll see it in Task Manager. To exit completely, close the process from Task Manager or add a system tray icon (future feature).

---

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+Space` | Open / hide the launcher |
| `↑` / `↓` | Navigate results |
| `Enter` | Open the selected result |
| `Escape` | Hide the launcher |

---

## Configuration

Edit **`config.json`** in the project root to customise the launcher:

```json
{
  "hotkey": "alt+space",
  "extra_folders": [],
  "max_results": 8,
  "web_search_url": "https://www.google.com/search?q={}"
}
```

### Fields

| Field | Description | Example |
|-------|-------------|---------|
| `hotkey` | Global keyboard shortcut | `"alt+space"`, `"win+space"`, `"ctrl+shift+space"` |
| `extra_folders` | Additional folders to index for file search | `["C:\\Projects", "D:\\Music"]` |
| `max_results` | Maximum number of results shown | `10` |
| `web_search_url` | Search engine URL; `{}` is replaced with your query | `"https://www.bing.com/search?q={}"` |

### Adding extra folders

Add any folder path to `extra_folders`. Use double backslashes (`\\`) in Windows paths inside JSON:

```json
{
  "hotkey": "alt+space",
  "extra_folders": [
    "C:\\Users\\YourName\\Projects",
    "D:\\Work\\Clients"
  ],
  "max_results": 8,
  "web_search_url": "https://www.google.com/search?q={}"
}
```

Restart the app after editing `config.json` for changes to take effect.

---

## Search behaviour

Results appear in this priority order:

1. **Apps** — searches Start Menu shortcuts (`%APPDATA%` and `%ProgramData%`)
2. **Files** — searches Documents, Desktop, Downloads, and your `extra_folders`
3. **Calculator** — type a math expression like `12 * 4` or `sqrt` to get an inline result
4. **Web search** — "Search Google for …" always appears last as a fallback

---

## Run on Windows startup

```bash
# Register the launcher so it starts automatically when you log in
python startup.py --install

# Remove it from startup
python startup.py --uninstall

# Check whether it's currently registered
python startup.py --status
```

This writes to `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run` (no administrator rights required).

---

## Hotkey notes

**Why Ctrl+Space?**

`Ctrl+Space` is reliable on Windows and doesn't conflict with any system shortcuts. `Win+Space` is reserved by Windows 10/11 for the IME language switcher at a lower hook level than user-space, making it unreliable. `Alt+Space` opens the window's system menu in some apps.

To change the hotkey, edit the `hotkey` field in `config.json`. Any combination supported by the `keyboard` library works (e.g. `"ctrl+shift+space"`, `"alt+space"`).

**Fullscreen suppression:** The hotkey is automatically ignored when a fullscreen application (such as a game) is in the foreground, so the launcher never interrupts your session.

**Conflicts with other apps:** If another app (like AutoHotkey) registers the same hotkey, both apps will respond. The `keyboard` library doesn't exclusively "own" a hotkey the way `RegisterHotKey` does.

---

## Project structure

```
spotlight-windows/
├── config.json              ← edit this to customise
├── requirements.txt
├── startup.py               ← run to enable/disable Windows startup
└── src/
    └── spotlight_windows/
        ├── main.py          ← entry point
        ├── config.py        ← loads config.json
        ├── calculator.py    ← safe math evaluation
        ├── indexer.py       ← background file indexer
        ├── search.py        ← search orchestrator
        ├── hotkey.py        ← global hotkey registration
        └── ui/
            └── launcher_window.py   ← PyQt6 floating window
```

---

## Troubleshooting

**"Could not register any global hotkey"**
- Try running the terminal as Administrator
- Check if another app is using the same hotkey
- Try a different hotkey in `config.json`

**App doesn't find my installed programs**
- The indexer searches Start Menu shortcuts. If your app has no Start Menu entry, add its folder to `extra_folders` in `config.json`.

**File search is missing a folder**
- Add the folder path to `extra_folders` in `config.json`.

**Calculator isn't working**
- Supported operators: `+`, `-`, `*`, `/`, `**` (power), `%` (modulo)
- The expression must contain at least one digit and one operator
- Spaces are fine: `12 * 4` works the same as `12*4`
