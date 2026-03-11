from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QStyle, QSystemTrayIcon

from spotlight_windows.config import AppSettings, ConfigManager
from spotlight_windows.hotkey import GlobalHotkeyListener
from spotlight_windows.search.app_discovery import AppDiscovery
from spotlight_windows.search.indexer import FileIndexer
from spotlight_windows.search.models import ResultType, SearchResult
from spotlight_windows.search.service import SearchService
from spotlight_windows.ui.launcher_window import LauncherWindow


class SpotlightApp:
    def __init__(self) -> None:
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False)

        self.config = ConfigManager()
        self.settings = self.config.load_settings()

        self.indexer = FileIndexer(self.config.db_path, self.settings.ignored_folders)
        self.app_discovery = AppDiscovery()
        self.app_discovery.refresh()
        self.search_service = SearchService(self.config.db_path, self.settings, self.app_discovery)

        self.window = LauncherWindow()
        self.window.query_changed.connect(self.on_query_changed)
        self.window.result_activated.connect(self.activate_result)

        self.hotkey_listener = GlobalHotkeyListener()
        self.hotkey_listener.triggered.connect(self.toggle_launcher)
        self.hotkey_listener.start(self.settings.hotkey_preference)

        self.tray = self._create_tray()
        self.ensure_index()

    def _create_tray(self) -> QSystemTrayIcon:
        icon = self.qt_app.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
        tray = QSystemTrayIcon(icon, self.qt_app)
        menu = QMenu()

        show_action = QAction("Show Launcher", self.qt_app)
        show_action.triggered.connect(self.show_launcher)

        rebuild_action = QAction("Rebuild Index", self.qt_app)
        rebuild_action.triggered.connect(self.rebuild_index)

        folders_action = QAction("Open Settings File", self.qt_app)
        folders_action.triggered.connect(self.open_settings)

        quit_action = QAction("Quit", self.qt_app)
        quit_action.triggered.connect(self.quit)

        menu.addAction(show_action)
        menu.addAction(rebuild_action)
        menu.addAction(folders_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.setToolTip("Spotlight Windows")
        tray.show()
        return tray

    def ensure_index(self) -> None:
        self.indexer.rebuild(self.settings.indexed_folders)
        self.indexer.start_watching(self.settings.indexed_folders)

    def rebuild_index(self) -> None:
        self.ensure_index()
        self.tray.showMessage("Spotlight Windows", "Index rebuilt successfully.")

    def open_settings(self) -> None:
        path = self.config.settings_path
        if not path.exists():
            self.config.save_settings(self.settings)
        os.startfile(str(path))

    def show_launcher(self) -> None:
        self.window.show_centered()
        self.window.set_results(self.search_service.search(""))

    def toggle_launcher(self) -> None:
        if self.window.isVisible():
            self.window.hide_launcher()
        else:
            self.show_launcher()

    def on_query_changed(self, query: str) -> None:
        self.window.set_results(self.search_service.search(query))

    def activate_result(self, result: SearchResult) -> None:
        if result.result_type == ResultType.CALCULATOR:
            QGuiApplication.clipboard().setText(result.target)
            self.tray.showMessage("Spotlight Windows", f"Copied {result.target} to clipboard", msecs=1200)
            self.window.hide_launcher()
            return

        target = Path(result.target)
        try:
            if result.action == "reveal" and target.exists():
                subprocess.run(["explorer", "/select,", str(target)], check=False)
            else:
                os.startfile(result.target)
            self.settings = self.config.add_recent_item(self.settings, result.target)
            self.search_service.settings = self.settings
            self.window.hide_launcher()
        except OSError as exc:
            QMessageBox.warning(self.window, "Launch failed", str(exc))

    def run(self) -> int:
        return self.qt_app.exec()

    def quit(self) -> None:
        self.hotkey_listener.stop()
        self.indexer.stop_watching()
        self.tray.hide()
        self.qt_app.quit()
