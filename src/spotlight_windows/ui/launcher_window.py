# launcher_window.py – the floating PyQt6 launcher window.
#
# PyQt6 crash course (enough to understand this file):
# ─────────────────────────────────────────────────────
# • QWidget     – the base class for all UI elements (windows, buttons, etc.)
# • QVBoxLayout – arranges child widgets vertically (one below the next)
# • QLineEdit   – a single-line text input field
# • QListWidget – a scrollable list of items
# • QListWidgetItem – one row in a QListWidget
# • QFileIconProvider – asks Windows for the icon associated with any file/path
# • pyqtSignal  – a channel for broadcasting events (e.g. "user pressed Enter")
#
# Window flags used here:
#   FramelessWindowHint    – removes the title bar and window border
#   Tool                   – hides the window from the taskbar
#   WindowStaysOnTopHint   – floats above all other windows
#
# Qt's coordinate system: (0, 0) is the top-left corner of the screen.
# X increases to the right; Y increases downward.

import os
import webbrowser
from typing import Optional

from PyQt6.QtCore import Qt, QFileInfo, QTimer
from PyQt6.QtGui import QKeyEvent, QIcon, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QFileIconProvider,
    QStyle,
    QApplication,
    QMessageBox,
)

from ..search import SearchResult, ResultKind, SearchService


# ---------------------------------------------------------------------------
# Dark theme stylesheet
# ---------------------------------------------------------------------------
# Qt stylesheets use a CSS-like syntax. "QWidget" targets all widget types;
# "#search_input" targets the widget with objectName "search_input".
_STYLESHEET = """
QWidget#card {
    background: rgba(30, 31, 38, 230);
    border-radius: 14px;
}

QLineEdit#search_input {
    background: rgba(255, 255, 255, 12);
    border: 1px solid rgba(255, 255, 255, 25);
    border-radius: 10px;
    padding: 10px 14px;
    color: #f0f0f5;
    font-size: 15px;
    selection-background-color: rgba(80, 128, 255, 180);
}

QListWidget#results_list {
    background: transparent;
    border: none;
    outline: none;
    color: #d8d8e0;
    font-size: 13px;
}

QListWidget#results_list::item {
    padding: 6px 8px;
    border-radius: 8px;
}

QListWidget#results_list::item:selected {
    background: rgba(80, 128, 255, 110);
    color: #ffffff;
}

QListWidget#results_list::item:hover {
    background: rgba(255, 255, 255, 15);
}

QLabel#hint_label {
    color: rgba(180, 180, 200, 100);
    font-size: 11px;
    padding: 2px 8px 6px 8px;
}
"""

# Window dimensions (pixels)
_WINDOW_WIDTH = 620
_WINDOW_MAX_HEIGHT = 520  # shrinks when there are fewer results


class LauncherWindow(QWidget):
    """The main floating launcher window.

    Lifecycle:
        window = LauncherWindow(search_service)
        window.toggle()   # called by the global hotkey listener
    """

    def __init__(self, search_service: SearchService) -> None:
        # QWidget.__init__(self) sets up the Qt internals. None means "no parent
        # widget" – this window is a top-level window, not embedded in another.
        super().__init__(None)

        self._search_service = search_service

        # QFileIconProvider asks Windows (via the Shell) for the icon of any
        # file. Create it once and reuse it – construction is expensive.
        self._icon_provider = QFileIconProvider()

        # Store the search results we're currently showing.
        self._current_results: list[SearchResult] = []

        self._setup_window_flags()
        self._build_ui()
        self._apply_stylesheet()
        self._connect_signals()

    # -----------------------------------------------------------------------
    # Initialisation helpers
    # -----------------------------------------------------------------------

    def _setup_window_flags(self) -> None:
        """Configure the window to be borderless, floating, and hidden from taskbar."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint       # No title bar or border
            | Qt.WindowType.Tool                    # Not shown in taskbar
            | Qt.WindowType.WindowStaysOnTopHint    # Always on top of other windows
        )
        # WA_TranslucentBackground allows the window to have transparent regions
        # (we use rgba colours with < 255 alpha to create the glass effect).
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def _build_ui(self) -> None:
        """Create and arrange all the widgets inside the window."""

        # The outer widget's background is transparent (WA_TranslucentBackground).
        # We put a "card" QWidget on top of it with a dark rounded background.
        # This gives us the frosted-glass floating panel look.
        self.setFixedWidth(_WINDOW_WIDTH)

        # Outer layout – holds just the card widget with some padding for
        # the drop shadow to show through.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)  # left, top, right, bottom

        # The "card" is a plain QWidget that receives our dark background style.
        card = QWidget()
        card.setObjectName("card")  # Matches #card in the stylesheet
        outer_layout.addWidget(card)

        # Inner layout – the actual content (search box + results) inside the card.
        inner_layout = QVBoxLayout(card)
        inner_layout.setContentsMargins(10, 10, 10, 6)
        inner_layout.setSpacing(6)

        # ── Search input ──────────────────────────────────────────────────
        self.search_input = QLineEdit()
        self.search_input.setObjectName("search_input")
        self.search_input.setPlaceholderText("Search apps, files, or calculate…")
        # Fix height so it stays the same regardless of content
        self.search_input.setFixedHeight(44)
        inner_layout.addWidget(self.search_input)

        # ── Results list ──────────────────────────────────────────────────
        self.results_list = QListWidget()
        self.results_list.setObjectName("results_list")
        # Don't show a scroll bar – we cap results to max_results
        self.results_list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        # Icon size for result items (width x height in pixels)
        self.results_list.setIconSize(self.results_list.iconSize().__class__(20, 20))
        # Hide the list initially; it becomes visible once there are results
        self.results_list.setVisible(False)
        inner_layout.addWidget(self.results_list)

        # ── Hint label ────────────────────────────────────────────────────
        self.hint_label = QLabel("↑↓ navigate  ↵ open  Esc dismiss")
        self.hint_label.setObjectName("hint_label")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setVisible(False)
        inner_layout.addWidget(self.hint_label)

        # Store reference to card so _resize() can adjust its height
        self._card = card

    def _apply_stylesheet(self) -> None:
        """Apply the dark theme to the window."""
        self.setStyleSheet(_STYLESHEET)

    def _connect_signals(self) -> None:
        """Wire up events: text changes trigger search; item activation opens items."""

        # textChanged fires every time the user types or deletes a character.
        # We connect it to our _on_query_changed method.
        self.search_input.textChanged.connect(self._on_query_changed)

        # itemActivated fires when the user double-clicks or presses Enter on an item.
        self.results_list.itemActivated.connect(self._on_item_activated)

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def toggle(self) -> None:
        """Show the launcher if hidden, hide it if visible."""
        if self.isVisible():
            self.hide_launcher()
        else:
            self.show_centered()

    def show_centered(self) -> None:
        """Show the window centered horizontally, ~25% from the top of the screen."""
        # Get the screen the cursor is currently on (handles multi-monitor setups)
        screen = QApplication.screenAt(
            QApplication.primaryScreen().geometry().center()
        ) or QApplication.primaryScreen()

        screen_rect = screen.availableGeometry()  # excludes taskbar area

        # Calculate where the top-left corner of the window should be so that
        # the window is horizontally centred and 25% from the top of the screen.
        x = screen_rect.x() + (screen_rect.width() - _WINDOW_WIDTH) // 2
        y = screen_rect.y() + screen_rect.height() // 4

        self.move(x, y)
        self.show()

        # Clear previous search state when re-opening
        self.search_input.clear()
        self.results_list.clear()
        self.results_list.setVisible(False)
        self.hint_label.setVisible(False)
        self._resize_to_content()

        # raise_() brings the window in front of everything, then activateWindow()
        # gives it keyboard focus so the user can type immediately.
        self.raise_()
        self.activateWindow()
        self.search_input.setFocus()

    def hide_launcher(self) -> None:
        """Hide the launcher window."""
        self.hide()

    # -----------------------------------------------------------------------
    # Event handlers
    # -----------------------------------------------------------------------

    def _on_query_changed(self, query: str) -> None:
        """Called every time the search text changes. Runs a new search."""
        results = self._search_service.search(query)
        self._current_results = results
        self._populate_results(results)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        """Called when the user double-clicks or hits Enter on a list item."""
        row = self.results_list.row(item)  # which row is this item on?
        if 0 <= row < len(self._current_results):
            self._open_result(self._current_results[row])

    def _open_result(self, result: SearchResult) -> None:
        """Open the selected search result."""
        self.hide_launcher()

        if result.kind == ResultKind.WEB:
            # Open the URL in the default browser
            webbrowser.open(result.url)
            return

        if result.kind == ResultKind.CALC:
            # Nothing to "open" for a calculator result.
            # A more advanced version might copy the answer to the clipboard.
            return

        # For apps and files, use os.startfile() which tells Windows to open the
        # file with whatever program is registered to handle that file type.
        if result.path:
            try:
                os.startfile(result.path)  # type: ignore[attr-defined]  # Windows-only
            except OSError as e:
                # Show a friendly error dialog if the file can't be opened.
                QMessageBox.warning(
                    None,
                    "Could not open file",
                    f"Failed to open:\n{result.path}\n\n{e}",
                )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard navigation throughout the launcher."""
        key = event.key()

        if key == Qt.Key.Key_Escape:
            self.hide_launcher()

        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # If a list item is selected, open it.
            current_item = self.results_list.currentItem()
            if current_item:
                self._on_item_activated(current_item)
            elif self._current_results:
                # Nothing selected yet → open the first result.
                self.results_list.setCurrentRow(0)
                self._on_item_activated(self.results_list.currentItem())

        elif key == Qt.Key.Key_Down:
            # Move selection one step down in the results list.
            current_row = self.results_list.currentRow()
            next_row = min(current_row + 1, self.results_list.count() - 1)
            self.results_list.setCurrentRow(next_row)
            # Keep focus on the text input so the user can keep typing
            self.search_input.setFocus()

        elif key == Qt.Key.Key_Up:
            current_row = self.results_list.currentRow()
            if current_row <= 0:
                # Already at the top – clear the selection and return focus to input
                self.results_list.clearSelection()
            else:
                self.results_list.setCurrentRow(current_row - 1)
            self.search_input.setFocus()

        else:
            # For all other keys, let the default handler run (so the user
            # can type in the search box normally).
            super().keyPressEvent(event)

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _populate_results(self, results: list[SearchResult]) -> None:
        """Clear the list and fill it with the new search results."""
        self.results_list.clear()

        for result in results:
            item = QListWidgetItem()
            item.setText(result.title)

            # Set a smaller subtitle using the item's tooltip (shown on hover)
            # and as a data role for potential future use.
            item.setToolTip(result.subtitle)

            # Get the icon for this result
            icon = self._get_icon(result)
            if icon:
                item.setIcon(icon)

            self.results_list.addItem(item)

        has_results = len(results) > 0
        self.results_list.setVisible(has_results)
        self.hint_label.setVisible(has_results)

        # Auto-select the first item so pressing Enter immediately works
        if has_results:
            self.results_list.setCurrentRow(0)

        self._resize_to_content()

    def _get_icon(self, result: SearchResult) -> Optional[QIcon]:
        """Return an appropriate QIcon for the given result."""
        if result.kind == ResultKind.WEB:
            # Use a built-in Qt standard icon for the web result
            return QApplication.style().standardIcon(
                QStyle.StandardPixmap.SP_BrowserReload
            )

        if result.kind == ResultKind.CALC:
            return QApplication.style().standardIcon(
                QStyle.StandardPixmap.SP_FileIcon
            )

        if result.path:
            # QFileIconProvider queries Windows Shell for the icon of this file.
            # For .lnk files, Windows returns the application icon embedded in the shortcut.
            return self._icon_provider.icon(QFileInfo(result.path))

        return None

    def _resize_to_content(self) -> None:
        """Adjust the window height to fit the current number of results."""
        # Base height: just the search input + margins
        base_height = 44 + 10 + 10 + 6 + 12 + 12  # input + padding + card margins

        if self.results_list.isVisible():
            # Each list item is about 34px tall; clamp to a maximum height
            item_height = 34
            list_height = min(
                self.results_list.count() * item_height,
                _WINDOW_MAX_HEIGHT - base_height,
            )
            base_height += list_height + 6 + 20  # spacing + hint label

        self.setFixedHeight(base_height)
