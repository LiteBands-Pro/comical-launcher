"""Main application window. Owns the view-switching (connect screen <->
library) with a smooth fade transition, and the boot sequence: silently
ping the usage counter, then check whether we're already signed in to
itch.io to decide which screen to show first.

Note: signing in is no longer required for Rocky to actually download or
play (see itch_public.py) — it's kept purely as a sign-in step so you
have a rough count of returning accounts, separate from the raw launch
count usage_counter.py tracks. If you'd rather players skip straight to
the library without any sign-in wall, that's the earlier, simpler
version of this file — just call self.library_view.load_public() in
_boot() instead of showing self.connect_view first.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import QGraphicsOpacityEffect, QMainWindow, QStackedWidget

from ..core import discord_rpc, i18n, itch_api, itch_key, launcher_updater, usage_counter
from .connect_view import ConnectView
from .library_view import LibraryView
from .workers import TaskRunner


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(i18n.t("app.title"))
        self.resize(1000, 640)
        self.setMinimumSize(820, 560)

        self._boot_runner = None
        self._counter_runner = None
        self._idle_runner = None
        self._update_check_runner = None
        self._update_dialog = None  # kept alive on self; see _show_forced_update()

        # "Comical Launcher" is a brand name, not something that needs
        # translating (see i18n.STRINGS["app.title"] — it's identical in
        # all three languages), so the window title itself never needs
        # to be re-set on a language switch. Only layout direction does.
        i18n.add_listener(self._apply_layout_direction)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.connect_view = ConnectView()
        self.connect_view.connected.connect(self._on_connected)

        self.library_view = LibraryView()
        self.library_view.signed_out.connect(self._on_signed_out)
        self.library_view.request_hide_window.connect(self.hide)
        self.library_view.request_show_window.connect(self._show_and_focus)

        self.stack.addWidget(self.connect_view)
        self.stack.addWidget(self.library_view)

        self._boot()

    # ---------- boot ----------

    def _boot(self) -> None:
        # Fire-and-forget: never blocks the UI, never fails visibly. Shows
        # up on Discord as soon as the launcher opens; launch_game() swaps
        # it to "Playing <game>" and puts it back to idle when a game exits.
        self._idle_runner = TaskRunner(discord_rpc.set_idle)
        self._idle_runner.start()

        self._counter_runner = TaskRunner(usage_counter.record_launch)
        self._counter_runner.start()

        # Mandatory launcher-update check runs before anything else in
        # the boot sequence gets to matter — if a newer build exists,
        # _show_forced_update() blocks here (via a modal dialog) and
        # nothing below this point runs until the person has updated.
        # A failed *check* (no internet, manifest host down, etc.) is
        # NOT the same as "update required" — see launcher_updater's
        # module docstring — so it falls through to _continue_boot()
        # exactly like "no update found" does.
        self._update_check_runner = TaskRunner(
            launcher_updater.check_for_update,
            on_success=self._on_update_checked,
            on_error=self._on_update_check_failed,
        )
        self._update_check_runner.start()

    def _on_update_checked(self, info) -> None:
        if info is not None:
            self._show_forced_update(info)
            return
        self._continue_boot()

    def _on_update_check_failed(self, _message: str) -> None:
        self._continue_boot()

    def _show_forced_update(self, info) -> None:
        from .update_view import UpdateRequiredDialog

        # Kept on self, not a local variable, purely so it can't be
        # garbage-collected mid-download — the same reasoning as every
        # *Runner reference elsewhere in this class.
        self._update_dialog = UpdateRequiredDialog(info, parent=self)
        # exec() blocks here on a nested Qt event loop (background
        # QThreads still run fine underneath it). It only returns if the
        # update is actually applied, which itself ends the process via
        # os._exit(0) before control ever gets back here — so in normal
        # operation _continue_boot() below is simply never reached once
        # this branch is taken.
        self._update_dialog.exec()

    def _continue_boot(self) -> None:
        def check_status():
            key = itch_key.load_key()
            if not key:
                return None
            try:
                return itch_api.whoami(key)
            except Exception:
                return None

        self._boot_runner = TaskRunner(check_status, on_success=self._on_boot_status)
        self._boot_runner.start()

    def _on_boot_status(self, username) -> None:
        if username:
            self._switch_to(self.library_view, animate=False)
            self.library_view.load_for_session(username)
        else:
            self._switch_to(self.connect_view, animate=False)

    # ---------- view transitions ----------

    def _on_connected(self, username: str) -> None:
        self.library_view.load_for_session(username)
        self._switch_to(self.library_view, animate=True)

    def _on_signed_out(self) -> None:
        self._switch_to(self.connect_view, animate=True)

    def _switch_to(self, widget, animate: bool) -> None:
        self.stack.setCurrentWidget(widget)
        if not animate:
            return

        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", widget)
        animation.setDuration(220)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        # Keep a reference so it isn't garbage-collected mid-animation.
        widget._fade_animation = animation
        animation.start()

    def _show_and_focus(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    # ---------- language ----------

    def _apply_layout_direction(self) -> None:
        # main.py sets this once at startup based on the saved language,
        # before any widget exists; this is the live-switch counterpart,
        # called via i18n.add_listener() whenever the language changes
        # from library_view.py's settings page while the app is already
        # running. Re-flows every existing widget's layout immediately.
        from PySide6.QtWidgets import QApplication

        QApplication.instance().setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if i18n.is_rtl() else Qt.LayoutDirection.LeftToRight
        )
