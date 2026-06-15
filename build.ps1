# MCP Tool Hub — PyInstaller 构建脚本
# 产出: dist/mcp-tool-hub/  (单目录，含 mcp-server.exe + mcp-client.exe)
#
# 用法:
#   .\build.ps1              # 默认构建（包含 Web 前端）
#   .\build.ps1 -Clean       # 清理后构建
#   .\build.ps1 -SkipInstall # 跳过 pyinstaller 安装检查
#   .\build.ps1 -SkipWeb     # 跳过 Web 前端构建
#   .\build.ps1 -Inno        # 同时构建 Inno Setup 安装包

param(
    [switch] $Clean,
    [switch] $SkipInstall,
    [switch] $SkipUpx,
    [switch] $Inno,
    [switch] $SkipWeb
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$SpecFile = "mcp_tool_hub.spec"
$DistDir = "dist"
$OutputDir = "output"
$OutputName = "mcp-tool-hub"

# ── 颜色辅助函数 ──
function Write-Step { param($Msg) Write-Host "`n>>> $Msg" -ForegroundColor Cyan }
function Write-OK { param($Msg) Write-Host "  [OK] $Msg" -ForegroundColor Green }
function Write-Warn { param($Msg) Write-Host "  [WARN] $Msg" -ForegroundColor Yellow }
function Write-Err { param($Msg) Write-Host "  [ERROR] $Msg" -ForegroundColor Red }

# ═══════════════════════════════════════════════════════════════
# 1. 环境检查
# ═══════════════════════════════════════════════════════════════
Write-Step "检查构建环境"

# uv
$uvExe = Get-Command uv -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (-not $uvExe) {
    Write-Err "未找到 uv，请先安装 uv 并添加到 PATH"
    exit 1
}
Write-OK "uv: $uvExe"

# 同步依赖
if (-not $SkipInstall) {
    Write-OK "同步项目依赖 (uv sync)..."
    uv sync --quiet
}

# Python (via uv)
$pyVer = uv run python --version 2>&1
Write-OK "Python: $pyVer"

# PyInstaller
if (-not $SkipInstall) {
    Write-OK "确保 PyInstaller 已安装..."
    uv sync --quiet
}

$pyiVer = uv run python -m PyInstaller --version 2>&1
Write-OK "PyInstaller: $pyiVer"

# Spec 文件
if (-not (Test-Path $SpecFile)) {
    Write-Err "未找到 spec 文件: $SpecFile"
    exit 1
}
Write-OK "Spec 文件: $SpecFile"

# ═══════════════════════════════════════════════════════════════
# 2. 构建 Web 前端 (npm)
# ═══════════════════════════════════════════════════════════════
Write-Step "构建 Web 前端"

if ($SkipWeb) {
    Write-OK "跳过 Web 前端构建 (-SkipWeb)"
}
else {
    $webDir = "$ScriptDir\web"
    $webPackage = "$webDir\package.json"
    $webDist = "$webDir\dist"
    $assetsWeb = "$ScriptDir\assets\web"
    
    if (-not (Test-Path $webPackage)) {
        Write-Warn "web/package.json 未找到，跳过 Web 前端构建"
    }
    else {
        # 检查 node/npm
        $nodeExe = Get-Command node -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
        $npmExe = Get-Command npm -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
        
        if (-not $nodeExe) {
            Write-Warn "未找到 node.js，跳过 Web 前端构建"
            Write-Warn "请安装 Node.js 并添加到 PATH: https://nodejs.org/"
        }
        else {
            Write-OK "Node.js: $nodeExe"
            
            # 检查是否需要构建（对比源文件和目标文件时间戳）
            $needBuild = $true
            if (Test-Path $assetsWeb) {
                $srcTime = (Get-ChildItem $webDir\src -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
                $distTime = (Get-ChildItem $assetsWeb -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
                if ($srcTime -lt $distTime) {
                    $needBuild = $false
                    Write-OK "Web 前端已是最新，跳过构建"
                }
            }
            
            if ($needBuild) {
                Write-OK "执行: npm run build (在 web/ 目录)"
                
                Push-Location $webDir
                try {
                    & $npmExe run build
                    if ($LASTEXITCODE -ne 0) {
                        Write-Err "npm run build 失败 (退出码: $LASTEXITCODE)"
                        exit $LASTEXITCODE
                    }
                }
                finally {
                    Pop-Location
                }
                
                Write-OK "Web 前端构建完成"
            }
        }
    }
}

# ═══════════════════════════════════════════════════════════════
# 4. 清理（仅在 -Clean 模式下执行，否则保留构建缓存以支持增量构建）
# ═══════════════════════════════════════════════════════════════
if ($Clean) {
    Write-Step "清理旧的构建产物（-Clean 模式）"

    $ToRemove = @(
        "$DistDir\$OutputName",
        "build",
        "__pycache__"
    )

    # 递归清理 __pycache__
    $pycacheDirs = Get-ChildItem -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
    foreach ($d in $pycacheDirs) {
        Remove-Item $d.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }

    foreach ($d in $ToRemove) {
        if (Test-Path $d) {
            try {
                Remove-Item $d -Recurse -Force -ErrorAction Stop
                Write-OK "已删除: $d"
            }
            catch {
                Write-Warn "无法删除 $d (可能被占用): $($_.Exception.Message)"
                Write-Warn "请先关闭正在运行的 mcp-server.exe / mcp-client.exe，然后重试"
                exit 1
            }
        }
    }
    Write-OK "清理完成"
}
else {
    Write-Step "跳过清理（增量构建模式，使用 -Clean 强制清理）"
}

# ═══════════════════════════════════════════════════════════════
# 5. 构建
# ═══════════════════════════════════════════════════════════════
Write-Step "开始 PyInstaller 构建..."

$pyiArgs = @(
    $SpecFile,
    "--distpath", $DistDir,
    "--workpath", "build",
    "--noconfirm"
)

# Clean 模式下才传 --clean（让 PyInstaller 重新分析依赖）
if ($Clean) {
    $pyiArgs += "--clean"
}

if (-not $SkipUpx) {
    # UPX 压缩 (如果已安装)
    $pyiArgs += "--upx-dir", "."
}

Write-OK "执行: uv run python -m PyInstaller $($pyiArgs -join ' ')"

$allArgs = @("run", "python", "-m", "PyInstaller") + $pyiArgs
$proc = Start-Process -FilePath $uvExe `
    -ArgumentList $allArgs `
    -NoNewWindow -Wait -PassThru

if ($proc.ExitCode -ne 0) {
    Write-Err "PyInstaller 构建失败 (退出码: $($proc.ExitCode))"
    exit $proc.ExitCode
}

Write-OK "PyInstaller 构建完成"

# ═══════════════════════════════════════════════════════════════
# 5.5 复制 magika 数据文件到 _internal（PyInstaller 未自动收集）
# ═══════════════════════════════════════════════════════════════
Write-Step "复制 magika 数据文件"

$magikaSrc = "$ScriptDir\.venv\Lib\site-packages\magika"
$magikaDst = "$DistDir\$OutputName\_internal\magika"

if (Test-Path $magikaSrc) {
    if (Test-Path $magikaDst) {
        Remove-Item $magikaDst -Recurse -Force
    }
    Copy-Item $magikaSrc -Destination $magikaDst -Recurse -Force
    Write-OK "magika 数据文件已复制到 _internal\magika\"
}
else {
    Write-Warn "未找到 magika 包目录: $magikaSrc"
}

# ═══════════════════════════════════════════════════════════════
# 6. 验证输出
# ═══════════════════════════════════════════════════════════════
Write-Step "验证构建产物"

$OutputDir = "$DistDir\$OutputName"
$ServerExe = "$OutputDir\mcp-server.exe"
$ClientExe = "$OutputDir\mcp-client.exe"
$InternalDir = "$OutputDir\_internal"

$allGood = $true

if (Test-Path $ServerExe) {
    $size = [math]::Round((Get-Item $ServerExe).Length / 1MB, 2)
    Write-OK "mcp-server.exe  ($size MB)"
}
else {
    Write-Err "mcp-server.exe 未找到!"
    $allGood = $false
}

if (Test-Path $ClientExe) {
    $size = [math]::Round((Get-Item $ClientExe).Length / 1MB, 2)
    Write-OK "mcp-client.exe  ($size MB)"
}
else {
    Write-Err "mcp-client.exe 未找到!"
    $allGood = $false
}

if (Test-Path $InternalDir) {
    $fileCount = (Get-ChildItem $InternalDir -Recurse -File).Count
    $dirSize = [math]::Round(
        (Get-ChildItem $InternalDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB, 2
    )
    Write-OK "_internal/  ($fileCount 文件, $dirSize MB)"
}
else {
    Write-Warn "_internal/ 未找到 (可能使用了 --onefile 模式?)"
}

# 检查资源文件
if (Test-Path "$InternalDir\plugins") {
    $pluginDirs = (Get-ChildItem "$InternalDir\plugins" -Directory).Count
    Write-OK "plugins/ 已包含 ($pluginDirs 个插件目录)"
}
else {
    Write-Warn "plugins/ 未找到"
}

if (Test-Path "$InternalDir\assets") {
    Write-OK "assets/ 已包含"
}
else {
    Write-Warn "assets/ 未找到"
}

# ═══════════════════════════════════════════════════════════════
# 7. 下载 nssm.exe（Windows 服务管理工具）
# ═══════════════════════════════════════════════════════════════
Write-Step "检查 nssm.exe"

$NssmExe = "$ScriptDir\nssm.exe"
$NssmUrl = "https://nssm.cc/release/nssm-2.24.zip"

if (Test-Path $NssmExe) {
    Write-OK "nssm.exe 已存在，跳过下载"
}
else {
    Write-OK "下载 nssm-2.24.zip ..."
    $zipPath = "$ScriptDir\nssm-2.24.zip"
    try {
        Invoke-WebRequest -Uri $NssmUrl -OutFile $zipPath -UseBasicParsing
        Write-OK "下载完成"
    }
    catch {
        Write-Err "下载 nssm 失败: $_"
        exit 1
    }

    # 解压到临时目录
    $tempDir = "$ScriptDir\_nssm_temp"
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
    Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force
    Write-OK "解压完成"

    # 复制 win64/nssm.exe 到项目根目录
    $nssmSrc = "$tempDir\nssm-2.24\win64\nssm.exe"
    if (Test-Path $nssmSrc) {
        Copy-Item $nssmSrc $NssmExe -Force
        Write-OK "nssm.exe 已复制到项目根目录"
    }
    else {
        Write-Err "解压后未找到 nssm-2.24\win64\nssm.exe"
        exit 1
    }

    # 清理临时文件
    Remove-Item $tempDir -Recurse -Force
    Remove-Item $zipPath -Force
    Write-OK "临时文件已清理"
}

$OutputDir = "$DistDir\$OutputName"
if (Test-Path $OutputDir) {
    Copy-Item $NssmExe "$OutputDir\nssm.exe" -Force
    Write-OK "nssm.exe 已复制到 $OutputDir\"
}

# ═══════════════════════════════════════════════════════════════
# 8. 生成 output 目录（ZIP + 安装包）
# ═══════════════════════════════════════════════════════════════
Write-Step "生成 output 目录"

$OutputZipDir = "$ScriptDir\output"
if (-not (Test-Path $OutputZipDir)) {
    New-Item -ItemType Directory -Path $OutputZipDir -Force | Out-Null
}
Write-OK "output 目录: $OutputZipDir"

# 读取版本号
$version = (Select-String -Path "pyproject.toml" -Pattern 'version\s*=\s*"([^"]+)"').Matches.Groups[1].Value
if (-not $version) { $version = "0.1.0" }
Write-OK "版本: $version"

# 创建 ZIP 压缩包（绿色版）
$zipFileName = "mcp-tool-hub-$version-win64.zip"
$zipPath = "$OutputZipDir\$zipFileName"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Write-OK "创建绿色版 ZIP: $zipFileName"
Compress-Archive -Path "$OutputDir\*" -DestinationPath $zipPath -CompressionLevel Optimal
$zipSize = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)
Write-OK "绿色版: $zipSize MB"

# ═══════════════════════════════════════════════════════════════
# 8. 汇总
# ═══════════════════════════════════════════════════════════════
Write-Host ""

if ($allGood) {
    $totalSize = [math]::Round((Get-ChildItem $OutputDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB, 2)
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  构建成功!" -ForegroundColor Green
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  输出目录: $OutputDir" -ForegroundColor White
    Write-Host "  总大小:   $totalSize MB" -ForegroundColor White
    Write-Host ""
    Write-Host "  运行服务端 (stdio): .\$OutputName\mcp-server.exe" -ForegroundColor White
    Write-Host "  运行服务端 (SSE):   .\$OutputName\mcp-server.exe --sse" -ForegroundColor White
    Write-Host "  运行管理界面:       .\$OutputName\mcp-client.exe" -ForegroundColor White
    Write-Host "  安装为 Windows 服务: .\$OutputName\nssm.exe" -ForegroundColor White
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Green
}
else {
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Red
    Write-Host "  构建存在问题，请检查上述错误" -ForegroundColor Red
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Red
    exit 1
}

# ═══════════════════════════════════════════════════════════════
# 9. Inno Setup 安装包（可选）
# ═══════════════════════════════════════════════════════════════
$buildInno = $Inno.IsPresent

if ($buildInno -and $allGood) {
    Write-Step "构建 Inno Setup 安装包"

    # 查找 ISCC（通过 PATH 环境变量）
    $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source

    if (-not $iscc) {
        Write-Warn "未找到 ISCC.exe，请将 Inno Setup 目录添加到 PATH 环境变量后重试"
    }
    else {
        Write-OK "ISCC: $iscc"

        # 清理 data 目录内运行数据，避免将日志和 SQLite 数据文件打包到安装程序中
        $dataDir = "$ScriptDir\data"
        if (Test-Path $dataDir) {
            Write-Step "清理 data 目录..."
            Get-ChildItem $dataDir -Force | Where-Object { $_.Name -notin '.gitignore', '.gitkeep' } | ForEach-Object {
                Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            }
            Write-OK "data 目录已清理"
        }

        # 读取版本号
        $version = (Select-String -Path "pyproject.toml" -Pattern 'version\s*=\s*"([^"]+)"').Matches.Groups[1].Value
        if (-not $version) { $version = "0.1.0" }
        Write-OK "版本: $version"

        $issFile = "$ScriptDir\setup.iss"
        if (-not (Test-Path $issFile)) {
            Write-Warn "未找到 setup.iss，跳过安装包构建"
        }
        else {
            $innoArgs = @($issFile, "/DVersion=$version")
            Write-OK "执行: ISCC $($innoArgs -join ' ')"

            $proc = Start-Process -FilePath $iscc `
                -ArgumentList $innoArgs `
                -NoNewWindow -Wait -PassThru

            if ($proc.ExitCode -ne 0) {
                Write-Err "Inno Setup 构建失败 (退出码: $($proc.ExitCode))"
            }
            else {
                $setupFile = Get-Item "output\mcp-tool-hub-$version-setup.exe" -ErrorAction SilentlyContinue
                if ($setupFile) {
                    $setupSize = [math]::Round($setupFile.Length / 1MB, 2)
                    Write-OK "安装包: $($setupFile.Name) ($setupSize MB)"
                }
                else {
                    Write-Warn "安装包已生成但未找到输出文件"
                }

                # 复制安装包到 output 目录（ISCC 已经输出到 output）
                Write-OK "安装包已生成到 output/ 目录"
            }
        }
    }
}

