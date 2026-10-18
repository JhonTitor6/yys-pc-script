<#
用 Tauri 自带 NSIS 工具链生成单文件便携版。

用法（项目根目录）：
  pwsh scripts/build_portable.ps1
  pwsh scripts/build_portable.ps1 -ReleaseDir gui\src-tauri\target\release -Version 1.0.0

产物：dist-electron/阴阳师脚本工作台-<版本>-portable.exe
说明：载荷解压到 %LOCALAPPDATA%\yys-script-manager\portable-runtime\<版本>，
      永久数据库、截图、图片覆盖、window-state 与 WebView2 profile 都不在该目录。
#>

[CmdletBinding()]
param(
    [string]$ReleaseDir = 'gui\src-tauri\target\release',
    [string]$OutputDir = 'dist-electron',
    [string]$Version = '1.0.0',
    [string]$NsisExe = $(if ($env:YYS_MAKENSIS) {
        $env:YYS_MAKENSIS
    }
    else {
        Join-Path $env:LOCALAPPDATA 'tauri\NSIS\makensis.exe'
    })
)

$ErrorActionPreference = 'Stop'
$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
$releasePath = Join-Path $PROJECT_ROOT $ReleaseDir
$outputPath = Join-Path $PROJECT_ROOT $OutputDir
$outFile = Join-Path $outputPath "阴阳师脚本工作台-$Version-portable.exe"
$script = Join-Path $PSScriptRoot 'portable.nsi'
$icon = Join-Path $PROJECT_ROOT 'gui\icon.ico'

foreach ($required in @(
        (Join-Path $releasePath 'yys-desktop.exe'),
        (Join-Path $releasePath 'backend\yys-backend.exe'),
        $script,
        $NsisExe
    )) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "缺少打包输入：$required"
    }
}
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null
if (Test-Path -LiteralPath $outFile) { Remove-Item -LiteralPath $outFile -Force }

& $NsisExe "/DAPPDIR=$releasePath" "/DOUTPUTFILE=$outFile" "/DAPP_VERSION=$Version" "/DICON=$icon" $script
if ($LASTEXITCODE -ne 0) { throw "makensis 失败（exit code $LASTEXITCODE）" }
if (-not (Test-Path -LiteralPath $outFile)) { throw "未生成便携版：$outFile" }

$bytes = (Get-Item -LiteralPath $outFile).Length
Write-Host ("[build_portable] 产物：{0}" -f $outFile)
Write-Host ("[build_portable] 字节：{0:N0}（{1:N1} MB）" -f $bytes, ($bytes / 1MB))
if ($bytes -ge 100000000) { throw "便携版超过 100,000,000 bytes 门槛：$bytes" }
Write-Output $outFile
