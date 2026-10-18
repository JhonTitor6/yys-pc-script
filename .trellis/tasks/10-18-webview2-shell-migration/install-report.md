# Tauri 2 工具链安装报告

日期：2026-10-18（Asia/Shanghai）  
范围：只完成阶段 0 获准的安装和安装验证；未开发正式宿主、未改产品代码或前端清单。

## 结论

获准的 Rust/MSVC 工具链、Windows SDK、项目本地 Tauri CLI 与隔离依赖探针均已安装并验证通过。Visual Studio 2019 与 MSVC 14.29.30133 保持原版本；安装器没有要求重启，当前也没有待重启标记。没有人工 UAC 提示，因为执行会话已有管理员提升权限。

## 安装版本与路径

| 项目 | 已安装内容 | 路径/状态 |
|---|---|---|
| Rustup | 1.29.1 | `C:\Users\56440\.cargo\bin\rustup.exe` |
| Rust | 1.99.1，默认 host `x86_64-pc-windows-msvc`；包含 Cargo | `C:\Users\56440\.rustup\toolchains\1.99.1-x86_64-pc-windows-msvc` |
| 已安装 target | `x86_64-pc-windows-msvc` | 与 host 相同，已由 `rustup target list --installed` 确认 |
| Visual Studio | Community 2019 `16.11.36422.26` | `C:\Program Files (x86)\Microsoft Visual Studio\2019\Community`，版本未变 |
| MSVC | v142 `14.29.30133`；`cl.exe` 文件版本 `19.29.30159.0` | 使用原有 x64/x86 工具，没有新增或替换工具集 |
| Windows SDK | VS 组件 `Microsoft.VisualStudio.Component.Windows10SDK.19041`；SDK 文件目录版本 `10.0.19041.0` | `C:\Program Files (x86)\Windows Kits\10`；VS 包记录版本 `10.0.19041.4` |
| Tauri Node CLI | `@tauri-apps/cli@2.12.2`，精确版本 | 本地安装于 `build/tauri-tools`；`tauri --version` 输出 `tauri-cli 2.12.2` |
| Tauri Rust 依赖探针 | `tauri = 2.12.3`、`tauri-build = 2.7.2` | `build/tauri-deps-probe`；Cargo 锁文件仅属于此探针 |

VS 安装器只添加了上述 Windows SDK 组件，没有添加 VS workload 或新 MSVC。该 SDK 组件的微软安装包内部同时选择了其 SDK 功能组（日志含 Desktop C++ x64/x86/ARM/ARM64、UWP、签名与 App Certification 等项）；这由 SDK 组件安装器的 feature 清单带入，不是额外选择的 VS workload。

## 执行摘要与官方来源

- Rustup 安装器来自 [Rust 官方 Windows 安装页](https://rust-lang.org/tools/install/) 和 `static.rust-lang.org`。执行 `rustup-init.exe -y --default-host x86_64-pc-windows-msvc --default-toolchain 1.99.1 --profile minimal --no-modify-path`，随后以 Rustup 安装精确 toolchain。下载的安装器 Authenticode 状态为 `NotSigned`，但其 SHA-256 与同一官方目录提供的 `.sha256` 文件一致：`6F4BEF66261261FCB43131BE8720BAB817D403A09EDEC7455C371974B90BDB7E`。Rust 版本与官方 [1.99.1 channel manifest](https://static.rust-lang.org/dist/channel-rust-1.99.1.toml) 相符。
- 按[微软 VS 命令行参数文档](https://learn.microsoft.com/en-us/visualstudio/install/use-command-line-parameters-to-install-visual-studio)及[Community 组件 ID 文档](https://learn.microsoft.com/en-us/visualstudio/install/workload-component-id-vs-community?view=visualstudio)，对现有 VS 2019 执行 `setup.exe modify --installPath <VS2019 Community> --channelId VisualStudio.16.Release --add Microsoft.VisualStudio.Component.Windows10SDK.19041 --passive --norestart`。VS Installer 与 SDK 下载包来自微软官方渠道，包日志记录 SHA-256 校验成功。
- Node CLI 从官方 [npm registry](https://registry.npmjs.org/@tauri-apps/cli/2.12.2) 安装：`npm install --prefix build/tauri-tools --save-dev --save-exact @tauri-apps/cli@2.12.2 --registry https://registry.npmjs.org/`。没有修改 `gui/package.json` 或 `gui/package-lock.json`。
- Cargo 从默认官方 crates.io registry 解析并恢复精确版本；探针执行 `cargo generate-lockfile` 和 `cargo check --target x86_64-pc-windows-msvc --locked`。版本来源：[tauri 2.12.3](https://crates.io/crates/tauri/2.12.3)、[tauri-build 2.7.2](https://crates.io/crates/tauri-build/2.7.2)。
- Windows 前置条件与 MSVC host 选择参照 [Tauri 官方 prerequisites](https://v2.tauri.app/start/prerequisites/)。

## 验证结果

1. `rustup show` 显示默认且 active toolchain 为 `1.99.1-x86_64-pc-windows-msvc`；`rustc --version --verbose` 为 `rustc 1.99.1 (58cf8f9c3 2026-10-13)`，`cargo --version` 为 `cargo 1.99.1 (5f94df478 2026-08-27)`。
2. `vswhere` 已能以 `Microsoft.VisualStudio.Component.Windows10SDK.19041` 查询到原 VS 2019 实例。`VsDevCmd.bat -host_arch=x64 -arch=x64` 输出 `VCToolsVersion=14.29.30133`、`WindowsSDKVersion=10.0.19041.0`；`INCLUDE`/`LIB` 所指 SDK 路径中的以下文件均存在：
   - 头文件：`C:\Program Files (x86)\Windows Kits\10\Include\10.0.19041.0\um\Windows.h`
   - x64 库：`C:\Program Files (x86)\Windows Kits\10\Lib\10.0.19041.0\um\x64\user32.lib`
   - UCRT 头/库及 `bin\10.0.19041.0\x64\rc.exe` 也存在。
3. 使用 Rust 1.99.1 对忽略目录内的 `windows_link_probe.rs` 执行 MSVC x64 链接；它显式引用 `user32.lib` 并成功生成 `windows_link_probe.exe`（126,464 bytes）。未运行该探针或任何产品应用。
4. 本地 CLI 返回 `tauri-cli 2.12.2`，`npm ls` 显示仅安装 `@tauri-apps/cli@2.12.2`。
5. Cargo 锁定 406 个探针依赖；锁文件确认 `tauri 2.12.3` 与 `tauri-build 2.7.2`。目标为 `x86_64-pc-windows-msvc` 的 `cargo check --locked` 成功，包含 `tauri`、`tauri-build`、`tao` 与 `webview2-com` 的编译检查。
6. SDK 安装命令最终退出码为 0，安装日志没有重启要求；安装后系统未显示 pending reboot。三份阶段 0 数据库快照及 manifest 哈希与执行前一致。

## 锁文件与 Git 边界

- 正式 `gui/src-tauri/Cargo.toml`、正式项目 `Cargo.lock` 尚不存在，本次没有创建它们。
- Cargo 探针的 `build/tauri-deps-probe/Cargo.lock` 与 Node 探针的 `build/tauri-tools/package-lock.json` 均位于 `.gitignore:20` 覆盖的 `build/` 下；Cargo 锁文件只表示独立探针解析结果。
- `@tauri-apps/api` 未安装（现有纯 JS 可使用官方全局 API）；没有安装全局 `cargo-tauri`。
- 执行前后 HEAD 均为 `d11c01f9730c4fa376da7dfaa1988e2a08f43986`。本次没有暂存、提交或推送；除本报告所在的既有未跟踪任务目录外，最终 Git 状态没有其他路径。
- 未触碰 8000 端口、旧 portable、游戏、用户 profile、截图、图片覆盖、源数据库或构建产物；未运行产品测试、正式 Tauri 宿主或工作台。

## 磁盘与环境影响

- 安装后 Windows SDK 根目录共 9,537 个文件、1,594,889,976 bytes。C 盘在 VS SDK 修改前可用 21,542,252,544 bytes，最终复核时可用 18,395,594,752 bytes；期间净减少约 3,146,657,792 bytes（包含 SDK/VS 安装缓存及 Cargo registry 缓存）。
- Rustup 标准目录当前大小：`C:\Users\56440\.rustup` 619,188,846 bytes；`C:\Users\56440\.cargo` 346,016,033 bytes。Cargo 缓存使用默认用户目录。
- 忽略目录中的 `build/tauri-tools` 为 29,231,756 bytes；`build/tauri-deps-probe`（含编译目标文件）为 1,693,326,678 bytes。两者均由 `git check-ignore` 确认忽略。
- 只在用户级 `Path` 末尾追加 `C:\Users\56440\.cargo\bin`；没有覆盖原条目，也没有改系统 PATH。当前已运行的终端不会自动刷新环境；新进程读取更新后的用户环境后可直接使用 Rust。如果 Codex 启动的终端仍继承旧环境，需要重开终端或 Codex 应用。没有设置 `CARGO_HOME` 或 `RUSTUP_HOME`。

## 安装过程中的修正与未完成项

- 第一次 VS Installer 命令因 PowerShell 参数中未给含空格的安装路径加引号，被安装器解析为 `C:\Program`，退出码 1，未安装组件。查看安装日志后修正引号并重试；最终只添加 19041 SDK 组件，退出码 0。
- rustup 第一次取官方 channel 文件时遇到 TLS 握手断开；确认官方端点可达后重试成功，toolchain 安装和版本核验均通过。
- 阶段 0 的安装范围已完成。正式 Tauri 宿主、正式依赖清单与 Cargo.lock，以及产品构建/运行验证仍待原会话检查规划并另行授权；本报告不表示这些项目已实施。