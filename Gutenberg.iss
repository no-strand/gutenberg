#define MyAppName "Gutenberg"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Nostrand"
#define MyAppDeveloper "Nostrand"
#define MyAppExeName "Gutenberg.exe"
#define MyAppPlatform "windows-x64"
#define MyAppDistName MyAppName + "-" + MyAppVersion + "-" + MyAppPlatform
#define MyAppDistDir AddBackslash(AddBackslash(SourcePath) + "dist") + MyAppDistName
#define MyAppIcon AddBackslash(SourcePath) + "installer.ico"
#define MyGutProgId "Gutenberg.GUT"
#define MyGutrProgId "Gutenberg.GUTR"

[Setup]
AppId={{6A5D56F3-5750-47B8-A7F8-7A5A9D6C3E11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir={#SourcePath}\dist_installer\{#MyAppDistName}
OutputBaseFilename={#MyAppName}-{#MyAppVersion}-{#MyAppPlatform}-setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
SetupIconFile={#MyAppIcon}
WizardStyle=modern
LanguageDetectionMethod=uilanguage
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes

[Languages]
Name: "ptBR"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "{#MyAppDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[InstallDelete]
Type: files; Name: "{localappdata}\Gutenberg\gutenberg_open_gut.cmd"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Sempre remove dados internos/cache do aplicativo no AppData local
Type: filesandordirs; Name: "{localappdata}\Gutenberg"

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: none; ValueName: "GUTENBERG_APP_PATH"; Flags: deletevalue
Root: HKCU; Subkey: "Environment"; ValueType: none; ValueName: "GUTENBERG_APP_SCRIPT"; Flags: deletevalue
Root: HKCU; Subkey: "Environment"; ValueType: none; ValueName: "GUTENBERG_PYTHON_PATH"; Flags: deletevalue
Root: HKCU; Subkey: "Environment"; ValueType: none; ValueName: "GUTENBERG_ICON_PATH"; Flags: deletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.gut\UserChoice"; Flags: deletekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.gutr\UserChoice"; Flags: deletekey

; Associação por usuário — aponta diretamente para o EXE instalado e usa o ícone real do build PyInstaller.
Root: HKCU; Subkey: "Software\Classes\.gut"; ValueType: string; ValueName: ""; ValueData: "{#MyGutProgId}"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.gut\OpenWithProgids"; ValueType: string; ValueName: "{#MyGutProgId}"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#MyGutProgId}"; ValueType: string; ValueName: ""; ValueData: "Arquivo Gutenberg"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\{#MyGutProgId}"; ValueType: string; ValueName: "FriendlyTypeName"; ValueData: "Arquivo Gutenberg"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\{#MyGutProgId}\DefaultIcon"; ValueType: expandsz; ValueName: ""; ValueData: """{code:GetGutFileIcon}"",0"; Flags: uninsdeletekey preservestringtype
Root: HKCU; Subkey: "Software\Classes\{#MyGutProgId}\shell\open\command"; ValueType: expandsz; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey preservestringtype

; Associação .gutr por usuário — ícone próprio de recursos e abertura direta pelo Gutenberg.
Root: HKCU; Subkey: "Software\Classes\.gutr"; ValueType: string; ValueName: ""; ValueData: "{#MyGutrProgId}"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.gutr\OpenWithProgids"; ValueType: string; ValueName: "{#MyGutrProgId}"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#MyGutrProgId}"; ValueType: string; ValueName: ""; ValueData: "Arquivo de Recursos Gutenberg"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\{#MyGutrProgId}"; ValueType: string; ValueName: "FriendlyTypeName"; ValueData: "Arquivo de Recursos Gutenberg"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\{#MyGutrProgId}\DefaultIcon"; ValueType: expandsz; ValueName: ""; ValueData: """{code:GetGutrFileIcon}"",0"; Flags: uninsdeletekey preservestringtype
Root: HKCU; Subkey: "Software\Classes\{#MyGutrProgId}\shell\open\command"; ValueType: expandsz; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey preservestringtype

; Associação também no nível da máquina — útil para instalações administrativas e outros usuários.
Root: HKLM; Subkey: "Software\Classes\.gut"; ValueType: string; ValueName: ""; ValueData: "{#MyGutProgId}"; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Classes\.gut\OpenWithProgids"; ValueType: string; ValueName: "{#MyGutProgId}"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Classes\{#MyGutProgId}"; ValueType: string; ValueName: ""; ValueData: "Arquivo Gutenberg"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\{#MyGutProgId}"; ValueType: string; ValueName: "FriendlyTypeName"; ValueData: "Arquivo Gutenberg"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\{#MyGutProgId}\DefaultIcon"; ValueType: expandsz; ValueName: ""; ValueData: """{code:GetGutFileIcon}"",0"; Flags: uninsdeletekey preservestringtype
Root: HKLM; Subkey: "Software\Classes\{#MyGutProgId}\shell\open\command"; ValueType: expandsz; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey preservestringtype

; Associação .gutr também no nível da máquina — ícone próprio de recursos.
Root: HKLM; Subkey: "Software\Classes\.gutr"; ValueType: string; ValueName: ""; ValueData: "{#MyGutrProgId}"; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Classes\.gutr\OpenWithProgids"; ValueType: string; ValueName: "{#MyGutrProgId}"; ValueData: ""; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Classes\{#MyGutrProgId}"; ValueType: string; ValueName: ""; ValueData: "Arquivo de Recursos Gutenberg"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\{#MyGutrProgId}"; ValueType: string; ValueName: "FriendlyTypeName"; ValueData: "Arquivo de Recursos Gutenberg"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\{#MyGutrProgId}\DefaultIcon"; ValueType: expandsz; ValueName: ""; ValueData: """{code:GetGutrFileIcon}"",0"; Flags: uninsdeletekey preservestringtype
Root: HKLM; Subkey: "Software\Classes\{#MyGutrProgId}\shell\open\command"; ValueType: expandsz; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey preservestringtype

[Code]
function GetGutFileIcon(Param: string): string;
var
  IconPathInternal: string;
  IconPathLegacy: string;
begin
  IconPathInternal := ExpandConstant('{app}\_internal\static\img\gut_file.ico');
  IconPathLegacy := ExpandConstant('{app}\static\img\gut_file.ico');

  if FileExists(IconPathInternal) then begin
    Result := IconPathInternal;
  end else begin
    Result := IconPathLegacy;
  end;
end;

function GetGutrFileIcon(Param: string): string;
var
  IconPathInternal: string;
  IconPathLegacy: string;
begin
  IconPathInternal := ExpandConstant('{app}\_internal\static\img\gutr_file.ico');
  IconPathLegacy := ExpandConstant('{app}\static\img\gutr_file.ico');

  if FileExists(IconPathInternal) then begin
    Result := IconPathInternal;
  end else begin
    Result := IconPathLegacy;
  end;
end;


procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  GutProjectsDir: string;
  GutUserAnswer: Integer;
begin
  if CurUninstallStep = usPostUninstall then begin
    GutProjectsDir := ExpandConstant('{userdocs}\Gutenberg');

    if DirExists(GutProjectsDir) then begin
      GutUserAnswer := MsgBox(
        'Deseja remover também os projetos salvos em:' + #13#10 + #13#10 +
        GutProjectsDir + #13#10 + #13#10 +
        'Se escolher Sim, essa pasta será excluída com todos os projetos dentro dela.' + #13#10 +
        'Se escolher Não, seus projetos serão mantidos.',
        mbConfirmation,
        MB_YESNO
      );

      if GutUserAnswer = IDYES then begin
        DelTree(GutProjectsDir, True, True, True);
      end;
    end;
  end;
end;
