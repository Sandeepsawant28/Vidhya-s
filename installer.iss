; Inno Setup 6 Script for Vidya’s Liquor Loft
; Packages dist\LiquorShop into a professional Windows Installer (Setup.exe)

#define MyAppName "Vidya's Liquor Loft"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Vidya's Liquor Loft"
#define MyAppExeName "LiquorShop.exe"

[Setup]
AppId={{C84F3D21-8291-420C-9DF1-A76F7BC87B32}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\LiquorShop
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=output
OutputBaseFilename=LiquorShop_Setup_v1.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startwithwindows"; Description: "Start Liquor Shop automatically when Windows boots"; GroupDescription: "Startup Options:"; Flags: unchecked

[Files]
; Source is the PyInstaller one-folder output
Source: "dist\LiquorShop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "backup.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Manual Backup"; Filename: "{app}\backup.bat"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startwithwindows

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up app cache files inside Program Files install folder
; NOTE: C:\ProgramData\LiquorShop is deliberately NEVER listed here, ensuring 
; that uninstalling or upgrading the app NEVER deletes your customer bills or sales database!
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
// Custom Inno Setup confirmation message during uninstallation
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    MsgBox('Vidya’s Liquor Loft program files have been uninstalled.' + #13#10 + #13#10 +
           'NOTE: Your shop database and backup files have been safely PRESERVED in:' + #13#10 +
           'C:\ProgramData\LiquorShop\' + #13#10 + #13#10 +
           'Reinstalling or updating the software will automatically reconnect to this data.', 
           mbInformation, MB_OK);
  end;
end;
