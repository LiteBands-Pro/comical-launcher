; Comical Launcher — Inno Setup script
;
; Build order:
;   1) pyinstaller comical_launcher.spec        -> dist\Comical Launcher\...
;   2) ISCC.exe installer.iss                   -> installer_output\ComicalLauncherSetup.exe
;
; Requires Inno Setup 6 (https://jrsoftware.org/isinfo.php).

; Keep MyAppVersion in sync with LAUNCHER_VERSION in
; comical_launcher/core/version.py — that constant is what the *running*
; app compares against the update manifest, this is what ends up in the
; installer/exe's own version metadata. They should match on every release.
#define MyAppName "Comical Launcher"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Comical Games"
#define MyAppExeName "Comical Launcher.exe"
#define MyAppURL "https://comical-games.itch.io/rocky-chapter-1"

[Setup]
; Keep this GUID fixed across versions so updates upgrade in place
; instead of installing side-by-side. Generate your own once and freeze it:
; Inno Setup > Tools > Generate GUID.
AppId={{B4996494-9F37-4177-A326-19085689C846}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=installer_output
OutputBaseFilename=ComicalLauncherSetup
SetupIconFile=icons\icon.ico
; LZMA2/max squeezes noticeably more out of the PyInstaller output than the
; default; solid compression helps since it's mostly one big Qt/Chromium
; payload rather than many small files.
; lzma2/ultra64 is Inno's strongest built-in preset (64-bit LZMA2, largest
; dictionary/match settings) -- stronger than lzma2/max, at the cost of
; slower compile time and more RAM while building. Worth it here since the
; PyInstaller spec now hands Inno raw, uncompressed binaries (UPX disabled)
; specifically so this compression pass has clean data to work with.
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; The auto-updater (core/launcher_updater.py) downloads this installer and
; runs it while the launcher may still technically be exiting — these two
; make Setup close a still-running "Comical Launcher.exe" itself (rather
; than fail with a file-in-use error) and bring it back up afterward, so
; a forced update feels like one continuous action to the person instead
; of "app vanished, please go find the installer and run it".
CloseApplications=yes
CloseApplicationsFilter={#MyAppExeName}
RestartApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; Pulls in the whole onedir output folder produced by comical_launcher.spec.
Source: "dist\Comical Launcher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Removes anything the launcher wrote at runtime (downloaded game files,
; cached art, etc.) so an uninstall doesn't leave stray data behind.
Type: filesandordirs; Name: "{app}"
