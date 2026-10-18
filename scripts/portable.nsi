; 单文件便携版：自解压到版本化载荷目录后启动宿主，不安装、不写注册表。
; 由 scripts/build_portable.ps1 传入 APPDIR / OUTPUTFILE / APP_VERSION / ICON。
Unicode true

!ifndef APP_VERSION
  !define APP_VERSION "1.0.0"
!endif
!ifndef APPDIR
  !error "缺少 /DAPPDIR（要打包的发布目录）"
!endif
!ifndef OUTPUTFILE
  !error "缺少 /DOUTPUTFILE（单文件产物路径）"
!endif

Name "阴阳师脚本工作台"
BrandingText "便携版 ${APP_VERSION}"
OutFile "${OUTPUTFILE}"
RequestExecutionLevel user
SilentInstall silent
SetCompressor /SOLID lzma
!ifdef ICON
  Icon "${ICON}"
!endif

; 载荷只落在版本化子目录，永久数据库/截图/profile 都在别处，清理不会碰到用户数据。
!define RUNTIME_BASE "$LOCALAPPDATA\yys-script-manager\portable-runtime"
!define RUNTIME_DIR "${RUNTIME_BASE}\${APP_VERSION}"

Section "运行"
  IfFileExists "${RUNTIME_DIR}\yys-desktop.exe" check_backend
  Goto extract
check_backend:
  IfFileExists "${RUNTIME_DIR}\backend\yys-backend.exe" launch
extract:
  CreateDirectory "${RUNTIME_DIR}"
  SetOutPath "${RUNTIME_DIR}"
  File "${APPDIR}\yys-desktop.exe"
  SetOutPath "${RUNTIME_DIR}\backend"
  File /r "${APPDIR}\backend\*"
launch:
  ExecWait '"${RUNTIME_DIR}\yys-desktop.exe"' $0
  SetErrorLevel $0
SectionEnd
