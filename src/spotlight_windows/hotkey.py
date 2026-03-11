from __future__ import annotations

import ctypes
import ctypes.wintypes
import threading

from PySide6.QtCore import QObject, Signal

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_WIN = 0x0008
VK_SPACE = 0x20


class GlobalHotkeyListener(QObject):
    """Background Win32 hotkey listener that emits a Qt signal on trigger."""
    triggered = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._thread: threading.Thread | None = None
        self._running = False
        self._registered_id: int | None = None
        self.registered_sequence = ""

    def start(self, preferred: str = "win+space") -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._message_loop, args=(preferred,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _message_loop(self, preferred: str) -> None:
        user32 = ctypes.windll.user32
        # Windows can reserve Win+Space (IME/input language), so keep fallback order.
        options = [(MOD_WIN, "Win+Space"), (MOD_ALT, "Alt+Space")]
        if preferred.lower() == "alt+space":
            options.reverse()

        hotkey_id = 1
        for modifier, name in options:
            if user32.RegisterHotKey(None, hotkey_id, modifier, VK_SPACE):
                self._registered_id = hotkey_id
                self.registered_sequence = name
                break
        if not self._registered_id:
            return

        msg = ctypes.wintypes.MSG()
        while self._running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                self.triggered.emit()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        user32.UnregisterHotKey(None, hotkey_id)
