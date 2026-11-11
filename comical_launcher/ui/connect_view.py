"""The itch.io connect screen. Shows a simple "Log in with itch.io" button
first; clicking it swaps in the embedded login page (ItchLoginView). No
API key is ever typed or pasted into this app — logging in with the real
account through itch.io's own page is what the embedded view is for, and
it removes the exact failure mode of a person copy-pasting a raw key
somewhere it shouldn't go.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import i18n, itch_api, itch_key
from .workers import TaskRunner


class ConnectView(QWidget):
    connected = Signal(str)  # emits the itch.io username on success

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._runner = None  # keeps the background TaskRunner alive while it runs
        self._login_view = None  # constructed lazily — see _ensure_login_view()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack)

        self.stack.addWidget(self._build_landing_page())

        i18n.add_listener(self.retranslate_ui)

    def retranslate_ui(self) -> None:
        self.title_label.setText(i18n.t("connect.title"))
        self.subtitle_label.setText(i18n.t("connect.subtitle"))
        self.login_btn.setText(i18n.t("connect.login_btn"))
        self.hint_label.setText(i18n.t("connect.hint"))
        # error_label is left alone here: it either shows nothing, or a
        # message _start_login()/_on_error() will re-set in the new
        # language next time it actually fires — retranslating a stale
        # error the person may have already dismissed mentally isn't
        # worth the extra state tracking it'd take to do "properly."

    # ---------- landing page (shown first, no Chromium cost paid yet) ----------

    def _build_landing_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(360)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(10)

        title = QLabel(i18n.t("connect.title"))
        title.setObjectName("Title")

        subtitle = QLabel(i18n.t("connect.subtitle"))
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)

        self.login_btn = QPushButton(i18n.t("connect.login_btn"))
        self.login_btn.clicked.connect(self._start_login)

        hint = QLabel(i18n.t("connect.hint"))
        hint.setObjectName("Hint")
        hint.setWordWrap(True)

        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorText")
        self.error_label.setWordWrap(True)

        self.title_label = title
        self.subtitle_label = subtitle
        self.hint_label = hint

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(12)
        card_layout.addWidget(self.login_btn)
        card_layout.addSpacing(6)
        card_layout.addWidget(hint)
        card_layout.addWidget(self.error_label)

        layout.addWidget(card)
        return page

    # ---------- embedded login (only built on first click) ----------

    def _ensure_login_view(self):
        if self._login_view is None:
            # Deferred import: QWebEngineView pulls in the Chromium
            # subprocess machinery, which is real startup weight — this
            # keeps that cost out of the app's boot path entirely for
            # anyone who's already connected or hasn't clicked yet.
            from .itch_login_view import ItchLoginView

            self._login_view = ItchLoginView()
            self._login_view.token_received.connect(self._on_token_received)
            self._login_view.login_failed.connect(self._on_login_failed)
            self._login_view.cancelled.connect(self._show_landing)
            self.stack.addWidget(self._login_view)
        return self._login_view

    def _start_login(self) -> None:
        from ..core import itch_oauth

        if not itch_oauth.is_configured():
            self.error_label.setText(i18n.t("connect.not_configured"))
            return

        self.error_label.setText("")
        view = self._ensure_login_view()
        self.stack.setCurrentWidget(view)
        view.start()

    def _show_landing(self) -> None:
        self.stack.setCurrentIndex(0)

    # ---------- token -> username, same local storage as before ----------

    def _on_token_received(self, token: str) -> None:
        def do_connect() -> str:
            username = itch_api.whoami(token)
            itch_key.save_key(token)
            return username

        self._runner = TaskRunner(do_connect, on_success=self._on_success, on_error=self._on_error)
        self._runner.start()

    def _on_success(self, username: str) -> None:
        self.connected.emit(username)

    def _on_error(self, message: str) -> None:
        self._show_landing()
        self.error_label.setText(message)

    def _on_login_failed(self, message: str) -> None:
        self._show_landing()
        self.error_label.setText(message)
