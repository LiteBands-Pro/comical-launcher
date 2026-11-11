#!/usr/bin/env bash
#
# Builds the Linux release of Comical Launcher end to end:
#   1. creates/reuses a clean venv (build-venv/) with only requirements.txt
#      + PyInstaller installed — extra packages in the build environment
#      get scanned and can bloat the output, so this venv is dedicated to
#      building, not your everyday dev env
#   2. runs PyInstaller against comical_launcher.spec (the same spec used
#      for Windows — it already excludes unused PySide6 submodules,
#      locale packs, and plugin binaries; see the comments in that file)
#   3. tars up the resulting onedir build as
#      installer_output/ComicalLauncher-linux.tar.gz — that exact
#      filename is what core/launcher_updater.py looks for as a release
#      asset (see _ASSET_FILENAMES there), so don't rename it
#
# PyInstaller does NOT cross-compile: this must be run ON Linux to
# produce a Linux build (a Windows build likewise has to be built on
# Windows, or in a Windows CI runner/VM — see installer.iss for that
# side).
#
# Usage:
#   scripts/build_linux.sh            # build
#   scripts/build_linux.sh --clean    # wipe venv + build dirs first, then build

set -euo pipefail

cd "$(dirname "$0")/.."   # repo root, regardless of where this is invoked from

VENV_DIR="build-venv"
DIST_DIR="dist"
BUILD_DIR="build"
OUT_DIR="installer_output"
APP_NAME="Comical Launcher"
ARCHIVE_NAME="ComicalLauncher-linux.tar.gz"

if [[ "${1:-}" == "--clean" ]]; then
    echo "==> Removing venv + previous build artifacts"
    rm -rf "$VENV_DIR" "$DIST_DIR" "$BUILD_DIR" "$OUT_DIR"
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found on PATH — install it first." >&2
    exit 1
fi

echo "==> Setting up build venv ($VENV_DIR)"
if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip --quiet
echo "==> Installing requirements.txt + PyInstaller"
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

echo "==> Running PyInstaller"
pyinstaller comical_launcher.spec --clean --noconfirm

if [[ ! -d "$DIST_DIR/$APP_NAME" ]]; then
    echo "Build didn't produce '$DIST_DIR/$APP_NAME' — check the PyInstaller output above." >&2
    exit 1
fi

# Make sure the entry-point binary is actually executable — PyInstaller
# normally sets this, but a fresh checkout/CI artifact download can lose
# the bit, and a non-executable "binary" inside the tarball would fail
# silently for whoever downloads the update.
chmod +x "$DIST_DIR/$APP_NAME/$APP_NAME"

echo "==> Packaging release archive"
mkdir -p "$OUT_DIR"
tar -czf "$OUT_DIR/$ARCHIVE_NAME" -C "$DIST_DIR" "$APP_NAME"

deactivate

RAW_SIZE=$(du -sh "$DIST_DIR/$APP_NAME" | cut -f1)
ARCHIVE_SIZE=$(du -sh "$OUT_DIR/$ARCHIVE_NAME" | cut -f1)

echo ""
echo "==> Done"
echo "    Raw build:  $DIST_DIR/$APP_NAME  ($RAW_SIZE)"
echo "    Release archive: $OUT_DIR/$ARCHIVE_NAME  ($ARCHIVE_SIZE)"
echo ""
echo "    Upload $OUT_DIR/$ARCHIVE_NAME as a release asset on the"
echo "    public releases repo — filename must stay exactly"
echo "    '$ARCHIVE_NAME' for the auto-updater to find it."
echo ""
echo "    To test the build locally without installing it anywhere:"
echo "        \"$DIST_DIR/$APP_NAME/$APP_NAME\""
