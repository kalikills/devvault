#define MyAppName "DevVault"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "DevVault"
#define MyAppExeName "DevVault.exe"

[Setup]
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppId={{A9D3C8B7-6D6C-4D44-9D92-1A2B3C4D5E6F}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\DevVault
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=DevVault-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\devvault_desktop\assets\vault.ico

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\devvault_desktop\assets\vault.ico"; DestDir: "{app}"; Flags: ignoreversion
; Copies the entire PyInstaller dist folder output into Program Files\DevVault
Source: "..\dist\DevVault\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\vault.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\vault.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent


