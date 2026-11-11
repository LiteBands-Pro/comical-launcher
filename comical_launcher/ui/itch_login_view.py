"""Embedded itch.io login. The person's actual itch.io account credentials
go directly into itch.io's own real login page — rendered inside this
app's own window via QWebEngineView, never in a separate browser process.
The password never touches this codebase at all; this view only ever
sees the OAuth token itch.io hands back at the end, which is the same
thing an external-browser OAuth flow would produce, just without ever
leaving the app.
"""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from ..core import i18n, itch_oauth


class ItchLoginView(QWidget):
    token_received = Signal(str)
    login_failed = Signal(str)
    cancelled = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._done = False
        # The Chromium subprocess behind QWebEngineView is real overhead
        # (memory + startup time) — it's only ever constructed the first
        # time someone actually clicks "Log in", not at app startup, so
        # the common case (already connected, or not logging in yet)
        # never pays for it. See ConnectView._ensure_login_view().

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(14, 10, 14, 10)
        # "itch.io" is the actual third-party service name, not UI copy —
        # it stays as-is in every language rather than going through i18n.t().
        toolbar_label = QLabel("itch.io")
        toolbar_label.setObjectName("Subtitle")
        self.cancel_btn = QPushButton(i18n.t("itch_login.cancel"))
        self.cancel_btn.setObjectName("GhostButton")
        self.cancel_btn.clicked.connect(self.cancelled.emit)
        toolbar.addWidget(toolbar_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self.cancel_btn)

        self.load_progress = QProgressBar()
        self.load_progress.setFixedHeight(3)
        self.load_progress.setTextVisible(False)

        self.webview = QWebEngineView()
        self.webview.urlChanged.connect(self._on_url_changed)
        self.webview.loadProgress.connect(self.load_progress.setValue)

        layout.addLayout(toolbar)
        layout.addWidget(self.load_progress)
        layout.addWidget(self.webview, stretch=1)

        i18n.add_listener(self.retranslate_ui)

    def retranslate_ui(self) -> None:
        self.cancel_btn.setText(i18n.t("itch_login.cancel"))
        # The embedded page itself (self.webview) is itch.io's own real
        # site, loaded live — its language is whatever itch.io serves,
        # entirely outside this app's control. Nothing to retranslate there.

    def start(self) -> None:
        self._done = False
        self.webview.load(QUrl(itch_oauth.authorize_url()))

    def _on_url_changed(self, url: QUrl) -> None:
        if self._done:
            return
        url_str = url.toString()
        if not itch_oauth.is_redirect(url_str):
            return

        self._done = True
        token = itch_oauth.extract_token(url_str)
        if token:
            self.token_received.emit(token)
        else:
            error = itch_oauth.extract_error(url_str) or "login was not completed"
            self.login_failed.emit(error)
