<#
准备 Windows 发布专用 Python 环境。

用法（在项目根目录）：
  pwsh scripts/prepare_package_env.ps1
  $env:YYS_PYTHON = (Resolve-Path .\build\package-env\Scripts\python.exe).Path
  pwsh scripts/build_release.ps1 -Target nsis -SkipOcrDownload

可选：
  $env:YYS_BASE_PYTHON = 'D:/ProgramData/anaconda3/envs/win_macro/python.exe'
  pwsh scripts/prepare_package_env.ps1 -EnvPath 'D:/yys-package-env'

说明：RapidOCR 使用 --no-deps 安装，避免它把完整的 opencv-python 拉回环境。
#>

[CmdletBinding()]
param(
    [string]$BasePython = $(if ($env:YYS_BASE_PYTHON) {
        $env:YYS_BASE_PYTHON
    }
    else {
        "D:/ProgramData/anaconda3/envs/win_macro/python.exe"
    }),
    [string]$EnvPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'build\package-env')
)

$ErrorActionPreference = 'Stop'
$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot

if (-not [IO.Path]::IsPathRooted($EnvPath)) {
    $EnvPath = Join-Path $PROJECT_ROOT $EnvPath
}
$EnvPath = [IO.Path]::GetFullPath($EnvPath)
$EnvPython = Join-Path (Join-Path $EnvPath 'Scripts') 'python.exe'

if (-not (Test-Path -LiteralPath $BasePython)) {
    throw "基础 Python 不存在：$BasePython；可设置 YYS_BASE_PYTHON 覆盖。"
}

function Invoke-EnvPython {
    param([string[]]$Arguments)
    & $EnvPython @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "专用环境命令失败（exit code $LASTEXITCODE）：$($Arguments -join ' ')"
    }
}

if (-not (Test-Path -LiteralPath $EnvPython)) {
    Write-Host "[prepare_package_env] 创建环境：$EnvPath" -ForegroundColor Yellow
    & $BasePython -m venv $EnvPath
    if ($LASTEXITCODE -ne 0) {
        throw "创建专用环境失败（exit code $LASTEXITCODE）"
    }
}

$packages = @(
    'loguru==0.7.3',
    'mss==10.0.0',
    'numpy==1.26.4',
    'Pillow==11.1.0',
    'pywin32==308',
    'onnxruntime==1.22.1',
    'opencv-python-headless==4.10.0.84',
    'fastapi==0.141.1',
    'httpx==0.28.1',
    'uvicorn[standard]==0.52.3',
    'pyinstaller==6.22.0',
    'pyclipper==1.3.0.post6',
    'PyYAML==6.0.2',
    'shapely==2.1.1',
    'six==1.17.0',
    'tqdm==4.67.1'
)

Write-Host "[prepare_package_env] 安装固定版本依赖..." -ForegroundColor Yellow
Invoke-EnvPython (@('-m', 'pip', 'install', '--disable-pip-version-check') + $packages)
Invoke-EnvPython @(
    '-m', 'pip', 'install', '--disable-pip-version-check', '--no-deps',
    'rapidocr-onnxruntime==1.4.4'
)

$verify = @'
import importlib.metadata as metadata
import sys
import cv2
import onnxruntime
import rapidocr_onnxruntime

assert sys.prefix != sys.base_prefix, "必须使用 venv，不得直接使用 Conda 环境"
assert hasattr(cv2, "matchTemplate"), "OpenCV 缺少 matchTemplate"
providers = metadata.packages_distributions().get("cv2", [])
assert "opencv-python-headless" in providers, providers
assert not any(
    name in providers
    for name in ("opencv-python", "opencv-contrib-python", "opencv-contrib-python-headless")
), providers
print(f"cv2={cv2.__version__}; onnxruntime={onnxruntime.__version__}; rapidocr=ok")
'@

Write-Host "[prepare_package_env] 执行环境自检..." -ForegroundColor Yellow
Invoke-EnvPython @('-c', $verify)
Write-Host "[prepare_package_env] 完成：$EnvPython" -ForegroundColor Green
Write-Output $EnvPython
