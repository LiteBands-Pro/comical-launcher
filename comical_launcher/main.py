"""Entry point: `python -m comical_launcher.main`"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from .core import discord_rpc, i18n
from .ui.main_window import MainWindow
from .ui.styles import STYLESHEET
from .ui.workers import wait_for_all_threads


def main() -> int:
    app = QApplication(sys.argv)
    # Fusion is a platform-independent style that fully respects QSS —
    # without this, the native Windows style (windowsvista/Windows11)
    # ignores the stylesheet's background for some widgets and paints its
    # own default behind them instead, which is what produces a black
    # box behind every label under a dark theme like this one.
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    app.setApplicationName("Comical Launcher")

    # Applied before any window is constructed so every widget lays out
    # mirrored from the start if the saved language is Arabic — flipping
    # this after widgets already exist works too (main_window.py does
    # that on a live language switch), but doing it here means the very
    # first frame is already correct instead of visibly re-flowing.
    app.setLayoutDirection(
        Qt.LayoutDirection.RightToLeft if i18n.is_rtl() else Qt.LayoutDirection.LeftToRight
    )

    # Prevents a crash (QThread destroyed while still running) if the
    # person closes the window while a network call or download is
    # in-flight — waits for background threads to actually finish first.
    app.aboutToQuit.connect(wait_for_all_threads)
    # Otherwise "Browsing the library" lingers on the profile after the
    # launcher itself has closed.
    app.aboutToQuit.connect(discord_rpc.clear_presence)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
