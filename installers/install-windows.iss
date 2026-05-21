; PRC Tray — Inno Setup Script
; Compile with Inno Setup 6+: https://jrsoftware.org/isinfo.php
; Open this .iss in Inno Setup IDE and click Build > Compile

#define MyAppName "PRC Tray"
#ifndef MyAppVersion
#define MyAppVersion "0.0.0-dev"
#endif
#define MyAppPublisher "endersonvizc"
#define MyAppExeName "prc-tray.exe"

[Setup]
AppId={{com-endersonvizc-prc-tray}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\prc-tray
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=.\output
OutputBaseFilename=PRC-Tray-{#MyAppVersion}-windows-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "autostart"; Description: "Start daemon automatically on login"; GroupDescription: "Startup:"

[Files]
; Single-file binary from PyInstaller --onefile
Source: "..\dist\prc-tray.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Stop Daemon"; Filename: "{app}\stop.bat"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{userstartup}\prc-tray"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--no-tray"; Tasks: autostart

[Run]
; Create stop script
Filename: "{app}\stop.bat"; Flags: shellexec skipifnotsilent runhidden
; Start the daemon after install
Filename: "{app}\{#MyAppExeName}"; Parameters: "--no-tray"; Description: "Start PRC Tray"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Kill daemon on uninstall
Filename: "taskkill"; Parameters: "/f /im {#MyAppExeName}"; Flags: runhidden; RunOnceId: "KillDaemon"

[Code]
// Generate stop.bat during install
procedure CurStepChanged(CurStep: TSetupStep);
var
  StopBat: string;
begin
  if CurStep = ssPostInstall then
  begin
    StopBat := ExpandConstant('{app}\stop.bat');
    SaveStringToFile(StopBat, '@echo off' + #13#10 +
      'taskkill /f /im prc-tray.exe' + #13#10 +
      'echo Daemon stopped.' + #13#10 +
      'pause', False);
  end;
end;
