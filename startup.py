# startup.py – adds or removes the launcher from Windows startup.
#
# Run this script once to make the launcher start automatically with Windows:
#   python startup.py --install
#
# To stop it from starting automatically:
#   python startup.py --uninstall
#
# How it works:
# Windows runs all programs listed under the registry key:
#   HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
# Each value in that key is a program path that Windows launches at login.
# We add/remove one entry there.
#
# winreg is a standard library module on Windows that lets Python read and
# write the Windows Registry (a hierarchical database of settings).

import sys
import winreg  # Windows-only standard library module

# The registry path that Windows reads at startup
STARTUP_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

# The name of our entry in the registry (any descriptive string)
APP_NAME = "SpotlightLauncher"


def get_launch_command() -> str:
    """Build the command Windows will run at startup.

    We use 'pythonw.exe' instead of 'python.exe' so the app starts
    without a black console window appearing in the background.
    """
    # sys.executable is the path to the Python interpreter running this script.
    # Replace python.exe with pythonw.exe to suppress the console window.
    python_exe = sys.executable.replace("python.exe", "pythonw.exe")

    # __file__ is the path to this script. We use it to locate the package.
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(script_dir, "src")

    # We run "pythonw -m spotlight_windows" with the src/ directory on the
    # Python path so it can find the package.
    return f'"{python_exe}" -m spotlight_windows'


def install() -> None:
    """Add the launcher to Windows startup via the registry."""
    command = get_launch_command()

    # winreg.OpenKey opens an existing registry key for writing.
    # HKEY_CURRENT_USER (HKCU) applies only to the current user – no admin needed.
    # KEY_SET_VALUE permission allows writing values.
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        STARTUP_REGISTRY_KEY,
        0,                         # reserved, always 0
        winreg.KEY_SET_VALUE,
    ) as key:
        # SetValueEx writes a string value into the registry key.
        # REG_SZ means "regular string" (as opposed to expandable strings, etc.)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)

    print(f"✓ Installed. '{APP_NAME}' will start with Windows.")
    print(f"  Command: {command}")
    print(f"  Registry: HKCU\\{STARTUP_REGISTRY_KEY}")


def uninstall() -> None:
    """Remove the launcher from Windows startup."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            STARTUP_REGISTRY_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            # DeleteValue removes a named value from an open registry key.
            winreg.DeleteValue(key, APP_NAME)
        print(f"✓ Uninstalled. '{APP_NAME}' will no longer start with Windows.")

    except FileNotFoundError:
        # The key didn't exist – already uninstalled.
        print(f"'{APP_NAME}' was not found in the startup registry (already removed).")


def status() -> None:
    """Check whether the launcher is registered for startup."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            STARTUP_REGISTRY_KEY,
            0,
            winreg.KEY_READ,
        ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            print(f"✓ Startup is ENABLED.")
            print(f"  Command: {value}")
    except FileNotFoundError:
        print("✗ Startup is DISABLED (not registered).")


if __name__ == "__main__":
    # sys.argv is the list of command-line arguments.
    # sys.argv[0] is always the script name; [1] is the first user argument.
    if len(sys.argv) < 2:
        print("Usage: python startup.py --install | --uninstall | --status")
        sys.exit(1)

    arg = sys.argv[1].lower()

    if arg == "--install":
        install()
    elif arg == "--uninstall":
        uninstall()
    elif arg == "--status":
        status()
    else:
        print(f"Unknown argument: {arg}")
        print("Usage: python startup.py --install | --uninstall | --status")
        sys.exit(1)
