# -*- mode: python ; coding: utf-8 -*-
#
# Build with:
#     pyinstaller comical_launcher.spec
#
# Replaces the old one-liner in build.txt. The app only ever imports
# PySide6.QtCore, QtGui, QtWidgets, and QtWebEngineWidgets (grep the repo
# and that's genuinely all of it — networking goes through `requests`, not
# QtNetwork). PySide6's wheel ships dozens of other Qt modules (3D, Charts,
# Multimedia, Sql, Pdf, Bluetooth, Nfc, Positioning, unused Quick/QML
# stacks, TextToSpeech, etc.) that PyInstaller will happily drag in anyway
# unless told not to — that's most of the unnecessary size. QtWebEngine
# itself is unavoidably large (it embeds a Chromium build for the itch.io
# login page) and can't be trimmed away without dropping that feature.
#
# Output is onedir (a folder), not onefile. onefile re-extracts the whole
# app -- including the Chromium payload behind QtWebEngine -- into a temp
# dir on every launch, which is slow with a dependency this big. onedir
# starts instantly and is what Inno Setup will package below. If you'd
# rather ship one exe, add EXE(..., exclude_binaries=False) instead of
# COLLECT and drop the "onedir" bits.

import sys

block_cipher = None

# --- PySide6 submodules never imported anywhere in this codebase ----------
#
# IMPORTANT: none of these can be a module QtWebEngineWidgets secretly
# needs. PyInstaller's own PySide6 hook force-adds certain modules as
# hidden imports specifically because QWebEngineView depends on them
# internally (even though itch_login_view.py never imports them itself) --
# and a manual `excludes=` entry always overrides a hook's hidden-import
# request. Get this wrong and QWebEngineView fails to construct at
# runtime, but silently, since this is a console=False build: the login
# button will hover/highlight fine (the rest of the UI is unaffected) but
# clicking it will appear to do nothing at all, with no error visible
# anywhere. QtOpenGL, QtOpenGLWidgets, and QtPositioning were removed from
# this list for exactly that reason -- they cost a few MB, but excluding
# them broke the embedded itch.io login.
UNUSED_PYSIDE6_MODULES = [
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "PySide6.QtBluetooth", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtLocation",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth", "PySide6.QtNfc", "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtSql", "PySide6.QtStateMachine",
    "PySide6.QtTest", "PySide6.QtTextToSpeech", "PySide6.QtWebSockets",
    "PySide6.QtXml", "PySide6.QtSvgWidgets", "PySide6.QtSpatialAudio",
    "PySide6.QtQuick3D", "PySide6.QtQuickControls2", "PySide6.QtQuickTest",
    "PySide6.QtUiTools",
    "PySide6.QtSvg",
]

# --- stdlib / stray-dependency cruft that sometimes gets hoovered in -------
# NOTE: don't add "distutils" here. setuptools ships a vendored copy and
# PyInstaller's own hook-distutils.py aliases the real module to it during
# analysis; if we've already force-excluded "distutils" ourselves that alias
# step finds it pre-marked as ExcludedModule and crashes with:
#   ValueError: Target module "distutils" already imported as
#   ExcludedModule('distutils',)
# Excluding it is unnecessary anyway -- distutils is tiny and setuptools'
# hook keeps only the vendored copy in the build regardless.
OTHER_EXCLUDES = [
    "tkinter", "test", "unittest", "lib2to3", "pydoc_data",
    "numpy", "matplotlib", "pandas", "scipy", "PIL",
]

a = Analysis(
    # NOT comical_launcher/main.py -- run as a bare script it has no parent
    # package, so its relative imports (`from .core import ...`) blow up
    # with "attempted relative import with no known parent package".
    # run.py imports the package properly instead.
    ["run.py"],
    pathex=["."],
    binaries=[],
    datas=[("icons/icon.png", "icons")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=UNUSED_PYSIDE6_MODULES + OTHER_EXCLUDES,
    noarchive=False,
    cipher=block_cipher,
)

# ---------------------------------------------------------------------------
# The `excludes=` list above only stops PyInstaller from following Python
# imports. QtWebEngine's locale packs and Qt's image-format plugins are
# plugin *binaries*, not importable modules, so they slip in regardless and
# have to be filtered out of the already-collected file lists instead.
# ---------------------------------------------------------------------------

KEEP_LOCALE = "qtwebengine_locales/en-us.pak"          # keep English only
DROP_IMAGEFORMAT_PLUGINS = (                            # formats we never load
    "qsvg", "qtga", "qtiff", "qwbmp", "qwebp", "qgif", "qicns",
)

def _is_unwanted_locale(dest_path: str) -> bool:
    norm = dest_path.replace("\\", "/").lower()
    return "qtwebengine_locales" in norm and not norm.endswith(KEEP_LOCALE)

def _is_unwanted_imageformat_plugin(dest_path: str) -> bool:
    norm = dest_path.replace("\\", "/").lower()
    if "imageformats" not in norm:
        return False
    return any(name in norm for name in DROP_IMAGEFORMAT_PLUGINS)

# app.setStyle("Fusion") in main.py forces Fusion, which is compiled into
# QtWidgets itself, not a plugin -- so the native-look style plugins
# (windowsvista, windows11, ...) PyInstaller stages by default are never
# actually reachable at runtime. Same story for the touch/tablet "generic"
# input plugins and platform input-context plugins (IME support for CJK
# text entry) -- nothing in this app's UI needs either.
DROP_PLUGIN_DIRS = ("styles", "generic", "platforminputcontexts")

def _is_unwanted_plugin_binary(dest_path: str) -> bool:
    norm = dest_path.replace("\\", "/").lower()
    return any(f"/plugins/{d}/" in norm for d in DROP_PLUGIN_DIRS)

# The app never calls QTranslator/installTranslator, so the base-Qt .qm
# translation catalogs (qtbase_de.qm, qtdeclarative_ja.qm, ...) are dead
# weight -- dozens of small files, but they add up. Leave the WebEngine
# locale packs alone; those are handled separately above.
def _is_unwanted_qt_translation(dest_path: str) -> bool:
    norm = dest_path.replace("\\", "/").lower()
    return (
        norm.endswith(".qm")
        and "/translations/" in norm
        and "qtwebengine_locales" not in norm
    )

# PySide6's WebEngine hook sometimes stages an empty
# qtwebengine_dictionaries/ folder for spellcheck even though the widget
# never enables it.
def _is_unwanted_webengine_dictionaries(dest_path: str) -> bool:
    norm = dest_path.replace("\\", "/").lower()
    return "qtwebengine_dictionaries" in norm

a.datas = [
    d for d in a.datas
    if not _is_unwanted_locale(d[0])
    and not _is_unwanted_qt_translation(d[0])
    and not _is_unwanted_webengine_dictionaries(d[0])
]
a.binaries = [
    b for b in a.binaries
    if not _is_unwanted_imageformat_plugin(b[0])
    and not _is_unwanted_plugin_binary(b[0])
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# upx=False on purpose: Inno Setup below re-compresses this entire folder
# with lzma2/ultra64. Compressing an already-UPX-packed binary a second
# time is usually a net loss -- LZMA compresses raw, uncompressed DLLs
# much better than it compresses UPX's already-high-entropy output. Letting
# Inno do the only compression pass, on clean binaries, produces a smaller
# final installer than stacking UPX + LZMA -- and avoids UPX-related
# antivirus false positives as a bonus. If you ever build without Inno
# (just distributing the raw dist/ folder), flip these back to upx=True.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Comical Launcher",
    icon="icons/icon.ico",
    console=False,
    strip=False,
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Comical Launcher",
)
