"""Blocking "you must update" screen shown before the rest of the app
opens, when launcher_updater finds a newer build than this one is
running. There's no cancel/skip affordance anywhere in this dialog on
purpose — see launcher_updater.py's module docstring for why a launcher
update specifically isn't optional, unlike a game update
(ui/library_view.py's update prompt, which the person can decline).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from ..core import i18n, launcher_updater
from .smooth_progress_bar import SmoothProgressBar
from .workers import DownloadRunner


class UpdateRequiredDialog(QDialog):
    def __init__(self, info: launcher_updater.LauncherUpdateInfo, parent=None) -> None:
        super().__init__(parent)
        self._info = info
        self._download_runner = None
        self._downloaded_path = None
        self._has_custom_notes = bool(info.notes)

        self.setWindowTitle(i18n.t("update.window_title"))
        self.setModal(True)
        self.setFixedWidth(420)
        # No system close button and no [X]/Alt+F4 dismissal — see
        # closeEvent()/keyPressEvent() below. This screen only ever goes
        # away by finishing the update.
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)

        self.title_label = QLabel(i18n.t("update.heading", version=info.version))
        self.title_label.setObjectName("Title")
        self.title_label.setWordWrap(True)

        # Release notes come from GitHub's release body verbatim (see
        # launcher_updater.py) — they're whatever language the maintainer
        # wrote them in, not something this app can translate. Only the
        # *fallback* text (no notes written) is one of our own strings,
        # so only that half re-translates on a language switch.
        subtitle_text = info.notes or i18n.t("update.default_notes")
        self.status_label = QLabel(subtitle_text)
        self.status_label.setObjectName("Subtitle")
        self.status_label.setWordWrap(True)

        self.progress_bar = SmoothProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setVisible(False)

        self.action_btn = QPushButton(i18n.t("update.button_update_now"))
        self.action_btn.clicked.connect(self._start)

        layout.addWidget(self.title_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.action_btn)

        # Tracks which *kind* of status text is currently shown so
        # retranslate_ui() can re-render the right template rather than
        # guessing from the label's current text.
        self._status_kind = "notes"  # "notes" | "downloading" | "installing" | "failed"
        self._status_kwargs: dict = {}

        i18n.add_listener(self.retranslate_ui)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(i18n.t("update.window_title"))
        self.title_label.setText(i18n.t("update.heading", version=self._info.version))
        if self._status_kind == "notes":
            self.status_label.setText(self._info.notes or i18n.t("update.default_notes"))
        elif self._status_kind == "downloading":
            self.status_label.setText(i18n.t("update.status_downloading", **self._status_kwargs))
        elif self._status_kind == "installing":
            self.status_label.setText(i18n.t("update.status_installing"))
        elif self._status_kind == "failed":
            self.status_label.setText(i18n.t("update.status_failed", **self._status_kwargs))

        if not self.action_btn.isEnabled():
            # Currently downloading — button reads "Updating…" either way.
            self.action_btn.setText(i18n.t("update.button_updating"))
        elif self._status_kind == "failed":
            self.action_btn.setText(i18n.t("update.button_retry"))
        else:
            self.action_btn.setText(i18n.t("update.button_update_now"))

    # ---------- block every way out except finishing the update ----------

    def closeEvent(self, event) -> None:
        event.ignore()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    # ---------- download -> apply ----------

    def _start(self) -> None:
        self.action_btn.setEnabled(False)
        self.action_btn.setText(i18n.t("update.button_updating"))
        self.progress_bar.setVisible(True)
        self._status_kind = "downloading"
        self._status_kwargs = {"percent": 0}
        self.status_label.setText(i18n.t("update.status_downloading", percent=0))

        def do_download(on_progress) -> None:
            self._downloaded_path = launcher_updater.download_update(
                self._info, on_progress=on_progress
            )

        self._download_runner = DownloadRunner(
            do_download,
            on_progress=self._on_progress,
            on_success=self._on_downloaded,
            on_error=self._on_error,
        )
        self._download_runner.start()

    def _on_progress(self, downloaded: int, total: int, speed_bps: float, eta_secs: float) -> None:
        if total > 0:
            percent = int(downloaded / total * 100)
            self.progress_bar.set_value_animated(percent)
            self._status_kind = "downloading"
            self._status_kwargs = {"percent": percent}
            self.status_label.setText(i18n.t("update.status_downloading", percent=percent))

    def _on_downloaded(self) -> None:
        self._status_kind = "installing"
        self._status_kwargs = {}
        self.status_label.setText(i18n.t("update.status_installing"))
        # Never returns: this either hands off to the installer/new
        # binary and calls os._exit(0), or raises on a platform this
        # code doesn't know how to self-update. Either way, nothing
        # meaningful happens after this call in the success path.
        launcher_updater.apply_update_and_exit(self._downloaded_path)

    def _on_error(self, message: str) -> None:
        self._status_kind = "failed"
        self._status_kwargs = {"message": message}
        self.status_label.setText(i18n.t("update.status_failed", message=message))
        self.action_btn.setEnabled(True)
        self.action_btn.setText(i18n.t("update.button_retry"))
        self.progress_bar.setVisible(False)
