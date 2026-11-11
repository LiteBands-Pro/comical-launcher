"""The main library screen: one game row (Rocky) with install/play, plus a
settings panel reachable from the sidebar nav.
"""

from __future__ import annotations

from pathlib import Path

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices

from ..core import game_config, game_updater, hwid, i18n, itch_key, itch_public, launcher
from .smooth_progress_bar import SmoothProgressBar
from .workers import DownloadRunner, TaskRunner


class LibraryView(QWidget):
    request_hide_window = Signal()
    request_show_window = Signal()
    signed_out = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._task_runner = None
        self._download_runner = None
        self._update_check_runner = None
        self._version_stamp_runner = None
        self._pending_game_update = None  # set once an update is found; cleared once applied
        self._current_username = None

        # Tracked so retranslate_ui() can re-render *current* state in the
        # new language instead of a frozen English string — same pattern
        # as update_view.py's _status_kind. "kwargs" is whatever t() needs.
        self._status_key = "status.checking"
        self._status_kwargs: dict = {}
        self._update_hint_key: str | None = None
        self._update_hint_kwargs: dict = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_content(), stretch=1)

        i18n.add_listener(self.retranslate_ui)

    def retranslate_ui(self) -> None:
        self.library_nav_btn.setText(i18n.t("nav.library"))
        self.settings_nav_btn.setText(i18n.t("nav.settings"))

        self.game_status_label.setText(i18n.t(self._status_key, **self._status_kwargs))
        mode = self.action_btn.property("mode") or "install"
        self.action_btn.setText(i18n.t("button.play" if mode == "play" else "button.install"))
        self.update_btn.setText(i18n.t("button.update"))
        self.uninstall_action.setText(i18n.t("button.uninstall"))

        if self._update_hint_key:
            self.update_hint_label.setText(i18n.t(self._update_hint_key, **self._update_hint_kwargs))

        self.itch_title_label.setText(i18n.t("settings.itch_title"))
        if self._current_username:
            self.itch_status_label.setText(
                i18n.t("settings.itch_connected_as", username=self._current_username)
            )
        else:
            self.itch_status_label.setText(i18n.t("settings.itch_not_connected"))
        self.itch_note_label.setText(i18n.t("settings.itch_note", game=game_config.GAME_TITLE))
        self.sign_out_btn.setText(i18n.t("button.sign_out"))

        self.device_title_label.setText(i18n.t("settings.device_title"))
        self.device_subtitle_label.setText(i18n.t("settings.device_subtitle"))
        self.hwid_toggle_btn.setText(i18n.t("button.hide" if self._hwid_revealed else "button.show"))

        self.language_title_label.setText(i18n.t("settings.language_title"))
        self.language_subtitle_label.setText(i18n.t("settings.language_subtitle"))

    # ---------- sidebar ----------

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(200)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 20)
        layout.setSpacing(16)

        self.username_label = QLabel("—")
        self.username_label.setStyleSheet("font-weight: 600;")

        self.library_nav_btn = QPushButton(i18n.t("nav.library"))
        self.library_nav_btn.setObjectName("NavButton")
        self.library_nav_btn.setCheckable(True)
        self.library_nav_btn.setChecked(True)
        self.library_nav_btn.clicked.connect(lambda: self._switch_tab(0))

        self.settings_nav_btn = QPushButton(i18n.t("nav.settings"))
        self.settings_nav_btn.setObjectName("NavButton")
        self.settings_nav_btn.setCheckable(True)
        self.settings_nav_btn.clicked.connect(lambda: self._switch_tab(1))

        self.support_nav_btn = QPushButton(i18n.t("nav.support"))
        self.support_nav_btn.setObjectName("NavButton")
        self.support_nav_btn.setCheckable(True)
        self.support_nav_btn.clicked.connect(lambda: self._switch_tab(2))

        layout.addWidget(self.username_label)
        layout.addWidget(self.library_nav_btn)
        layout.addWidget(self.settings_nav_btn)
        layout.addWidget(self.support_nav_btn)
        layout.addStretch(1)

        return sidebar

    def _switch_tab(self, index: int) -> None:
        self.library_nav_btn.setChecked(index == 0)
        self.settings_nav_btn.setChecked(index == 1)
        self.support_nav_btn.setChecked(index == 2)
        self.content_stack.setCurrentIndex(index)

    # ---------- content ----------

    def _build_content(self) -> QWidget:
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(28, 28, 28, 28)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self._build_library_page())
        self.content_stack.addWidget(self._build_settings_page())
        self.content_stack.addWidget(self._build_support_page())
        wrapper_layout.addWidget(self.content_stack)

        return wrapper

    def _build_library_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        row = QFrame()
        row.setObjectName("Card")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(18, 18, 18, 18)
        row_layout.setSpacing(18)

        self.art_label = QLabel()
        self.art_label.setObjectName("GameArt")
        self.art_label.setFixedSize(84, 84)
        self.art_label.setScaledContents(True)
        self.art_label.setStyleSheet(
            "background-color: #242529; border: 1px solid #3a3b40; border-radius: 8px;"
        )

        meta = QVBoxLayout()
        self.game_title_label = QLabel(game_config.GAME_TITLE)
        self.game_title_label.setObjectName("GameTitle")
        self.game_status_label = QLabel(i18n.t("status.checking"))
        self.game_status_label.setObjectName("GameStatus")

        self.progress_bar = SmoothProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setVisible(False)

        self.progress_stats_label = QLabel("")
        self.progress_stats_label.setObjectName("Hint")
        self.progress_stats_label.setVisible(False)

        # Purely informational — never blocks Play. See _on_game_update_checked().
        self.update_hint_label = QLabel("")
        self.update_hint_label.setObjectName("Hint")
        self.update_hint_label.setVisible(False)

        meta.addWidget(self.game_title_label)
        meta.addWidget(self.game_status_label)
        meta.addWidget(self.update_hint_label)
        meta.addSpacing(6)
        meta.addWidget(self.progress_bar)
        meta.addWidget(self.progress_stats_label)

        self.action_btn = QPushButton(i18n.t("button.install"))
        # A fixed width clips "Play"/"Install" fine in English but cuts
        # off longer translations (e.g. French "Désinstaller" in the menu,
        # or "Mettre à jour" on the update button below) — a minimum
        # width keeps buttons a consistent size for short labels while
        # letting them grow to fit longer ones instead of truncating.
        self.action_btn.setMinimumWidth(110)
        self.action_btn.clicked.connect(self._on_action_clicked)

        # Only shown once a game update is actually available — see
        # _on_game_update_checked(). Play always stays enabled alongside
        # this; updating is never required to keep playing.
        self.update_btn = QPushButton(i18n.t("button.update"))
        self.update_btn.setObjectName("GhostButton")
        self.update_btn.setMinimumWidth(90)
        self.update_btn.setVisible(False)
        self.update_btn.clicked.connect(self._start_game_update)

        self.more_btn = QToolButton()
        self.more_btn.setText("⋯")
        self.more_btn.setObjectName("GhostButton")
        self.more_btn.setFixedSize(34, 34)
        self.more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_btn.setVisible(False)  # only shown once something is installed

        more_menu = QMenu(self.more_btn)
        self.uninstall_action = more_menu.addAction(i18n.t("button.uninstall"))
        self.uninstall_action.triggered.connect(self._on_uninstall_clicked)
        self.more_btn.setMenu(more_menu)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(6)
        actions_row.addWidget(self.action_btn)
        actions_row.addWidget(self.update_btn)
        actions_row.addWidget(self.more_btn)

        row_layout.addWidget(self.art_label)
        row_layout.addLayout(meta, stretch=1)
        row_layout.addLayout(actions_row)
        row_layout.setAlignment(actions_row, Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(row)
        return page

    def _build_support_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(16)

        # --- Socials Card ---
        social_card = QFrame()
        social_card.setObjectName("Card")
        social_layout = QVBoxLayout(social_card)
        social_layout.setContentsMargins(20, 20, 20, 20)
        social_layout.setSpacing(12)

        social_title = QLabel(i18n.t("Community & Support"))
        social_title.setObjectName("Title")
        
        social_subtitle = QLabel(i18n.t("join"))
        social_subtitle.setObjectName("Subtitle")
        social_subtitle.setWordWrap(True)

        # Buttons layout
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)

        discord_btn = QPushButton("Discord")
        discord_btn.setObjectName("GhostButton")
        discord_btn.setMinimumHeight(36)
        discord_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://discord.gg/https://discord.gg/dwg9gbrWtx")))

        instagram_btn = QPushButton("Instagram")
        instagram_btn.setObjectName("GhostButton")
        instagram_btn.setMinimumHeight(36)
        instagram_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://instagram.com/comicalgames")))

        buttons_row.addWidget(discord_btn)
        buttons_row.addWidget(instagram_btn)
        buttons_row.addStretch(1)

        social_layout.addWidget(social_title)
        social_layout.addWidget(social_subtitle)
        social_layout.addSpacing(4)
        social_layout.addLayout(buttons_row)

        layout.addWidget(social_card)
        return page


    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(16)

        itch_card = QFrame()
        itch_card.setObjectName("Card")
        itch_layout = QVBoxLayout(itch_card)
        itch_layout.setContentsMargins(20, 20, 20, 20)
        itch_layout.setSpacing(8)

        itch_title = QLabel(i18n.t("settings.itch_title"))
        itch_title.setObjectName("Title")
        self.itch_status_label = QLabel(i18n.t("settings.itch_not_connected"))
        self.itch_status_label.setObjectName("Subtitle")

        itch_note = QLabel(i18n.t("settings.itch_note", game=game_config.GAME_TITLE))
        itch_note.setObjectName("Hint")
        itch_note.setWordWrap(True)

        self.sign_out_btn = QPushButton(i18n.t("button.sign_out"))
        self.sign_out_btn.setObjectName("GhostButton")
        self.sign_out_btn.clicked.connect(self._on_sign_out)

        self.itch_title_label = itch_title
        self.itch_note_label = itch_note

        itch_layout.addWidget(itch_title)
        itch_layout.addWidget(self.itch_status_label)
        itch_layout.addWidget(itch_note)
        itch_layout.addSpacing(6)
        itch_layout.addWidget(self.sign_out_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        device_card = QFrame()
        device_card.setObjectName("Card")
        device_layout = QVBoxLayout(device_card)
        device_layout.setContentsMargins(20, 20, 20, 20)
        device_layout.setSpacing(8)

        device_title = QLabel(i18n.t("settings.device_title"))
        device_title.setObjectName("Title")
        device_subtitle = QLabel(i18n.t("settings.device_subtitle"))
        device_subtitle.setObjectName("Subtitle")

        self._hwid_value = hwid.get_hwid()
        self._hwid_revealed = False

        self.hwid_display = QLineEdit(self._masked_hwid())
        self.hwid_display.setReadOnly(True)

        self.hwid_toggle_btn = QPushButton(i18n.t("button.show"))
        self.hwid_toggle_btn.setObjectName("GhostButton")
        self.hwid_toggle_btn.setMinimumWidth(78)
        self.hwid_toggle_btn.clicked.connect(self._toggle_hwid_visibility)

        hwid_row = QHBoxLayout()
        hwid_row.addWidget(self.hwid_display, stretch=1)
        hwid_row.addWidget(self.hwid_toggle_btn)

        device_layout.addWidget(device_title)
        device_layout.addWidget(device_subtitle)
        device_layout.addLayout(hwid_row)

        self.device_title_label = device_title
        self.device_subtitle_label = device_subtitle

        layout.addWidget(itch_card)
        layout.addWidget(device_card)
        layout.addWidget(self._build_language_card())
        return page

    def _build_language_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(8)

        self.language_title_label = QLabel(i18n.t("settings.language_title"))
        self.language_title_label.setObjectName("Title")
        self.language_subtitle_label = QLabel(i18n.t("settings.language_subtitle"))
        self.language_subtitle_label.setObjectName("Subtitle")

        self.language_combo = QComboBox()
        self.language_combo.setObjectName("LanguageCombo")
        self.language_combo.setMinimumHeight(36)
        self.language_combo.setMinimumWidth(220)
        self.language_combo.setMaximumWidth(320)
        self.language_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.language_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.language_combo.view().setMinimumWidth(220)
        # Language names are shown in their own script regardless of the
        # currently active UI language (their "autonym") — that's the
        # standard convention (see e.g. any OS language picker): someone
        # who doesn't read the current language still needs to recognize
        # their own to switch to it, so these three labels never go
        # through i18n.t() themselves.
        for code, label in i18n.LANGUAGES.items():
            self.language_combo.addItem(label, userData=code)
        current_index = list(i18n.LANGUAGES.keys()).index(i18n.get_language())
        self.language_combo.setCurrentIndex(current_index)
        self.language_combo.currentIndexChanged.connect(self._on_language_selected)

        card_layout.addWidget(self.language_title_label)
        card_layout.addWidget(self.language_subtitle_label)
        card_layout.addSpacing(4)
        # AlignLeading (not AlignLeft) so this correctly sits on the
        # "start" side of the card in RTL layouts (Arabic) too, instead
        # of always pinning to the physical left.
        card_layout.addWidget(self.language_combo, alignment=Qt.AlignmentFlag.AlignLeading)
        return card

    def _on_language_selected(self, index: int) -> None:
        code = self.language_combo.itemData(index)
        if code:
            i18n.set_language(code)

    def _masked_hwid(self) -> str:
        return "•" * 16

    def _toggle_hwid_visibility(self) -> None:
        self._hwid_revealed = not self._hwid_revealed
        if self._hwid_revealed:
            self.hwid_display.setText(self._hwid_value)
            self.hwid_toggle_btn.setText(i18n.t("button.hide"))
        else:
            self.hwid_display.setText(self._masked_hwid())
            self.hwid_toggle_btn.setText(i18n.t("button.show"))

    # ---------- status/hint text helpers (state + language aware) ----------

    def _set_status(self, key: str, **kwargs) -> None:
        self._status_key = key
        self._status_kwargs = kwargs
        self.game_status_label.setText(i18n.t(key, **kwargs))

    def _set_update_hint(self, key: str | None, **kwargs) -> None:
        self._update_hint_key = key
        self._update_hint_kwargs = kwargs
        if key:
            self.update_hint_label.setText(i18n.t(key, **kwargs))

    # ---------- lifecycle ----------

    def load_for_session(self, username: str) -> None:
        self._current_username = username
        self.username_label.setText(username)
        self.itch_status_label.setText(i18n.t("settings.itch_connected_as", username=username))
        self._switch_tab(0)
        self._load_game_info()
        self._refresh_install_state()

    def _load_game_info(self) -> None:
        # Best-effort only: the title already shows correctly from
        # game_config.GAME_TITLE, this just fills in cover art if itch.io's
        # public page data has one. Silent on failure, same as before.
        def fetch():
            return itch_public.get_game_metadata(game_config.GAME_URL)

        self._task_runner = TaskRunner(fetch, on_success=self._apply_game_info, on_error=lambda _: None)
        self._task_runner.start()

    def _apply_game_info(self, info) -> None:
        if info.title:
            self.game_title_label.setText(info.title)
        if info.cover_url:
            self._load_cover_art(info.cover_url)

    def _load_cover_art(self, url: str) -> None:
        def fetch_bytes():
            import requests

            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            return resp.content

        def apply(data: bytes) -> None:
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                self.art_label.setPixmap(pixmap)

        self._task_runner = TaskRunner(fetch_bytes, on_success=apply, on_error=lambda _: None)
        self._task_runner.start()

    def _refresh_install_state(self) -> None:
        installed = launcher.is_installed(game_config.GAME_SLUG)
        self.more_btn.setVisible(installed)
        if installed:
            self._set_status("status.installed")
            self.action_btn.setText(i18n.t("button.play"))
            self.action_btn.setProperty("mode", "play")
            self._check_for_game_update()
        else:
            self._set_status("status.not_installed")
            self.action_btn.setText(i18n.t("button.install"))
            self.action_btn.setProperty("mode", "install")
            self.update_hint_label.setVisible(False)
            self._set_update_hint(None)
            self.update_btn.setVisible(False)
            self._pending_game_update = None

    # ---------- game update (optional — never blocks Play) ----------

    def _check_for_game_update(self) -> None:
        manifest_url = game_config.GAME_VERSION_MANIFEST_URL
        if not manifest_url:
            return

        def do_check():
            return game_updater.check_for_update(manifest_url, game_config.GAME_SLUG)

        # on_error is a no-op on purpose: this check is a courtesy, and a
        # transient network failure here shouldn't interrupt anyone or
        # show up as an error about a feature they didn't ask to use.
        self._update_check_runner = TaskRunner(
            do_check, on_success=self._on_game_update_checked, on_error=lambda _: None
        )
        self._update_check_runner.start()

    def _on_game_update_checked(self, info) -> None:
        if info is None:
            return

        self._pending_game_update = info
        self._set_update_hint("game_update.hint_available", version=info.version)
        self.update_hint_label.setVisible(True)
        self.update_btn.setVisible(True)

        notes_line = i18n.t("game_update.notes_line", notes=info.notes) if info.notes else ""
        reply = QMessageBox.question(
            self,
            i18n.t("game_update.dialog_title"),
            i18n.t(
                "game_update.dialog_body",
                game=game_config.GAME_TITLE,
                version=info.version,
                notes_line=notes_line,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_game_update()
        # If they said No: nothing else happens here. The hint label and
        # Update button stay visible so they can update whenever they
        # want, but Play is untouched and nothing is forced.

    def _start_game_update(self) -> None:
        upload = game_config.recommended_upload()
        if not upload or self._pending_game_update is None:
            return

        self.action_btn.setEnabled(False)
        self.update_btn.setEnabled(False)
        self._set_update_hint("game_update.hint_updating", version=self._pending_game_update.version)
        self._run_download_and_install(
            upload,
            on_success=self._on_game_update_success,
            on_error=self._on_game_update_error,
            stamp_version=self._pending_game_update.version,
        )

    def _on_game_update_success(self) -> None:
        self._pending_game_update = None
        self.update_hint_label.setVisible(False)
        self._set_update_hint(None)
        self.update_btn.setVisible(False)
        self.update_btn.setEnabled(True)
        self._on_install_success()  # resets action_btn/progress bar back to "Play"/idle

    def _on_game_update_error(self, message: str) -> None:
        self.update_btn.setEnabled(True)
        self._set_update_hint("game_update.hint_failed", message=message)
        self._on_install_error(message)

    # ---------- install / play ----------

    def _on_action_clicked(self) -> None:
        mode = self.action_btn.property("mode") or "install"
        if mode == "install":
            self._start_install()
        else:
            self._start_play()

    def _start_install(self) -> None:
        upload = game_config.recommended_upload()
        if not upload:
            self._set_status("status.no_build")
            return

        self.action_btn.setEnabled(False)
        self._set_status("status.downloading", percent=0)
        self.progress_bar.setVisible(True)
        self.progress_stats_label.setVisible(True)
        self.progress_bar.setValue(0)

        # A fresh install has no update to compare against yet, but if a
        # manifest is configured, stamp whatever it currently says as
        # "installed" — otherwise game_updater.check_for_update() would
        # have nothing to compare future checks against (see its
        # docstring on why "nothing recorded" means "stay silent").
        self._run_download_and_install(
            upload,
            on_success=self._on_install_success,
            on_error=self._on_install_error,
            stamp_version=None,
        )

    def _run_download_and_install(
        self, upload, on_success, on_error, stamp_version: str | None
    ) -> None:
        """Shared by both a fresh install and a game-update — downloading
        and encrypting a build in place is exactly the same operation
        either way; only what happens right after differs (button/label
        state, and which version gets stamped as installed)."""

        def do_download(on_progress) -> None:
            import tempfile

            machine_id = hwid.get_hwid()
            staging = Path(tempfile.gettempdir()) / f"cl-dl-{game_config.GAME_SLUG}.bin"

            itch_public.download_upload_public(
                game_config.GAME_URL, upload.upload_id, staging, on_progress=on_progress
            )

            dest_dir = launcher.install_root() / game_config.GAME_SLUG
            launcher.create_protected_dir(dest_dir)
            dest_file = dest_dir / upload.binary_filename

            from ..core import crypto

            crypto.encrypt_file(staging, dest_file, machine_id)
            crypto.secure_delete(staging)

            version_to_stamp = stamp_version or self._fetch_manifest_version()
            if version_to_stamp:
                game_updater.save_installed_version(game_config.GAME_SLUG, version_to_stamp)

        self._download_runner = DownloadRunner(
            do_download,
            on_progress=self._on_download_progress,
            on_success=on_success,
            on_error=on_error,
        )
        self._download_runner.start()

    def _fetch_manifest_version(self) -> str | None:
        """Best-effort synchronous lookup of the manifest's current
        version, called from the download worker thread (not the UI
        thread) right after a fresh install finishes — safe here since
        it's plain `requests`, not a Qt call. Silent on any failure: a
        missing version stamp just means the next update check has
        nothing to compare against yet (see game_updater's docstring),
        not a broken install."""
        manifest_url = game_config.GAME_VERSION_MANIFEST_URL
        if not manifest_url:
            return None
        try:
            resp = requests.get(manifest_url, timeout=15)
            resp.raise_for_status()
            return resp.json().get("version")
        except (requests.RequestException, ValueError):
            return None

    def _on_download_progress(self, downloaded: int, total: int, speed_bps: float, eta_secs: float) -> None:
        if total > 0:
            percent = int(downloaded / total * 100)
            self.progress_bar.set_value_animated(percent)
            self._set_status("status.downloading", percent=percent)
        speed_mb = speed_bps / 1_000_000
        eta_text = (
            i18n.t("progress.eta_seconds_left", seconds=int(eta_secs))
            if eta_secs > 0
            else i18n.t("progress.calculating")
        )
        # Not retranslated live if the language changes mid-download (see
        # i18n.py's module docstring) — the next progress tick a moment
        # later re-renders it correctly anyway, so it self-corrects fast
        # enough that tracking extra state for it isn't worth the cost.
        self.progress_stats_label.setText(i18n.t("progress.speed_eta", speed=speed_mb, eta=eta_text))

    def _on_install_success(self) -> None:
        self._set_status("status.installed")
        self.action_btn.setText(i18n.t("button.play"))
        self.action_btn.setProperty("mode", "play")
        self.action_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_stats_label.setVisible(False)
        # Fresh installs used to leave the "⋯" (uninstall) menu hidden
        # until the app was restarted, because only _refresh_install_state()
        # (called on load_for_session()) ever showed it. Show it the
        # moment an install actually finishes so it's usable right away.
        self.more_btn.setVisible(True)

    def _on_install_error(self, message: str) -> None:
        self._set_status("status.install_failed", message=message)
        self.action_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_stats_label.setVisible(False)

    def _start_play(self) -> None:
        self.action_btn.setEnabled(False)
        self._set_status("status.launching")

        def do_launch():
            launcher.launch_game(
                game_config.GAME_SLUG,
                game_config.recommended_upload().binary_filename,
                game_config.GAME_TITLE,
                on_before_launch=self.request_hide_window.emit,
                on_after_launch=self.request_show_window.emit,
            )

        self._task_runner = TaskRunner(
            do_launch,
            on_success=lambda _: self._on_play_finished(None),
            on_error=self._on_play_finished,
        )
        self._task_runner.start()

    def _on_play_finished(self, error_message) -> None:
        self.action_btn.setEnabled(True)
        if error_message:
            self._set_status("status.launch_failed", message=error_message)
        else:
            self._set_status("status.installed")

    # ---------- uninstall (3-dot menu — recovery path for a corrupted install) ----------

    def _on_uninstall_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            i18n.t("uninstall.dialog_title", game=game_config.GAME_TITLE),
            i18n.t("uninstall.dialog_body"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            launcher.uninstall_game(game_config.GAME_SLUG)
        except OSError as exc:
            self._set_status("status.uninstall_failed", message=str(exc))
            return
        self._refresh_install_state()

    # ---------- sign out ----------

    def _on_sign_out(self) -> None:
        itch_key.clear_key()
        self.signed_out.emit()
