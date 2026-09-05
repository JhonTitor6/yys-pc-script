!macro customInit
  ; 只在初始化阶段设置安装目录，不从线程定时器调用 NSIS 控件。
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
    Goto install_dir_ready
    existing_install_dir:
    StrCpy $INSTDIR "$0"
    install_dir_ready:
  ${endif}

  ${if} $0 == ""
  ${andIf} $1 == ""
    IfFileExists "D:\*.*" 0 no_d_drive
    StrCpy $INSTDIR "D:\${APP_FILENAME}"
    no_d_drive:
  ${endif}

!macroend
