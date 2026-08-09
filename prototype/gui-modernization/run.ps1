$ErrorActionPreference = 'Stop'
$electron = Join-Path $PSScriptRoot '..\..\gui\node_modules\.bin\electron.cmd'

if (-not (Test-Path -LiteralPath $electron)) {
  throw "未找到现有 Electron 运行时：$electron"
}

& $electron (Join-Path $PSScriptRoot 'main.js')
