# 阶段 4 实施记录

日期：2026-10-18（Asia/Shanghai）。对应任务：`webview2-shell-migration`。

## 结论

阶段 4 完成：Tauri NSIS 安装包与单文件便携版均已产出，两个产物分别为 80,333,964 与 80,247,980 bytes，都严格小于 100,000,000 bytes 门槛；安装、启动、卸载与便携版解压启动均实测通过。

## 体积问题的根因与解决

- 首版 NSIS 为 101,734,922 bytes，超限 1.73 MB。根因是 conda 环境的 OpenCV 自带 Qt5 + ICU（54.0 MB）并拆成 60 多个模块 DLL（连同 cv2.pyd 合计 165.6 MB）。
- 外科式裁剪不可行：单独移出 `opencv_gapi4100.dll` 或单独移出 Qt5+ICU，都会让打包后端的 cv2 导入失败（两者都是硬依赖，已实测）。
- 改用仓库既有的 `scripts/prepare_package_env.ps1` 专用环境（`opencv-python-headless==4.10.0.84`，脚本自带 headless 断言），重建后端：334.7 MB → 243.6 MB。
- 结果：NSIS 80,333,964 bytes；portable 80,247,980 bytes，余量约 19.7 MB。

## 交付内容

| 项 | 实现 |
|---|---|
| NSIS 配置 | `bundle.active=true`、`targets=["nsis"]`、currentUser、LZMA、简体中文；`webviewInstallMode=downloadBootstrapper`（不内嵌 Fixed Version / 离线安装器） |
| 前端 staging | Tauri 拒绝前端目录含 `node_modules`；staging 把裁剪器复制为 `cropper.min.js` 并改写 index.html 引用，目录保持 6 个白名单文件 |
| 发布入口 | `scripts/build_release.ps1` 改为六步：清理 → PyInstaller → 同步 → OCR 模型 → 前端 staging → Tauri 构建/portable → 体积门槛；保留 `-Target all/nsis/portable` 与 `-SkipOcrDownload` |
| 单文件便携版 | `scripts/portable.nsi` + `scripts/build_portable.ps1`，用 Tauri 自带的 makensis 生成；载荷解压到 `%LOCALAPPDATA%\yys-script-manager\portable-runtime\<版本>`，只打包宿主与 `backend`，不写注册表 |
| Runtime 检测 | 新增 `runtime.rs`：读 HKLM(32 位视图)/HKCU 的 EdgeUpdate 客户端版本；缺失时弹出带官方下载地址的对话框，点“重试”重新检测 |
| 退出边界 | 便携版 `ExecWait` 宿主退出后返回；安装版由 Tauri NSIS 管理卸载 |

## 实测结果

| 场景 | 结果 |
|---|---|
| NSIS 静默安装 `setup.exe /S /D=<临时目录>` | 退出码 0，安装目录含 `yys-desktop.exe`、`backend`、`uninstall.exe` |
| 安装版启动 | 窗口“阴阳师脚本工作台”出现，后端监听 8000 |
| 卸载 `uninstall.exe /S` | 退出码 0，安装目录清空；`%APPDATA%` 业务库仍在 |
| 便携版首次运行 | 自动解压到 `portable-runtime\1.0.0` 并启动，窗口“已连接”，后端监听 8000 |
| 便携版二次运行 | 跳过解压直接启动 |
| 体积门槛 | NSIS 80,333,964 bytes、portable 80,247,980 bytes，均 < 100,000,000 |

## 验证命令

```powershell
pwsh scripts/build_release.ps1 -SkipOcrDownload
# 输出末尾会逐个打印产物字节数与是否通过 100,000,000 门槛
```

## 本轮改动

- `gui/src-tauri/tauri.conf.json`：启用 NSIS 打包、resources、webviewInstallMode。
- `gui/src-tauri/src/runtime.rs`（新增）：Runtime 版本检测、缺失提示与重试。
- `gui/src-tauri/src/main.rs`：启动前检查 Runtime。
- `scripts/stage-tauri.cjs`：裁剪器避开 `node_modules`，改写页面引用。
- `scripts/build_release.ps1`：改为 Tauri 发布流水线。
- `scripts/build_portable.ps1`、`scripts/portable.nsi`（新增）：单文件便携版。

## 未覆盖与后续

1. Runtime 缺失/离线安装的实机矩阵未做：本机已安装 155.0.4283.62，只验证了检测分支与解析单测；卸载 Runtime 会影响机器上其他应用，未执行。
2. 快捷方式外观、安装目录选择页、旧版升级路径（Electron 安装版 → Tauri）未做图形化确认。
3. Windows 10 22H2、真实多屏拔插与多 DPI 仍未上机。
4. 便携版旧版本载荷目录不会自动清理（只保证不碰用户数据），清理策略留待后续。
