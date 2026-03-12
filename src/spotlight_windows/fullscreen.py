# fullscreen.py – detects whether a fullscreen app (e.g. a game) is in the foreground.
#
# Why bother?
# If you're in a fullscreen game, a launcher popup is jarring and disruptive.
# We check whether the foreground window fills the entire screen before showing
# the launcher. If it does, we silently ignore the hotkey.
#
# How fullscreen detection works on Windows:
# ───────────────────────────────────────────
# We use the Windows API (via ctypes, a built-in Python module that lets you
# call C functions in .dll files without writing any C code) to:
#   1. GetForegroundWindow()  → get the handle (ID) of the active window
#   2. GetWindowRect(handle)  → get that window's pixel coordinates
#   3. GetSystemMetrics()     → get the screen's width and height
# If the window covers the whole screen, a fullscreen app is running.
#
# ctypes.windll is only available on Windows. On Linux/Mac this module
# gracefully returns False so the rest of the app can still run.

import sys
import logging

logger = logging.getLogger(__name__)

# sys.platform is a string identifying the OS:
#   "win32"  → Windows (even on 64-bit!)
#   "linux"  → Linux / WSL
#   "darwin" → macOS
_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    # ctypes lets Python call functions from Windows DLLs.
    # ctypes.wintypes provides Windows-specific type definitions like RECT and HWND.
    import ctypes
    import ctypes.wintypes

    # Shortcuts to the Windows API DLLs we'll use.
    # user32.dll contains the window management functions.
    _user32 = ctypes.windll.user32

    # Tell ctypes what type each function returns, so it interprets the raw
    # bytes correctly. HWND is a "handle to a window" – basically an integer ID.
    _user32.GetForegroundWindow.restype = ctypes.wintypes.HWND

    # GetWindowRect needs a pointer to a RECT struct that it fills in.
    # We declare this so ctypes knows how to pass the argument.
    _user32.GetWindowRect.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.POINTER(ctypes.wintypes.RECT),
    ]
    _user32.GetWindowRect.restype = ctypes.wintypes.BOOL

    # GetSystemMetrics(0) = SM_CXSCREEN = screen width in pixels
    # GetSystemMetrics(1) = SM_CYSCREEN = screen height in pixels
    _SM_CXSCREEN = 0
    _SM_CYSCREEN = 1


def is_fullscreen_app_active() -> bool:
    """Return True if a fullscreen app (like a game) is currently in the foreground.

    Returns False on non-Windows platforms, or if detection fails for any reason.
    We never raise an exception from here — a detection failure should be silent.
    """
    if not _IS_WINDOWS:
        # We're on Linux or macOS (e.g. developing in WSL).
        # Fullscreen detection isn't supported here, so always allow the hotkey.
        return False

    try:
        # Step 1: Get the window that currently has keyboard focus.
        # Every open window has a unique HWND (handle). This returns the one
        # that's in the foreground (the one the user is looking at / typing into).
        hwnd = _user32.GetForegroundWindow()

        if not hwnd:
            # No foreground window (e.g. the desktop is focused).
            return False

        # Step 2: Get the position and size of that window.
        # RECT is a struct with four fields: left, top, right, bottom (in pixels).
        # We create an empty RECT and pass a pointer to it; Windows fills it in.
        rect = ctypes.wintypes.RECT()
        if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False

        # Calculate the window's width and height from its corner coordinates.
        window_width  = rect.right  - rect.left
        window_height = rect.bottom - rect.top

        # Step 3: Get the primary screen resolution.
        # This is the raw pixel size – it does NOT subtract the taskbar.
        # A fullscreen game will exactly match or exceed these values.
        screen_width  = _user32.GetSystemMetrics(_SM_CXSCREEN)
        screen_height = _user32.GetSystemMetrics(_SM_CYSCREEN)

        # A window is considered fullscreen if it covers the entire screen.
        # We use >= (not ==) to handle cases where the window is 1px oversized,
        # which some games do to avoid Windows visual effects on the edge.
        is_fullscreen = (window_width >= screen_width and window_height >= screen_height)

        if is_fullscreen:
            logger.debug(
                "Fullscreen app detected (%dx%d covering %dx%d screen) – hotkey suppressed.",
                window_width, window_height, screen_width, screen_height,
            )

        return is_fullscreen

    except Exception as exc:
        # If anything goes wrong, log it and don't block the hotkey.
        logger.debug("Fullscreen detection failed: %s", exc)
        return False
