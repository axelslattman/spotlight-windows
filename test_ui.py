# Quick test: launch the window directly without needing a global hotkey.
# Run with: PYTHONPATH=src .venv/bin/python3 test_ui.py
import sys
sys.path.insert(0, "src")

from PyQt6.QtWidgets import QApplication
from spotlight_windows import config as cfg_module
from spotlight_windows.indexer import FileIndexer
from spotlight_windows.search import SearchService
from spotlight_windows.ui.launcher_window import LauncherWindow

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(True)  # exit when the window is closed in this test
app.setStyle("Fusion")

cfg = cfg_module.load()
indexer = FileIndexer(cfg)
indexer.start()

search = SearchService(indexer=indexer, cfg=cfg)
window = LauncherWindow(search_service=search)
window.show_centered()

sys.exit(app.exec())
