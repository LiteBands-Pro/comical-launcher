"""Lightweight, dependency-free translation system — English, French, and
Arabic. No Qt .ts/.qm pipeline (that would mean every contributor needs
`pyside6-lupdate`/`lrelease` on PATH just to build); this is a plain
Python dict lookup instead, which is easy to grep, easy to extend, and
needs nothing beyond what's already installed.

Usage from a UI file:

    from ..core import i18n
    label = QLabel(i18n.t("connect.title"))
    ...
    i18n.add_listener(self.retranslate_ui)   # re-called on every language switch

    def retranslate_ui(self) -> None:
        label.setText(i18n.t("connect.title"))

Static strings (button labels, titles) can just be re-set directly in
retranslate_ui(). Strings that depend on live state (an install status,
a username, a percentage) should have that state tracked in an instance
attribute alongside the key, so retranslate_ui() can re-render the
*current* state in the *new* language rather than re-showing a stale
English string that never gets updated until the state changes again —
see library_view.py's _status_key/_status_kwargs pattern for the idea.

Language choice is persisted next to the itch.io key (see itch_key.py's
config_dir()) so it survives restarts, and notifies registered listeners
immediately on change so already-open screens update without needing a
restart.

Arabic is RTL — is_rtl() is what main.py / main_window.py use to flip
QApplication's layout direction. Translations here are a solid first
pass, not professionally reviewed; if this ships to real Arabic/French-
speaking players, get a native speaker to proofread STRINGS before
launch — machine-quality wording in a shipped game launcher reads as
careless in a way it wouldn't in a dev tool.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import itch_key

DEFAULT_LANGUAGE = "en"

LANGUAGES = {
    "en": "English",
    "fr": "Français",
    "ar": "العربية",
}

RTL_LANGUAGES = {"ar"}

# key -> {lang_code: text}. Missing an entry for a language falls back to
# English, then to the raw key itself if even English is missing (see
# t() below) — so a half-translated new string never crashes, it just
# shows English until someone fills the gap in.

_current_language: str | None = None  # lazily loaded from disk on first get_language()
_listeners: list[Callable[[], None]] = []

STRINGS: dict[str, dict[str, str]] = {
    # ---- app-wide ----
    "app.title": {
        "en": "Comical Launcher",
        "fr": "Comical Launcher",
        "ar": "Comical Launcher",
    },
    # ---- connect screen ----
    "connect.title": {
        "en": "Connect itch.io",
        "fr": "Connexion à itch.io",
        "ar": "الاتصال بـ itch.io",
    },
    "connect.subtitle": {
        "en": "Sign in with your itch.io account to continue",
        "fr": "Connectez-vous avec votre compte itch.io pour continuer",
        "ar": "سجّل الدخول بحسابك على itch.io للمتابعة",
    },
    "connect.login_btn": {
        "en": "Log in with itch.io",
        "fr": "Se connecter avec itch.io",
        "ar": "تسجيل الدخول عبر itch.io",
    },
    "connect.hint": {
        "en": (
            "Connecting to itch.io helps us determine whether you have ownership of the game or not. "
            "We do not collect anything about you. "
            "Only itch.io can get your login details, Comical simply can't do that."
        ),
        "fr": (
            "La connexion à itch.io nous permet de vérifier si vous possédez le jeu. "
            "Nous ne collectons aucune information vous concernant. "
            "Seul itch.io reçoit vos identifiants de connexion ; Comical n'y a jamais accès."
        ),
        "ar": (
            "الاتصال بـ itch.io يساعدنا على التحقق مما إذا كنت تملك اللعبة أم لا. "
            "نحن لا نجمع أي معلومات عنك. "
            "بيانات تسجيل الدخول الخاصة بك تصل إلى itch.io فقط، ولا يمكن لتطبيق Comical الوصول إليها إطلاقًا."
        ),
    },
    "connect.not_configured": {
        "en": "itch.io login isn't configured yet — set CLIENT_ID in itch_oauth.py",
        "fr": "La connexion itch.io n'est pas encore configurée — définissez CLIENT_ID dans itch_oauth.py",
        "ar": "لم يتم إعداد تسجيل الدخول عبر itch.io بعد — يرجى ضبط CLIENT_ID في itch_oauth.py",
    },
    # ---- embedded itch.io login page chrome ----
    "itch_login.cancel": {
        "en": "Cancel",
        "fr": "Annuler",
        "ar": "إلغاء",
    },
    # ---- mandatory launcher update dialog ----
    "update.window_title": {
        "en": "Update Required",
        "fr": "Mise à jour requise",
        "ar": "التحديث مطلوب",
    },
    "update.heading": {
        "en": "A required update is available — v{version}",
        "fr": "Une mise à jour obligatoire est disponible — v{version}",
        "ar": "يتوفر تحديث مطلوب — الإصدار {version}",
    },
    "update.default_notes": {
        "en": "Please update to continue using Comical Launcher.",
        "fr": "Veuillez effectuer la mise à jour pour continuer à utiliser Comical Launcher.",
        "ar": "يرجى التحديث لمتابعة استخدام Comical Launcher.",
    },
    "update.button_update_now": {
        "en": "Update Now",
        "fr": "Mettre à jour",
        "ar": "تحديث الآن",
    },
    "update.button_updating": {
        "en": "Updating…",
        "fr": "Mise à jour en cours…",
        "ar": "جارٍ التحديث…",
    },
    "update.button_retry": {
        "en": "Retry",
        "fr": "Réessayer",
        "ar": "إعادة المحاولة",
    },
    "update.status_downloading": {
        "en": "Downloading update… {percent}%",
        "fr": "Téléchargement de la mise à jour… {percent} %",
        "ar": "جارٍ تنزيل التحديث… {percent}٪",
    },
    "update.status_installing": {
        "en": "Installing update — the app will restart…",
        "fr": "Installation de la mise à jour — l'application va redémarrer…",
        "ar": "جارٍ تثبيت التحديث — سيُعاد تشغيل التطبيق…",
    },
    "update.status_failed": {
        "en": "Update failed: {message}",
        "fr": "Échec de la mise à jour : {message}",
        "ar": "فشل التحديث: {message}",
    },
    # ---- sidebar nav ----
    "nav.library": {
        "en": "Library",
        "fr": "Bibliothèque",
        "ar": "المكتبة",
    },
    "nav.settings": {
        "en": "Settings",
        "fr": "Paramètres",
        "ar": "الإعدادات",
    },
    "nav.support": {
        "en": "Support",
        "fr": "Support",
        "ar": "المساعدة",
    },
    # ---- game status ----
    "status.checking": {
        "en": "Checking install status…",
        "fr": "Vérification de l'état d'installation…",
        "ar": "جارٍ التحقق من حالة التثبيت…",
    },
    "status.installed": {
        "en": "Installed",
        "fr": "Installé",
        "ar": "مثبَّت",
    },
    "status.not_installed": {
        "en": "Not installed",
        "fr": "Non installé",
        "ar": "غير مثبَّت",
    },
    "status.no_build": {
        "en": "No build available for this OS",
        "fr": "Aucune version disponible pour ce système d'exploitation",
        "ar": "لا يتوفر إصدار لهذا النظام",
    },
    "status.downloading": {
        "en": "Downloading… {percent}%",
        "fr": "Téléchargement… {percent} %",
        "ar": "جارٍ التنزيل… {percent}٪",
    },
    "status.install_failed": {
        "en": "Install failed — {message}",
        "fr": "Échec de l'installation — {message}",
        "ar": "فشل التثبيت — {message}",
    },
    "status.launching": {
        "en": "Launching…",
        "fr": "Lancement…",
        "ar": "جارٍ التشغيل…",
    },
    "status.launch_failed": {
        "en": "Launch failed — {message}",
        "fr": "Échec du lancement — {message}",
        "ar": "فشل التشغيل — {message}",
    },
    "status.uninstall_failed": {
        "en": "Uninstall failed: {message}",
        "fr": "Échec de la désinstallation : {message}",
        "ar": "فشل إلغاء التثبيت: {message}",
    },
    # ---- buttons ----
    "button.install": {
        "en": "Install",
        "fr": "Installer",
        "ar": "تثبيت",
    },
    "button.play": {
        "en": "Play",
        "fr": "Jouer",
        "ar": "تشغيل",
    },
    "button.update": {
        "en": "Update",
        "fr": "Mettre à jour",
        "ar": "تحديث",
    },
    "button.uninstall": {
        "en": "Uninstall",
        "fr": "Désinstaller",
        "ar": "إلغاء التثبيت",
    },
    "button.show": {
        "en": "Show",
        "fr": "Afficher",
        "ar": "إظهار",
    },
    "button.hide": {
        "en": "Hide",
        "fr": "Masquer",
        "ar": "إخفاء",
    },
    "button.sign_out": {
        "en": "Sign out",
        "fr": "Se déconnecter",
        "ar": "تسجيل الخروج",
    },
    # ---- optional game update ----
    "game_update.hint_available": {
        "en": "Update available — v{version}",
        "fr": "Mise à jour disponible — v{version}",
        "ar": "يتوفر تحديث — الإصدار {version}",
    },
    "game_update.hint_updating": {
        "en": "Updating to v{version}…",
        "fr": "Mise à jour vers la v{version}…",
        "ar": "جارٍ التحديث إلى الإصدار {version}…",
    },
    "game_update.hint_failed": {
        "en": "Update failed — {message}",
        "fr": "Échec de la mise à jour — {message}",
        "ar": "فشل التحديث — {message}",
    },
    "game_update.dialog_title": {
        "en": "Update Available",
        "fr": "Mise à jour disponible",
        "ar": "يتوفر تحديث",
    },
    "game_update.dialog_body": {
        "en": (
            "A new version of {game} is available (v{version}). "
            "Update now?{notes_line}\n\n"
            "You can keep playing the current version and update later "
            "from the Update button if you'd rather not update now."
        ),
        "fr": (
            "Une nouvelle version de {game} est disponible (v{version}). "
            "Mettre à jour maintenant ?{notes_line}\n\n"
            "Vous pouvez continuer à jouer avec la version actuelle et "
            "mettre à jour plus tard via le bouton Mettre à jour."
        ),
        "ar": (
            "يتوفر إصدار جديد من {game} (الإصدار {version}). "
            "هل تريد التحديث الآن؟{notes_line}\n\n"
            "يمكنك متابعة اللعب بالإصدار الحالي والتحديث لاحقًا عبر زر التحديث."
        ),
    },
    "game_update.notes_line": {
        "en": "\n\n{notes}",
        "fr": "\n\n{notes}",
        "ar": "\n\n{notes}",
    },
    # ---- uninstall confirmation ----
    "uninstall.dialog_title": {
        "en": "Uninstall {game}?",
        "fr": "Désinstaller {game} ?",
        "ar": "هل تريد إلغاء تثبيت {game}؟",
    },
    "uninstall.dialog_body": {
        "en": "This removes the installed files from this device. You can reinstall any time.",
        "fr": "Cela supprime les fichiers installés sur cet appareil. Vous pouvez réinstaller à tout moment.",
        "ar": "سيؤدي هذا إلى إزالة الملفات المثبَّتة من هذا الجهاز. يمكنك إعادة التثبيت في أي وقت.",
    },
    # ---- settings: itch.io card ----
    "settings.itch_title": {
        "en": "itch.io",
        "fr": "itch.io",
        "ar": "itch.io",
    },
    "settings.itch_not_connected": {
        "en": "Not connected",
        "fr": "Non connecté",
        "ar": "غير متصل",
    },
    "settings.itch_connected_as": {
        "en": "Connected as {username}",
        "fr": "Connecté en tant que {username}",
        "ar": "متصل باسم {username}",
    },
    "settings.itch_note": {
        "en": (
            "{game} downloads directly and doesn't require this — signing in "
            "just lets you keep an account connected to the launcher."
        ),
        "fr": (
            "{game} se télécharge directement et cela n'est pas nécessaire — se connecter "
            "permet simplement de garder un compte associé au launcher."
        ),
        "ar": (
            "يتم تنزيل {game} مباشرة ولا يتطلب ذلك تسجيل الدخول — تسجيل الدخول "
            "يتيح لك فقط ربط حساب بالبرنامج."
        ),
    },
    # ---- settings: device card ----
    "settings.device_title": {
        "en": "Device",
        "fr": "Appareil",
        "ar": "الجهاز",
    },
    "settings.device_subtitle": {
        "en": "Automatically identifies this install",
        "fr": "Identifie automatiquement cette installation",
        "ar": "يحدد هذا التثبيت تلقائيًا",
    },
    # ---- settings: language card ----
    "settings.language_title": {
        "en": "Language",
        "fr": "Langue",
        "ar": "اللغة",
    },
    "settings.language_subtitle": {
        "en": "Choose the language for the launcher",
        "fr": "Choisissez la langue du launcher",
        "ar": "اختر لغة البرنامج",
    },
    # ---- download progress ----
    "progress.speed_eta": {
        "en": "{speed:.2f} MB/s · {eta}",
        "fr": "{speed:.2f} Mo/s · {eta}",
        "ar": "{speed:.2f} م.ب/ث · {eta}",
    },
    "progress.eta_seconds_left": {
        "en": "{seconds}s left",
        "fr": "{seconds} s restantes",
        "ar": "{seconds} ث متبقية",
    },
    "progress.calculating": {
        "en": "calculating…",
        "fr": "calcul en cours…",
        "ar": "جارٍ الحساب…",
    },
    # ---- community & support ----
    "Community & Support": {
        "en": "Community & Support",
        "fr": "Communauté & Support",
        "ar": "المجتمع والدعم",
    },
    "join": {
        "en": "Join our Discord or check out our Instagram for updates and more!",
        "fr": "Rejoignez notre serveur Discord et n'oubliez pas de visiter notre Instagram pour plus d'info !",
        "ar": "انضم إلى ديسكورد أو تفقد إنستغرام لمتابعة التحديثات والمزيد!",
    },
}
def _language_path() -> Path:
    return itch_key.config_dir() / "language.local"


def _load_saved_language() -> str:
    path = _language_path()
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value in LANGUAGES:
            return value
    return DEFAULT_LANGUAGE


def get_language() -> str:
    global _current_language
    if _current_language is None:
        _current_language = _load_saved_language()
    return _current_language


def set_language(code: str) -> None:
    """Persists the choice and notifies every registered listener
    immediately — already-open screens re-render in the new language
    without needing a restart. A listener that raises is logged and
    skipped rather than allowed to break the others; one broken
    retranslate_ui() shouldn't leave every other screen stuck untranslated."""
    global _current_language
    if code not in LANGUAGES:
        raise ValueError(f"unknown language code: {code!r}")
    if code == get_language():
        return
    _current_language = code
    try:
        _language_path().write_text(code, encoding="utf-8")
    except OSError:
        pass  # persistence is a nicety; an unwritable config dir shouldn't block switching for this session
    _notify_listeners()


def is_rtl(code: str | None = None) -> bool:
    return (code or get_language()) in RTL_LANGUAGES


def add_listener(callback: Callable[[], None]) -> None:
    _listeners.append(callback)


def remove_listener(callback: Callable[[], None]) -> None:
    if callback in _listeners:
        _listeners.remove(callback)


def _notify_listeners() -> None:
    for callback in list(_listeners):
        try:
            callback()
        except Exception:
            pass


def t(key: str, **kwargs) -> str:
    """Looks up `key` in the current language, falling back to English,
    then to the raw key itself if even that's missing — so a typo'd or
    not-yet-added key shows up as visible junk in the UI instead of
    raising and taking the whole screen down with it."""
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(get_language()) or entry.get(DEFAULT_LANGUAGE) or key
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return text
