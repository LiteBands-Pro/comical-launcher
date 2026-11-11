<#
.SYNOPSIS
    Builds the Windows release of Comical Launcher end to end:
      1. creates/reuses a clean venv (build-venv\) with only requirements.txt
         + PyInstaller installed
      2. runs PyInstaller against comical_launcher.spec (same spec used for
         Linux — already excludes unused PySide6 submodules, locale packs,
         and plugin binaries; see the comments in that file)
      3. compiles installer.iss with Inno Setup to produce
         installer_output\ComicalLauncherSetup.exe — that exact filename is
         what core/launcher_updater.py looks for as a release asset (see
         _ASSET_FILENAMES there), so don't rename it

    PyInstaller does NOT cross-compile: this must be run ON Windows to
    produce a Windows build (a Linux build likewise has to be built on
    Linux — see scripts/build_linux.sh).

    Requires Inno Setup 6 installed (https://jrsoftware.org/isdl.php) so
    ISCC.exe is available — either on PATH or at its default install
    location, which this script checks automatically.

.PARAMETER Clean
    Wipe the build venv and previous build artifacts before building.

.EXAMPLE
    .\scripts\build_windows.ps1
.EXAMPLE
    .\scripts\build_windows.ps1 -Clean
#>

param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

# Repo root, regardless of where this is invoked from
Set-Location (Join-Path $PSScriptRoot "..")

$VenvDir = "build-venv"
$DistDir = "dist"
$BuildDir = "build"
$OutDir = "installer_output"
$InstallerName = "ComicalLauncherSetup.exe"

if ($Clean) {
    Write-Host "==> Removing venv + previous build artifacts"
    Remove-Item -Recurse -Force $VenvDir, $DistDir, $BuildDir, $OutDir -ErrorAction SilentlyContinue
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "python not found on PATH — install it first."
}

Write-Host "==> Setting up build venv ($VenvDir)"
if (-not (Test-Path $VenvDir)) {
    python -m venv $VenvDir
}
& "$VenvDir\Scripts\Activate.ps1"

python -m pip install --upgrade pip --quiet
Write-Host "==> Installing requirements.txt + PyInstaller"
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

Write-Host "==> Running PyInstaller"
pyinstaller comical_launcher.spec --clean --noconfirm

$AppDir = Join-Path $DistDir "Comical Launcher"
if (-not (Test-Path $AppDir)) {
    Write-Error "Build didn't produce '$AppDir' — check the PyInstaller output above."
}

# Locate Inno Setup's compiler: PATH first, then the usual install paths.
$Iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $Iscc) {
    $Candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $Found = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($Found) { $Iscc = $Found } else { $Iscc = $null }
} else {
    $Iscc = $Iscc.Source
}

if (-not $Iscc) {
    deactivate
    Write-Error "Inno Setup's ISCC.exe not found. Install Inno Setup 6 (https://jrsoftware.org/isdl.php), then re-run this script. The unpacked build is at '$AppDir' if you want to test it directly without an installer."
}

Write-Host "==> Compiling installer with Inno Setup"
& $Iscc "installer.iss"

deactivate

$InstallerPath = Join-Path $OutDir $InstallerName
if (-not (Test-Path $InstallerPath)) {
    Write-Error "Expected installer at '$InstallerPath' but it wasn't created — check the Inno Setup output above."
}

$RawSizeMB = "{0:N1} MB" -f ((Get-ChildItem $AppDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB)
$InstallerSizeMB = "{0:N1} MB" -f ((Get-Item $InstallerPath).Length / 1MB)

Write-Host ""
Write-Host "==> Done"
Write-Host "    Raw build:  $AppDir  ($RawSizeMB)"
Write-Host "    Installer:  $InstallerPath  ($InstallerSizeMB)"
Write-Host ""
Write-Host "    Upload $InstallerPath as a release asset on the public"
Write-Host "    releases repo — filename must stay exactly '$InstallerName'"
Write-Host "    for the auto-updater to find it."
