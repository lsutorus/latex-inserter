; LaTeX Inserter — Inno Setup Installer Script

#ifndef AppVersion
  #error "AppVersion must be defined via /DAppVersion=x.y.z"
#endif

[Setup]
AppName=LaTeX Inserter
AppVersion={#AppVersion}
AppId={{A7B8C9D0-E1F2-4A3B-5C6D-7E8F9A0B1C2D}
AppPublisher=Lucas Sutorus
AppPublisherURL=https://github.com/lsutorus/latex-inserter
DefaultDirName={pf}\LaTeX Inserter
DefaultGroupName=LaTeX Inserter
UninstallDisplayIcon={app}\LaTeX-Inserter.exe
UninstallDisplayName=LaTeX Inserter
OutputDir=dist
OutputBaseFilename=LaTeX-Inserter-setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
CloseApplications=force
SetupIconFile=LaTeX-Inserter-icon-final.ico

; Disable license page (no EULA)
DisableReadyPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "startmenuicon"; Description: "Create a &Start Menu shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
Source: "dist\LaTeX-Inserter.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\LaTeX Inserter"; Filename: "{app}\LaTeX-Inserter.exe"; Tasks: startmenuicon
Name: "{autodesktop}\LaTeX Inserter"; Filename: "{app}\LaTeX-Inserter.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LaTeX-Inserter.exe"; Description: "&Launch LaTeX Inserter"; Flags: nowait postinstall runascurrentuser

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDataPath: string;
  ResultCode: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDataPath := ExpandConstant('{userappdata}\LaTeX Inserter');
    if DirExists(AppDataPath) then
    begin
      if MsgBox('Do you want to remove your custom LaTeX mappings?', mbConfirmation, MB_YESNO) = IDYES then
      begin
        DelTree(AppDataPath, True, True, True);
      end;
    end;
  end;
end;
