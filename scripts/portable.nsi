; 单文件便携版：每次独立解压，等待宿主退出后清理，不安装、不写注册表。
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

; 永久数据由宿主固定写入 APPDATA；这里只使用 NSIS 自动清理的独立临时目录。
!define RUNTIME_DIR "$PLUGINSDIR\runtime"

Section "运行"
  InitPluginsDir
  ClearErrors
  SetOutPath "${RUNTIME_DIR}"
  File "${APPDIR}\yys-desktop.exe"
  SetOutPath "${RUNTIME_DIR}\backend"
  File /r "${APPDIR}\backend\*"
  IfErrors failed
  ClearErrors
  ExecWait '"${RUNTIME_DIR}\yys-desktop.exe"' $0
  IfErrors failed
  ; 当前工作目录不能被删除，离开载荷目录后再让 NSIS 回收 PLUGINSDIR。
  SetOutPath "$TEMP"
  SetErrorLevel $0
  Goto done
failed:
  SetOutPath "$TEMP"
  MessageBox MB_OK|MB_ICONSTOP "便携版解压或启动失败，请检查临时目录空间和文件访问权限。"
  SetErrorLevel 1
done:
SectionEnd
