; KanzonasCAD installer (Inno Setup 6). Built by the GitHub workflow:
;   ISCC.exe /DMyAppVersion=0.4.1 installer\KanzonasCAD.iss
; Installs for the current user (no administrator rights needed) unless "all users" is picked
; on the first page (Windows' administrator prompt). KanzonasCAD's Update now runs the next
; setup the same way the copy was installed. Adapted from KanzonasPDF's installer.

#ifndef MyAppVersion
  #define MyAppVersion "0.0"
#endif
#define MyAppName "KanzonasCAD"
#define MyAppExe "KanzonasCAD.exe"

[Setup]
; (never change the AppId: it is how a new setup finds the copy it updates)
AppId={{3D7B9E24-6A1C-4F85-B2E0-9C4D7A15E863}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=KanzonasCAD
AppPublisherURL=https://github.com/keithlyding/KanzonasCAD
AppSupportURL=https://github.com/keithlyding/KanzonasCAD
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist-installer
OutputBaseFilename={#MyAppName}-v{#MyAppVersion}-setup
SetupIconFile=..\assets\kanzonascad-setup.ico
UninstallDisplayIcon={app}\{#MyAppExe}
LicenseFile=..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked
Name: "kzcadfiles"; Description: "Open .kzcad project files with {#MyAppName} (double-click)"

[Files]
Source: "..\dist\{#MyAppName}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
; (an update replaces the program's own files: none of an older version's are left behind)
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; .kzcad projects open in KanzonasCAD (for this user, or everyone with an all-users install;
; removed again by the uninstaller)
Root: HKA; Subkey: "Software\Classes\.kzcad"; ValueType: string; ValueData: "KanzonasCAD.Project"; Flags: uninsdeletevalue; Tasks: kzcadfiles
Root: HKA; Subkey: "Software\Classes\.kzcad\OpenWithProgids"; ValueType: string; ValueName: "KanzonasCAD.Project"; ValueData: ""; Flags: uninsdeletevalue; Tasks: kzcadfiles
Root: HKA; Subkey: "Software\Classes\KanzonasCAD.Project"; ValueType: string; ValueData: "KanzonasCAD project"; Flags: uninsdeletekey; Tasks: kzcadfiles
Root: HKA; Subkey: "Software\Classes\KanzonasCAD.Project\DefaultIcon"; ValueType: string; ValueData: "{app}\{#MyAppExe},0"; Tasks: kzcadfiles
Root: HKA; Subkey: "Software\Classes\KanzonasCAD.Project\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExe}"" ""%1"""; Tasks: kzcadfiles
; listed under "Open with" for .kzcad and .dxf files (never taking over .dxf by itself)
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExe}\SupportedTypes"; ValueType: string; ValueName: ".kzcad"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExe}\SupportedTypes"; ValueType: string; ValueName: ".dxf"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExe}\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExe}"" ""%1"""

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Start {#MyAppName}"; Flags: nowait postinstall skipifsilent
; KanzonasCAD's Update now runs this setup quietly with /RELAUNCH: start the app again when done
Filename: "{app}\{#MyAppExe}"; Flags: nowait runasoriginaluser; Check: RelaunchAfterUpdate

[Code]
function RelaunchAfterUpdate: Boolean;
begin
  Result := WizardSilent and (Pos('/RELAUNCH', Uppercase(GetCmdTail)) > 0);
end;
