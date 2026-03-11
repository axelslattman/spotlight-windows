from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from spotlight_windows.search.models import SearchResult


class LauncherWindow(QWidget):
    query_changed = Signal(str)
    result_activated = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(760, 430)
        self._results: list[SearchResult] = []
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)

        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Search apps, files, folders, or calculate…")
        self.input.setMinimumHeight(50)
        self.input.setFont(QFont("Segoe UI", 13))
        self.input.textChanged.connect(self.query_changed.emit)

        self.list_widget = QListWidget()
        self.list_widget.itemActivated.connect(self._activate_item)
        self.list_widget.itemDoubleClicked.connect(self._activate_item)

        hint_row = QHBoxLayout()
        hint = QLabel("↵ Open or copy    ↑↓ Navigate    Esc Hide")
        hint.setObjectName("hint")
        hint_row.addWidget(hint)
        hint_row.addStretch()

        layout.addWidget(self.input)
        layout.addWidget(self.list_widget)
        layout.addLayout(hint_row)
        outer.addWidget(card)

        self.setStyleSheet(
            """
            QWidget#card {
                background-color: rgba(24, 26, 31, 245);
                border: 1px solid rgba(255,255,255,22);
                border-radius: 18px;
            }
            QLineEdit {
                background: rgba(255,255,255,20);
                border: 1px solid rgba(255,255,255,36);
                border-radius: 12px;
                color: #f3f3f3;
                padding: 10px 14px;
            }
            QListWidget {
                background: transparent;
                border: none;
                color: #efefef;
                font-size: 13px;
                outline: none;
            }
            QListWidget::item {
                border-radius: 10px;
                padding: 8px;
                margin: 1px;
            }
            QListWidget::item:selected {
                background: rgba(80, 128, 255, 110);
            }
            QLabel#hint {
                color: #9da3b0;
                font-size: 12px;
            }
            """
        )

    def show_centered(self) -> None:
        screen = self.screen() or self.windowHandle().screen() if self.windowHandle() else None
        if screen:
            geometry = screen.availableGeometry()
            x = geometry.center().x() - self.width() // 2
            y = int(geometry.top() + geometry.height() * 0.18)
            self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()
        self.input.selectAll()

    def hide_launcher(self) -> None:
        self.hide()

    def set_results(self, results: list[SearchResult]) -> None:
        self._results = results
        self.list_widget.clear()
        for result in results:
            item = QListWidgetItem(f"{result.title}\n{result.subtitle}")
            self.list_widget.addItem(item)
        if results:
            self.list_widget.setCurrentRow(0)

    def selected_result(self) -> SearchResult | None:
        idx = self.list_widget.currentRow()
        if idx < 0 or idx >= len(self._results):
            return None
        return self._results[idx]

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.hide_launcher()
            return
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            result = self.selected_result()
            if result:
                self.result_activated.emit(result)
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self.hide_launcher()
        super().focusOutEvent(event)

    def _activate_item(self, item: QListWidgetItem) -> None:
        _ = item
        result = self.selected_result()
        if result:
            self.result_activated.emit(result)
