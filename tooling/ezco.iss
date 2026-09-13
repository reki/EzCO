#ifndef MyAppVersion
#define MyAppVersion "1.0.0"
#endif
#ifndef SourceDir
#define SourceDir "staging"
#endif
#ifndef OutputDir
#define OutputDir "."
#endif
#ifndef OutputBaseName
#define OutputBaseName "EzCo-setup"
#endif
#ifndef SetupIcon
#define SetupIcon ""
#endif

[Setup]
AppId={{A3F8C2D1-6B4E-4A19-9C7D-8E2F1A0B3C4D}}
AppName=EzCo
AppVersion={#MyAppVersion}
AppPublisher=reki
DefaultDirName={autopf}\EzCo
DefaultGroupName=EzCo
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseName}
UninstallDisplayIcon={app}\EzCo.exe
#if SetupIcon != ""
SetupIconFile={#SetupIcon}
#endif

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップに EzCo のショートカットを作る"; GroupDescription: "追加:"; Flags: checkedonce; Languages: japanese
Name: "desktopicon"; Description: "Create a desktop shortcut for EzCo"; GroupDescription: "Additional:"; Flags: checkedonce; Languages: english
Name: "desktopmanual"; Description: "デスクトップにユーザーマニュアルのショートカットを作る"; GroupDescription: "追加:"; Flags: checkedonce; Languages: japanese
Name: "desktopmanual"; Description: "Create a desktop shortcut for the user manual"; GroupDescription: "Additional:"; Flags: checkedonce; Languages: english

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\EzCo"; Filename: "{app}\EzCo.exe"
Name: "{autodesktop}\EzCo"; Filename: "{app}\EzCo.exe"; Tasks: desktopicon
Name: "{autodesktop}\EzCo ユーザーマニュアル"; Filename: "{app}\UserManual\Manual(JP).html"; Tasks: desktopmanual; Languages: japanese
Name: "{autodesktop}\EzCo User Manual"; Filename: "{app}\UserManual\Manual(EN).html"; Tasks: desktopmanual; Languages: english

[Run]
Filename: "{app}\EzCo.exe"; Description: "EzCo を起動"; Flags: nowait postinstall skipifsilent; Languages: japanese
Filename: "{app}\EzCo.exe"; Description: "Launch EzCo"; Flags: nowait postinstall skipifsilent; Languages: english
