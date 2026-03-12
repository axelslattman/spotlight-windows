# main.py – the entry point for the Spotlight launcher.
#
# This module wires together all the other components:
#   config → indexer → search service → launcher window → hotkey listener
#
# Python entry point convention:
#   if __name__ == "__main__": ...
# This block only runs when the file is executed directly, not when imported.
# Since we're a package, we use __main__.py for the "python -m" invocation,
# but this file is also callable via "python -m spotlight_windows.main".

import logging
import sys

# PyQt6 imports
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

# Our own modules (relative imports within the package)
from . import config as cfg_module
from .indexer import FileIndexer
from .search import SearchService
from .hotkey import HotkeyListener
from .ui.launcher_window import LauncherWindow


def setup_logging() -> None:
    """Configure Python's built-in logging module.

    logging is like a smarter print() – messages have levels (DEBUG, INFO,
    WARNING, ERROR) and can be filtered, formatted, and written to files.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    """Start the launcher application."""
    setup_logging()
    logger = logging.getLogger(__name__)

    # ── 1. Load config ────────────────────────────────────────────────────
    config = cfg_module.load()
    logger.info("Config loaded: hotkey=%s, extra_folders=%s", config.hotkey, config.extra_folders)

    # ── 2. Create the Qt application ─────────────────────────────────────
    # QApplication manages the Qt event loop and all application-wide settings.
    # sys.argv passes any command-line arguments to Qt (e.g. platform options).
    app = QApplication(sys.argv)
    app.setApplicationName("Spotlight Launcher")
    app.setApplicationVersion("0.1.0")

    # IMPORTANT: Don't quit when the last window closes.
    # Our window hides on Escape/focus-loss; we don't want the app to exit.
    app.setQuitOnLastWindowClosed(False)

    # Use the Fusion style which fully supports custom stylesheets/dark themes.
    app.setStyle("Fusion")

    # ── 3. Start the file indexer (background thread) ─────────────────────
    logger.info("Starting file indexer...")
    indexer = FileIndexer(config)
    indexer.start()  # Blocks briefly for first scan, then launches daemon thread
    logger.info("File indexer started. %d entries indexed.", len(indexer.entries))

    # ── 4. Create the search service ──────────────────────────────────────
    search_service = SearchService(indexer=indexer, cfg=config)

    # ── 5. Create the launcher window ─────────────────────────────────────
    window = LauncherWindow(search_service=search_service)
    # Don't show it yet – it will appear when the hotkey is pressed.

    # ── 6. Register the global hotkey ─────────────────────────────────────
    listener = HotkeyListener(config.hotkey)

    try:
        active_hotkey = listener.register()
        logger.info("Hotkey active: %s", active_hotkey)
    except RuntimeError as e:
        logger.error("Failed to register hotkey: %s", e)
        # Show a basic error message and exit – can't run without a hotkey.
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None,
            "Hotkey registration failed",
            str(e) + "\n\nThe app will now exit.",
        )
        sys.exit(1)

    # Connect the hotkey signal to the window's toggle() method.
    # When the hotkey fires (in the keyboard thread), Qt delivers this call
    # to the main thread via the event loop.
    listener.triggered.connect(window.toggle)

    # ── 7. Clean up the hotkey when the app is about to quit ──────────────
    # app.aboutToQuit is a signal emitted just before the event loop exits.
    app.aboutToQuit.connect(listener.unregister)

    logger.info("Spotlight launcher running. Press %s to open.", active_hotkey)

    # ── 8. Start the Qt event loop ────────────────────────────────────────
    # app.exec() blocks here until the app is quit (e.g. via sys.exit or
    # the system tray menu). Qt processes UI events, signals, and timers
    # inside this loop.
    sys.exit(app.exec())


# Allow running as: python -m spotlight_windows.main
if __name__ == "__main__":
    main()
