# 阶段 4 实施记录

日期：2026-10-18（Asia/Shanghai）。对应任务：`webview2-shell-migration`。

## 结论

阶段 4 完成：Tauri NSIS 安装包与单文件便携版均已产出，分别为 80,335,700 与 80,264,275 bytes，都严格小于 100,000,000 bytes 门槛；安装（默认 D 盘）、快捷方式、启动、卸载、便携版解压启动、Runtime 缺失提示均已实测通过。

## 体积问题的根因与解决

- 首版 NSIS 为 101,734,922 bytes，超限 1.73 MB。根因是 conda 环境的 OpenCV 自带 Qt5 + ICU（54.0 MB）并拆成 60 多个模块 DLL（连同 cv2.pyd 合计 165.6 MB）。
- 外科式裁剪不可行：单独移出 `opencv_gapi4100.dll` 或单独移出 Qt5+ICU，都会让打包后端的 cv2 导入失败（两者都是硬依赖，已实测）。
- 改用仓库既有的 `scripts/prepare_package_env.ps1` 专用环境（`opencv-python-headless==4.10.0.84`，脚本自带 headless 断言），重建后端：334.7 MB → 243.6 MB。
- 结果：NSIS 80,335,700 bytes；portable 80,264,275 bytes，余量约 19.7 MB。

## 交付内容

| 项 | 实现 |
|---|---|
| NSIS 配置 | `bundle.active=true`、`targets=["nsis"]`、currentUser、LZMA、简体中文；`webviewInstallMode=downloadBootstrapper`（不内嵌 Fixed Version / 离线安装器） |
| 安装目录 | 自定义 NSIS 模板（基于 tauri-cli-v2.12.2，MIT）：currentUser 默认 `D:\<产品名>`（D 盘不存在时回退 `%LOCALAPPDATA%`）；复用旧 InstallLocation 前先验证目录仍存在 |
| 前端 staging | Tauri 拒绝前端目录含 `node_modules`；staging 把裁剪器复制为 `cropper.min.js` 并改写 index.html 引用，目录保持 6 个白名单文件 |
| 发布入口 | `scripts/build_release.ps1` 六步：清理 → PyInstaller → 同步 → OCR 模型 → staging → Tauri 构建/portable → 体积门槛；保留 `-Target all/nsis/portable` 与 `-SkipOcrDownload` |
| 单文件便携版 | `scripts/portable.nsi` + `scripts/build_portable.ps1`，Tauri 自带 makensis 生成；只打包宿主与 `backend`，解压到 `%LOCALAPPDATA%\yys-script-manager\portable-runtime\<版本>`，不写注册表 |
| Runtime 检测 | `runtime.rs` 读 HKLM(32 位视图)/HKCU 的 EdgeUpdate 版本；缺失时弹出官方下载地址与“重试/取消”，取消后只退出、不再叠加第二个错误框 |
| 调试模拟 | 仅调试构建支持 `YYS_FORCE_NO_RUNTIME=1`，用于验证缺失提示，不影响发布产物 |

## 实测结果

| 场景 | 结果 |
|---|---|
| NSIS 静默安装（不带 /D） | 退出码 0，默认安装到 `D:\阴阳师脚本工作台` |
| 快捷方式 | 开始菜单 `阴阳师脚本工作台.lnk`、桌面 `D:\Users\56440\Desktop\阴阳师脚本工作台.lnk` 均指向 `D:\阴阳师脚本工作台\yys-desktop.exe` |
| 安装版启动 | 窗口“阴阳师脚本工作台”出现，后端监听 8000 |
| 卸载 `uninstall.exe /S` | 退出码 0；安装目录、开始菜单与桌面快捷方式全部移除；`%APPDATA%` 业务库保留 |
| 便携版首次运行 | 解压到 `portable-runtime\1.0.0` 并启动，“已连接”，后端监听 8000 |
| 便携版二次运行 | 跳过解压直接启动 |
| Runtime 缺失 | 弹窗显示官方地址，取消后进程退出码 1，未建窗、未起后端、无第二个对话框（截图 `build/e2e-runtime-missing.png`） |
| 体积门槛 | NSIS 80,335,700 bytes、portable 80,264,275 bytes，均 < 100,000,000 |

## 验证命令

```powershell
pwsh scripts/build_release.ps1 -SkipOcrDownload
# 输出末尾会逐个打印产物字节数与是否通过 100,000,000 门槛
```

## 本轮改动

- `gui/src-tauri/tauri.conf.json`：启用 NSIS 打包、resources、webviewInstallMode、自定义模板。
- `gui/src-tauri/installer.nsi.template`（新增）：D 盘默认安装目录 + 旧位置存在性校验。
- `gui/src-tauri/src/runtime.rs`（新增）：Runtime 检测、缺失提示、重试、调试模拟。
- `gui/src-tauri/src/main.rs`：启动前检查 Runtime；取消时不再弹第二个错误框。
- `scripts/stage-tauri.cjs`：裁剪器避开 `node_modules` 并改写页面引用。
- `scripts/build_release.ps1`：改为 Tauri 发布流水线。
- `scripts/build_portable.ps1`、`scripts/portable.nsi`（新增）：单文件便携版。

## 未覆盖与后续

1. 旧 Electron 安装版（`D:\Program Files\新建文件夹\yys-script-manager`）到新 Tauri 包的原位升级未做图形化确认；模板只保证“旧 Tauri 安装位置复用”，不识别 electron-builder 的注册表键。
2. Windows 10 22H2、真实多屏拔插与多 DPI 仍未上机。
3. 便携版旧版本载荷目录不会自动清理（只保证不碰用户数据）。
4. 自定义模板与 Tauri CLI 版本绑定；升级 CLI 时必须重新对比上游模板。
