<#
一键打包（Tauri）：PyInstaller 后端 -> 前端 staging -> Tauri NSIS -> 单文件 portable

用法（在项目根目录）：
  pwsh scripts/prepare_package_env.ps1            # 首次准备打包专用环境
  $env:YYS_PYTHON = (Resolve-Path .\build\package-env\Scripts\python.exe).Path
  pwsh scripts/build_release.ps1                   # NSIS + portable
  pwsh scripts/build_release.ps1 -Target nsis      # 只出 NSIS
  pwsh scripts/build_release.ps1 -Target portable  # 只出 portable
  pwsh scripts/build_release.ps1 -SkipOcrDownload  # 跳过 OCR 模型准备

产物：
  gui/src-tauri/target/release/bundle/nsis/阴阳师脚本工作台_<版本>_x64-setup.exe
  dist-electron/阴阳师脚本工作台-<版本>-portable.exe

门槛：两个产物都必须严格小于 100,000,000 bytes，任一超出即失败。
#>

param(
    [switch]$SkipOcrDownload,
    [ValidateSet('all', 'nsis', 'portable')]
    [string]$Target = 'all'
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
$PYTHON = if ($env:YYS_PYTHON) {
    $env:YYS_PYTHON
}
else {
    Join-Path $PROJECT_ROOT 'build\package-env\Scripts\python.exe'
}
$MAX_BYTES = 100000000

function Write-StepHeader {
    param([string]$Text)
    Write-Host ""
    Write-Host $Text -ForegroundColor Yellow
}

function Invoke-External {
    # 用 & call + 立即保存 $LASTEXITCODE，避免被 | Out-Null 等管道覆盖
    param([scriptblock]$Cmd)
    & $Cmd
    return $LASTEXITCODE
}

Write-Host "[build_release] 项目根：$PROJECT_ROOT" -ForegroundColor Cyan
Write-Host "[build_release] Python ：$PYTHON" -ForegroundColor Cyan
Write-Host "[build_release] 目标   ：$Target" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $PYTHON)) {
    Write-Host "[build_release] 打包环境不存在：$PYTHON" -ForegroundColor Red
    Write-Host "  先运行 pwsh scripts/prepare_package_env.ps1，或设置 YYS_PYTHON。" -ForegroundColor Red
    exit 1
}

Push-Location $PROJECT_ROOT
try {
    # 1) 清理旧产物（只清理本流程自己的目录，不碰 build/tauri-target 编译缓存）
    Write-StepHeader "[1/6] 清理旧产物..."
    foreach ($p in @('dist', 'dist-electron', 'gui\build\tauri-frontend')) {
        $full = Join-Path $PROJECT_ROOT $p
        if (Test-Path $full) {
            Remove-Item -Recurse -Force $full
            Write-Host "  - 已删除 $p"
        }
    }

    # 2) PyInstaller 打包后端（专用 headless 环境）
    Write-StepHeader "[2/6] PyInstaller 打包后端..."
    $ec = Invoke-External { & $PYTHON -m PyInstaller build_backend.spec --clean --noconfirm 2>&1 | Out-Host }
    if ($ec -ne 0) { throw "PyInstaller 失败（exit code $ec）" }
    if (-not (Test-Path 'dist\backend\yys-backend.exe')) {
        throw "PyInstaller 产物 dist\backend\yys-backend.exe 不存在"
    }
    $ec = Invoke-External { node scripts/sync-backend.js 2>&1 | Out-Host }
    if ($ec -ne 0) { throw "同步后端失败（exit code $ec）" }

    # 3) OCR 模型
    Write-StepHeader "[3/6] 准备 OCR 模型..."
    if ($SkipOcrDownload) {
        Write-Host "  - 跳过（-SkipOcrDownload）"
    }
    else {
        $ec = Invoke-External { & $PYTHON scripts/download_ocr_models.py 2>&1 | Out-Host }
        if ($ec -ne 0) { throw "OCR 模型准备失败（exit code $ec）" }
    }

    # 4) 前端 staging（受控六个文件 + 图片 ID 清单）
    Write-StepHeader "[4/6] 前端 staging..."
    $ec = Invoke-External { node scripts/stage-tauri.cjs 2>&1 | Out-Host }
    if ($ec -ne 0) { throw "前端 staging 失败（exit code $ec）" }

    # 5) Tauri 构建（NSIS 与/或 release 目录）
    Write-StepHeader "[5/6] Tauri 构建..."
    Push-Location gui
    try {
        if ($Target -eq 'portable') {
            $ec = Invoke-External { & .\node_modules\.bin\tauri.cmd build --no-bundle 2>&1 | Out-Host }
        }
        else {
            $ec = Invoke-External { & .\node_modules\.bin\tauri.cmd build --bundles nsis 2>&1 | Out-Host }
        }
        if ($ec -ne 0) { throw "tauri build 失败（exit code $ec）" }
    }
    finally {
        Pop-Location
    }

    # 6) 单文件 portable + 体积门槛
    Write-StepHeader "[6/6] 收集产物并检查体积..."
    $artifacts = @()
    $nsisDir = 'gui\src-tauri\target\release\bundle\nsis'
    if ($Target -ne 'portable') {
        $setup = Get-ChildItem -Path $nsisDir -Filter '*.exe' -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not $setup) { throw "未找到 NSIS 安装包" }
        $artifacts += $setup.FullName
    }
    if ($Target -ne 'nsis') {
        $ec = Invoke-External { pwsh -NoProfile -File scripts\build_portable.ps1 2>&1 | Out-Host }
        if ($ec -ne 0) { throw "便携版构建失败（exit code $ec）" }
        $artifacts += (Get-ChildItem -Path 'dist-electron' -Filter '*-portable.exe' |
                Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
    }

    $failed = $false
    foreach ($artifact in $artifacts) {
        $bytes = (Get-Item -LiteralPath $artifact).Length
        $ok = $bytes -lt $MAX_BYTES
        if (-not $ok) { $failed = $true }
        $state = if ($ok) { '通过' } else { '超限' }
        Write-Host ("  {0}  {1:N0} bytes  [{2}]" -f (Split-Path $artifact -Leaf), $bytes, $state) -ForegroundColor $(if ($ok) { 'Green' } else { 'Red' })
    }
    if ($failed) { throw "存在超过 $MAX_BYTES bytes 的产物，停止发布" }

    Write-Host ""
    Write-Host "[build_release] 全部完成：" -ForegroundColor Green
    foreach ($artifact in $artifacts) { Write-Host "  $artifact" }
}
catch {
    Write-Host ""
    Write-Host "[build_release] 失败：$_" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
