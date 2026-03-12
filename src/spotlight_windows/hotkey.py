# hotkey.py – registers a global keyboard shortcut and notifies the UI.
#
# The core challenge: thread safety
# ──────────────────────────────────
# The `keyboard` library intercepts keystrokes by running its own background
# thread. When our hotkey fires, the callback runs in *that* thread – not in
# the Qt main thread. Qt requires that all UI operations happen on the main
# thread, so calling window.show() directly from the keyboard callback would
# cause crashes or undefined behaviour.
#
# The solution is a PyQt6 *signal*. Signals can be emitted from any thread;
# Qt's event loop automatically delivers the connected slot on the main thread.
# Think of it like a thread-safe message: the background thread drops a note
# ("hotkey fired!"), and the Qt event loop picks it up and acts on it safely.

import logging

import keyboard  # Third-party: global keyboard hooks
from PyQt6.QtCore import QObject, pyqtSignal

from .fullscreen import is_fullscreen_app_active

# Set up logging so we can see what's happening without cluttering the UI.
# logging.getLogger(__name__) creates a logger named after this module.
logger = logging.getLogger(__name__)

# Fallback hotkeys tried if the configured one can't be registered.
# ctrl+space is reliable and doesn't conflict with any Windows system shortcuts.
_FALLBACK_SEQUENCE = ["ctrl+space", "alt+space"]


class HotkeyListener(QObject):
    """Registers a global hotkey and emits a signal when it's pressed.

    Inherits from QObject (not QWidget) because it has no visual representation;
    it just needs to emit signals.

    Usage:
        listener = HotkeyListener(cfg.hotkey)
        listener.triggered.connect(window.toggle)  # called on the main thread
        listener.register()
    """

    # pyqtSignal() declares a signal with no arguments.
    # When this signal is emitted, all connected slots are called.
    triggered = pyqtSignal()

    def __init__(self, hotkey: str) -> None:
        super().__init__()
        self._hotkey = hotkey          # The hotkey string from config, e.g. "alt+space"
        self._handle = None            # Returned by keyboard.add_hotkey(); needed to remove it

    def register(self) -> str:
        """Register the hotkey. Returns the hotkey string that was successfully registered.

        Tries the configured hotkey first. If it fails, tries the fallback sequence.
        """
        candidates = [self._hotkey]
        # Add any fallbacks that aren't already the primary choice
        for fallback in _FALLBACK_SEQUENCE:
            if fallback != self._hotkey:
                candidates.append(fallback)

        for hotkey_str in candidates:
            try:
                # keyboard.add_hotkey() installs a hook that calls our callback
                # whenever the key combination is pressed. It returns a handle
                # we need to save for later removal.
                self._handle = keyboard.add_hotkey(
                    hotkey_str,
                    self._on_hotkey_pressed,
                    suppress=True,   # Prevent the hotkey from reaching other apps
                )
                self._hotkey = hotkey_str
                logger.info("Registered hotkey: %s", hotkey_str)
                return hotkey_str

            except Exception as exc:
                logger.warning("Could not register hotkey '%s': %s", hotkey_str, exc)

        raise RuntimeError(
            "Could not register any global hotkey. "
            "Try running as administrator, or check for conflicts with other apps."
        )

    def unregister(self) -> None:
        """Remove the hotkey hook. Called on app shutdown."""
        if self._handle is not None:
            try:
                keyboard.remove_hotkey(self._handle)
                self._handle = None
                logger.info("Unregistered hotkey: %s", self._hotkey)
            except Exception as exc:
                logger.warning("Error removing hotkey: %s", exc)

    def _on_hotkey_pressed(self) -> None:
        """Called by the keyboard library's thread when the hotkey fires.

        We must NOT touch Qt widgets here. Instead we emit the signal,
        which Qt will deliver to connected slots on the main thread.
        """
        # If a fullscreen app (like a game) is in the foreground, silently
        # ignore the hotkey so we don't disrupt the user's session.
        if is_fullscreen_app_active():
            logger.debug("Hotkey suppressed: fullscreen app is active.")
            return

        # self.triggered.emit() is thread-safe: Qt queues the call and
        # processes it in the next iteration of the main event loop.
        self.triggered.emit()
