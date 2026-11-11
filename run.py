"""PyInstaller entry point.

Do not point PyInstaller's Analysis at comical_launcher/main.py directly --
run as a bare script, it has no parent package, so main.py's relative
imports (`from .core import discord_rpc`, `from .ui.main_window import
MainWindow`, ...) fail with:

    ImportError: attempted relative import with no known parent package

Importing the package here and calling its main() instead keeps
comical_launcher a proper package, so the relative imports inside it
resolve normally both when run with `python run.py` and once frozen.
"""

import sys

from comical_launcher.main import main

if __name__ == "__main__":
    sys.exit(main())
