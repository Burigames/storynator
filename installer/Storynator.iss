[Setup]
AppId={{6A746520-8499-4779-99F7-2C5C306EC683}
AppName=Storynator
AppVersion=0.4.0
AppPublisher=Burigames
DefaultDirName={localappdata}\Programs\Storynator
DefaultGroupName=Storynator
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableWelcomePage=yes
DisableReadyPage=yes
ChangesAssociations=yes
OutputDir=..\dist
OutputBaseFilename=Storynator-Setup
SetupIconFile=..\assets\Storynator.ico
UninstallDisplayIcon={app}\Storynator.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[Files]
Source: "..\dist\Storynator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{userprograms}\Storynator"; Filename: "{app}\Storynator.exe"; WorkingDir: "{app}"
[Registry]
Root: HKCU; Subkey: "Software\Classes\.storynator"; ValueType: string; ValueData: "Storynator.Project"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.storynator\OpenWithProgids"; ValueType: string; ValueName: "Storynator.Project"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\Storynator.Project"; ValueType: string; ValueData: "Storynator project"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Storynator.Project\DefaultIcon"; ValueType: string; ValueData: """{app}\Storynator.exe"",0"
Root: HKCU; Subkey: "Software\Classes\Storynator.Project\shell\open\command"; ValueType: string; ValueData: """{app}\Storynator.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\.storynator-preset"; ValueType: string; ValueData: "Storynator.Preset"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.storynator-preset\OpenWithProgids"; ValueType: string; ValueName: "Storynator.Preset"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\Storynator.Preset"; ValueType: string; ValueData: "Storynator category preset"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Storynator.Preset\DefaultIcon"; ValueType: string; ValueData: """{app}\Storynator.exe"",0"
Root: HKCU; Subkey: "Software\Classes\Storynator.Preset\shell\open\command"; ValueType: string; ValueData: """{app}\Storynator.exe"" --import-preset ""%1"""
[Run]
Filename: "{app}\Storynator.exe"; Description: "Storynator"; Flags: nowait skipifsilent
