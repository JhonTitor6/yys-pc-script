; 没有历史安装目录时，优先把默认目录放到 D 盘。
; electron-builder 已在此宏之前读取 HKCU/HKLM 的 InstallLocation，存在时不改写。
; 标准目录页通过独立计时器同步浏览结果。
; ThreadTimer.dll 来自 NSIS 官方插件页面，放在构建资源目录的 x86-unicode 下。
!addplugindir /x86-unicode "${BUILD_RESOURCES_DIR}\x86-unicode"

!ifndef BUILD_UNINSTALLER
Var yysDirectoryTimerStarted

Function yysShowDirectoryPage
  StrCmp $yysDirectoryTimerStarted 1 yysShowDirectoryPageDone
  GetFunctionAddress $0 yysDirectoryMonitor
  ThreadTimer::Start /NOUNLOAD 100 -1 $0
  StrCpy $yysDirectoryTimerStarted 1
  Call yysNormalizeDirectoryInput
yysShowDirectoryPageDone:
FunctionEnd

Function yysDirectoryMonitor
  FindWindow $0 "#32770" "" $HWNDPARENT
  GetDlgItem $1 $0 1019
  IntCmp $1 0 yysDirectoryMonitorDone

  ; 输入框获得焦点时不改写，避免用户手动输入路径时被打断。
  System::Call 'user32::GetFocus() p.r2'
  StrCmp $2 $1 yysDirectoryMonitorDone
  Call yysNormalizeDirectoryInput
yysDirectoryMonitorDone:
FunctionEnd

Function yysNormalizeDirectoryInput
  FindWindow $0 "#32770" "" $HWNDPARENT
  GetDlgItem $1 $0 1019
  IntCmp $1 0 yysNormalizeDirectoryInputDone

  System::Call 'user32::GetWindowText(i r1, t.r2, i ${NSIS_MAX_STRLEN})'
  StrLen $3 "${APP_FILENAME}"
  StrLen $4 $2
  IntOp $4 $4 - $3
  StrCpy $5 $2 $3 $4
  StrCmp $5 "${APP_FILENAME}" yysNormalizeDirectoryInputDone

  StrCpy $6 $2 1 -1
  StrCmp $6 "\" yysDirectoryInputHasSeparator
  StrCpy $2 "$2\${APP_FILENAME}"
  Goto yysDirectoryInputUpdated
yysDirectoryInputHasSeparator:
  StrCpy $2 "$2${APP_FILENAME}"
yysDirectoryInputUpdated:
  SendMessage $1 0x000C 0 "STR:$2"
yysNormalizeDirectoryInputDone:
FunctionEnd

Function .onGUIEnd
  ThreadTimer::Stop
FunctionEnd
!endif

!macro customInit
  ReadRegStr $0 HKCU "${INSTALL_REGISTRY_KEY}" InstallLocation
  ${if} $0 == ""
    ReadRegStr $0 HKLM "${INSTALL_REGISTRY_KEY}" InstallLocation
  ${endif}
  ${StdUtils.GetParameter} $1 "D" ""

  ; 旧版本可能把父目录写入 InstallLocation；先补齐应用目录，
  ; 这样目录页显示的默认值就和 electron-builder 的实际安装路径一致。
  ${if} $0 != ""
  ${andIf} $1 == ""
    StrLen $2 "${APP_FILENAME}"
    StrLen $3 $0
    IntOp $3 $3 - $2
    StrCpy $4 $0 $2 $3
    StrCmp $4 "${APP_FILENAME}" existing_install_dir
    StrCpy $INSTDIR "$0\${APP_FILENAME}"
    existing_install_dir:
  ${endif}

  ${if} $0 == ""
  ${andIf} $1 == ""
    IfFileExists "D:\*.*" 0 no_d_drive
    StrCpy $INSTDIR "D:\${APP_FILENAME}"
    no_d_drive:
  ${endif}

  Call yysShowDirectoryPage
!macroend
