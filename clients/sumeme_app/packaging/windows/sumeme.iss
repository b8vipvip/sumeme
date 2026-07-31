#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef BuildDir
  #define BuildDir "."
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif

[Setup]
AppId={{D54D418F-36A7-475C-BF76-860ED1631DD0}
AppName=SuMeMe
AppVersion={#AppVersion}
AppPublisher=SuMeMe
DefaultDirName={localappdata}\Programs\SuMeMe
DefaultGroupName=SuMeMe
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=SuMeMe-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\sumeme_app.exe

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\SuMeMe"; Filename: "{app}\sumeme_app.exe"
Name: "{userdesktop}\SuMeMe"; Filename: "{app}\sumeme_app.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："; Flags: unchecked

[Run]
Filename: "{app}\sumeme_app.exe"; Description: "启动 SuMeMe"; Flags: nowait postinstall skipifsilent
