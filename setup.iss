; ═══════════════════════════════════════════════════════════════
; MCP Tool Hub — Inno Setup 安装脚本
;
; 用法:
;   ISCC setup.iss                         # 默认构建
;   ISCC setup.iss /DVersion=1.0.0         # 指定版本
;
; 前置条件:
;   1. 先运行 .\build.ps1 完成 PyInstaller 打包
;   2. dist\mcp-tool-hub\ 目录已存在
;   3. 安装 Inno Setup 6 (https://jrsoftware.org/isdl.php)
; ═══════════════════════════════════════════════════════════════

#ifndef Version
  #define Version "0.1.0"
#endif

#define AppName "MCP Tool Hub"
#define AppPublisher "MCP Tool Hub"
#define AppURL "https://github.com/example/mcp-tool-hub"
#define AppExeName "mcp-client.exe"
#define ServerExeName "mcp-server.exe"
#define DataDirName "MCP Tool Hub"

[Setup]
; ── 基本信息 ──
AppId={{B8E3F2A1-5D6C-4A9E-8F1B-3C7D2E4A6F90}
AppName={#AppName}
AppVersion={#Version}
AppVerName={#AppName} {#Version}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}

; ── 输出 ──
OutputDir=dist
OutputBaseFilename=mcp-tool-hub-{#Version}-setup
SetupIconFile=assets\icon.ico
Compression=lzma2/normal
SolidCompression=yes
LZMANumBlockThreads=4

; ── 权限与架构 ──
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; ── 安装界面 ──
WizardStyle=modern
WizardSizePercent=100

; ── 卸载 ──
Uninstallable=yes

; ── 其他 ──
CloseApplications=force
RestartApplications=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
chinesesimplified.WelcomeLabel2=这将安装 {#AppName} {#Version} 到您的计算机。%n%n集成式 MCP 工具平台，为 AI 客户端提供统一工具服务。
english.WelcomeLabel2=This will install {#AppName} {#Version} on your computer.%n%nAn integrated MCP tool platform providing unified tool services for AI clients.

[Tasks]
; ── 快捷方式 ──
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startmenuicon"; Description: "创建开始菜单快捷方式 / Create Start Menu shortcuts"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; ── 主程序 ──
Source: "dist\mcp-tool-hub\mcp-server.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\mcp-tool-hub\mcp-client.exe"; DestDir: "{app}"; Flags: ignoreversion

; ── 内部依赖 ──
Source: "dist\mcp-tool-hub\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── NSSM（服务管理由 UI 调用） ──
Source: "dist\mcp-tool-hub\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion

; ── 数据目录结构（空目录占位） ──
Source: "data\*"; DestDir: "{localappdata}\{#DataDirName}"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: not DataDirExists

[Icons]
; ── 开始菜单 ──
Name: "{group}\MCP Tool Hub 管理界面"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: startmenuicon
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"; Tasks: startmenuicon

; ── 桌面 ──
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; ── 完成后启动 ──
Filename: "{app}\{#AppExeName}"; Description: "启动 MCP Tool Hub 管理界面"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; ── 清理安装目录 ──
Type: filesandordirs; Name: "{app}\data"

[Code]
function DataDirExists: Boolean;
var
  DataPath: string;
begin
  DataPath := ExpandConstant('{localappdata}\{#DataDirName}');
  Result := DirExists(DataPath);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataPath: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataPath := ExpandConstant('{localappdata}\{#DataDirName}');
    if DirExists(DataPath) then
    begin
      if MsgBox(
        FmtMessage('检测到用户数据目录：%1%n%n是否保留用户数据（日志、插件配置等）？%n%n选择「是」保留数据，选择「否」将删除所有数据。', [DataPath]),
        mbConfirmation,
        MB_YESNO
      ) = IDNO then
      begin
        DelTree(DataPath, True, True, True);
      end;
    end;
  end;
end;
