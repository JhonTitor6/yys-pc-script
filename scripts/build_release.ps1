<#
一键打包脚本：PyInstaller -> 同步产物 -> OCR 模型 -> electron-builder

用法（在项目根目录）：
  pwsh scripts/build_release.ps1
  pwsh scripts/build_release.ps1 -SkipOcrDownload   # 跳过 OCR 模型下载
  pwsh scripts/build_release.ps1 -Target portable   # 只出 portable
  pwsh scripts/build_release.ps1 -Target nsis       # 只出 NSIS 安装包

前置条件：
  - Node 20+ 和 npm 已安装
  - conda 环境 win_macro 已就绪（默认路径 D:/ProgramData/anaconda3/envs/win_macro）
  - 首次运行会把当前 Python 环境内的 RapidOCR 模型复制到 assets/（无需联网下载）

注意：
  - Windows PowerShell 5.x 不支持 `n 转义在 Write-Host 中的展开，所以空行都用
    独立 Write-Host "" 输出，兼容 5.x 与 7.x。
  - $LASTEXITCODE 会被管道覆盖，所以每条命令后立即保存到局部变量。
#>

param(
    [switch]$SkipOcrDownload,
    [ValidateSet('all', 'nsis', 'portable')]
    [string]$Target = 'all'
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
$PYTHON = "D:/ProgramData/anaconda3/envs/win_macro/python.exe"

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
Write-Host "[build_release] Python  ：$PYTHON" -ForegroundColor Cyan
Write-Host "[build_release] 目标    ：$Target" -ForegroundColor Cyan

Push-Location $PROJECT_ROOT
try {
    # 1) 清理旧产物
    Write-StepHeader "[1/5] 清理旧产物..."
    foreach ($p in @('dist', 'gui\build', 'dist-electron')) {
        $full = Join-Path $PROJECT_ROOT $p
        if (Test-Path $full) {
            Remove-Item -Recurse -Force $full
            Write-Host "  - 已删除 $p"
        }
    }

    # 2) 安装/更新 Python 依赖
    Write-StepHeader "[2/5] 安装 Python 依赖..."
    $ec = Invoke-External { & $PYTHON -m pip install -r requirements.txt pyinstaller 2>&1 | Out-Host }
    if ($ec -ne 0) { throw "pip install 失败（exit code $ec）" }

    # 3) PyInstaller 打包后端（--onedir）
    Write-StepHeader "[3/5] PyInstaller 打包后端..."
    $ec = Invoke-External { & $PYTHON -m PyInstaller build_backend.spec --clean --noconfirm 2>&1 | Out-Host }
    if ($ec -ne 0) { throw "PyInstaller 失败（exit code $ec）" }
    if (-not (Test-Path 'dist\backend\yys-backend.exe')) {
        throw "PyInstaller 产物 dist\backend\yys-backend.exe 不存在"
    }

    # 4) 准备 OCR 模型
    Write-StepHeader "[4/5] 准备 OCR 模型..."
    if ($SkipOcrDownload) {
        Write-Host "  - 跳过（-SkipOcrDownload）"
    }
    else {
        $ec = Invoke-External { & $PYTHON scripts/download_ocr_models.py 2>&1 | Out-Host }
        if ($ec -ne 0) { throw "OCR 模型下载失败（exit code $ec）" }
    }

    # 5) electron-builder 打包
    Write-StepHeader "[5/5] electron-builder 打包..."
    Push-Location gui
    try {
        if (-not (Test-Path 'node_modules\electron-builder')) {
            Write-Host "  - 安装 npm 依赖..."
            $ec = Invoke-External { npm install 2>&1 | Out-Host }
            if ($ec -ne 0) { throw "npm install 失败（exit code $ec）" }
        }

        switch ($Target) {
            'nsis'     { $ec = Invoke-External { npm run build:nsis 2>&1 | Out-Host } }
            'portable' { $ec = Invoke-External { npm run build:portable 2>&1 | Out-Host } }
            default    { $ec = Invoke-External { npm run build:win 2>&1 | Out-Host } }
        }
        if ($ec -ne 0) { throw "electron-builder 失败（exit code $ec）" }
    }
    finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "[build_release] 全部完成！产物在 dist-electron/ 下：" -ForegroundColor Green
    Get-ChildItem -Path dist-electron -Filter '*.exe' -ErrorAction SilentlyContinue |
        ForEach-Object { Write-Host "  $($_.FullName)" }
}
catch {
    Write-Host ""
    Write-Host "[build_release] 失败：$_" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
