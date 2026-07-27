; VSTrustee Installer Script
[Setup]
AppName=VSTrustee
AppVersion=1.0.0
DefaultDirName={localappdata}\VSTrustee
DefaultGroupName=VSTrustee
OutputBaseFilename=VSTrusteeInstaller
Compression=lzma
SolidCompression=yes
DisableStartupPrompt=yes
SetupIconFile=C:\Users\Dell\Desktop\vstrustee_icon.ico

[Files]
; Your uploaded EXE (source on build machine) - change path to where the file is when compiling
Source: "C:\Users\Dell\Desktop\password_final_code.exe"; DestDir: "{app}"; DestName: "VSTrustee.exe"; Flags: ignoreversion

; Recovery tool (Python script) - include as-is or bundle as exe
Source: "C:\Users\Dell\Desktop\vstrustee_recovery_tool.py"; DestDir: "{app}"; Flags: ignoreversion

; Optional: include icon file in the install
Source: "C:\Users\Dell\Desktop\vstrustee_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userdesktop}\VSTrustee"; Filename: "{app}\VSTrustee.exe"; IconFilename: "{app}\vstrustee_icon.ico"
Name: "{group}\VSTrustee"; Filename: "{app}\VSTrustee.exe"; IconFilename: "{app}\vstrustee_icon.ico"

[Tasks]
Name: "add_desktop_shortcut"; Description: "Create a desktop shortcut"; GroupDescription: "Additional tasks"; Flags: unchecked

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    { Optional: if you want the recovery tool to be registered or launched automatically, do it here }
    { Example: create a simple association or schedule }
  end;
end;
