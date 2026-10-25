; Inno Setup script for PHI. Build with: ISCC.exe installer.iss  (after PyInstaller: dist\PHI)
#define AppName "PHI"
#define AppVersion "0.1.0"

[Setup]
AppId={{6B1D0C52-7A0E-4E7B-9C61-5D9F3A0F2B11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=PHI
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=PHI-Setup
SetupIconFile=phi.ico
UninstallDisplayIcon={app}\PHI.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\PHI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "redist\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "extension\*"; DestDir: "{app}\extension"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PHI"; Filename: "{app}\PHI.exe"; IconFilename: "{app}\PHI.exe"; AppUserModelID: "PHI.Companion"
Name: "{group}\PHI browser extension folder"; Filename: "{app}\extension"
Name: "{autodesktop}\PHI"; Filename: "{app}\PHI.exe"; Tasks: desktopicon

[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Microsoft Visual C++ runtime..."; Flags: waituntilterminated; Check: NeedsVCRedist
Filename: "{app}\PHI.exe"; Description: "Launch PHI"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\reg.exe"; Parameters: "delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v PHI /f"; Flags: runhidden; RunOnceId: "RemovePhiAutostart"

[Code]
function NeedsVCRedist: Boolean;
begin
  Result := not RegKeyExists(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64');
end;

