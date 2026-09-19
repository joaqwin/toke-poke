; Instalador de Toke-Poke (Inno Setup 6): `iscc installer.iss`
; Requiere haber ejecutado antes `pyinstaller toke_poke.spec` (dist\TokePoke\).

#define AppName "Toke-Poke"
#define AppVersion "1.0.0"
#define AppExe "TokePoke.exe"
#define AppPublisher "Joaquin Perez"
#define AppURL "https://github.com/joaqwin/toke-poke"

[Setup]
AppId={{7C9E4B4A-2F0D-4A8B-9B7E-2E3F1A5C0D11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
SetupIconFile=assets\icon\pokeball.ico
WizardStyle=modern
; Instala por usuario (sin pedir administrador) en %LOCALAPPDATA%\Programs\Toke-Poke.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist\installer
OutputBaseFilename=TokePoke-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup"; Description: "Iniciar {#AppName} al encender Windows"; GroupDescription: "Inicio automático:"; Flags: unchecked

[Files]
Source: "dist\TokePoke\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Los datos del usuario (state.json y sprites) quedan en %LOCALAPPDATA%\TokePoke y no se borran.
Type: filesandordirs; Name: "{app}"
