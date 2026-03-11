from __future__ import annotations

import sys

from spotlight_windows.app import SpotlightApp


def main() -> int:
    app = SpotlightApp()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
