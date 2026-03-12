# __main__.py – lets you run the package with "python -m spotlight_windows"
#
# When Python sees "python -m some_package", it looks for __main__.py inside
# that package and runs it. This file simply delegates to main.py.

from .main import main

main()
