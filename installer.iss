[Setup]
AppName=DevVault
AppVersion=1.0.0
AppPublisher=TSW Technologies
DefaultDirName={pf}\DevVault
DefaultGroupName=DevVault
OutputDir=dist_installer
OutputBaseFilename=DevVault_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\DevVault.exe
SetupIconFile=devvault_desktop\assets\vault.ico

[Files]
Source: "dist\DevVault.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\DevVault"; Filename: "{app}\DevVault.exe"
Name: "{commondesktop}\DevVault"; Filename: "{app}\DevVault.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\DevVault.exe"; Description: "Launch DevVault"; Flags: nowait postinstall skipifsilent
