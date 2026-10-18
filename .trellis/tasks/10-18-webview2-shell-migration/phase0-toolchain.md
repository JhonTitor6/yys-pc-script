# 阶段 0：Tauri 工具链基线核验

> 本文保留安装前工具链基线。后续缺失项已按用户授权补装，且原会话验收通过；当前事实以 install-report.md 和 installation-review.md 为准，下文“缺失”描述不代表安装后的状态。

核验日期：2026-10-18（Asia/Shanghai）  
范围：只读检查；未安装、下载、恢复或构建任何依赖，未启动工作台或游戏。

## 结论

阶段 0 的工具链核验已完成，但还不能进入 Tauri 阶段 1。当前机器有可供 Rust 使用的 MSVC x64/x86 编译器和 MSBuild，缺少可确认的 Windows SDK；Rust、Cargo、rustup 和 Tauri CLI 均未安装或不在常见位置。阶段 1 的最小阻断项是补齐 Windows SDK 与 Rust MSVC 工具链，然后在实际安装前重新核对版本并生成锁文件。

现有 electron-builder 缓存中有 NSIS 3.0.4.1、NSIS 资源 3.4.1 和 7-Zip，可作为 Tauri NSIS/portable 调查的候选缓存。它们属于 electron-builder 缓存，尚未证明 Tauri bundler 会自动复用；本阶段没有执行 `makensis`、7-Zip 或任何构建。

## MSVC、SDK 与 MSBuild

`C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe` 可用。`vswhere` 定位到完整的 Visual Studio Community 2019 实例：

| 项目 | 实测值 |
|---|---|
| 安装实例 | Visual Studio Community 2019 |
| 安装版本 | 16.11.36422.26（产品显示 16.11.51） |
| 安装目录 | `C:\Program Files (x86)\Microsoft Visual Studio\2019\Community` |
| MSVC 工具集 | 14.29.30133 |
| x64 编译器 | `VC\Tools\MSVC\14.29.30133\bin\Hostx64\x64\cl.exe`，文件版本 19.29.30159.0 |
| x86 编译器 | `VC\Tools\MSVC\14.29.30133\bin\Hostx64\x86\cl.exe`，文件版本 19.29.30159.0 |
| x64 MSBuild | `MSBuild\Current\Bin\amd64\MSBuild.exe`，文件版本 16.11.6.22506 |
| 32 位 MSBuild | `MSBuild\Current\Bin\MSBuild.exe`，文件版本 16.11.6.22506 |

`vswhere -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64` 能返回该实例及上述 x64/x86 编译器。对 Windows 8.1 SDK、Windows 10 SDK 10.0.10240/14393/17763/18362/19041/20348、Windows 11 SDK 22000/22621 的组件查询均没有返回实例。

本机可见的 `C:\Program Files (x86)\Windows Kits\8.1` 只有 `References` 目录；没有 `Windows Kits\10` 或 `Windows Kits\11` 的目录、头文件、库或 `rc.exe`。对应的 Windows SDK 注册表键（`HKLM/HKCU` 下 v10.0、v8.1 及 WOW6432Node）也不存在。因此当前结论是：

- MSVC x64/x86 和 MSBuild 已具备，可保留。
- Windows SDK 未核实到，Tauri Windows 链接阶段不能视为可用。
- 不需要另装一套 Visual Studio IDE；阶段 1 前应在现有 VS Installer 实例中补齐 Windows SDK（建议 Windows 10 SDK 10.0.19041.0，或经验证的更新版本）并重新运行 `vswhere` 组件检查。

## electron-builder 缓存与 NSIS 候选

只读检查 `C:\Users\56440\AppData\Local\electron-builder\Cache` 得到：

| 缓存 | 位置或版本 | 状态 |
|---|---|---|
| NSIS 主工具集 | `nsis\nsis-3.0.4.1` | 存在 `Bin\makensis.exe`（439,296 bytes）、`NSIS.exe`、`Include`、`Plugins`、`Stubs` 等完整目录 |
| NSIS 资源 | `nsis\nsis-resources-3.4.1-2jx2y` 与 `nsis-resources-3.4.1.7z` | 已缓存；存在对应 `.state` 文件 |
| 7-Zip（electron-builder） | `7zip@1.0.0\7zip-win-x64-a34pt\bin\7za.exe` | 文件版本 24.09，849,920 bytes |
| 7-Zip（项目 node_modules） | `gui\node_modules\7zip-bin\win\x64\7za.exe` | 文件版本 21.07，1,231,360 bytes |

NSIS 可执行文件没有嵌入可读的文件版本字段，缓存目录名 `nsis-3.0.4.1` 是当前可用的版本证据。缓存完整性可在阶段 1 通过 Tauri bundler 的版本探测或隔离构建确认；在此之前不能把 electron-builder 缓存宣称为 Tauri 的正式工具链，也不能因缓存存在而跳过 Tauri 自身的 NSIS 资源要求。

## Rust、Tauri 与仓库锁文件

以下命令和常见位置均为只读核验结果：

| 项目 | 结果 |
|---|---|
| `cargo`、`rustc`、`rustup`、`tauri` | 均不在当前 PATH |
| `CARGO_HOME`、`RUSTUP_HOME` | 未设置 |
| `C:\Users\56440\.cargo`、`D:\Users\56440\.cargo` | 不存在 |
| `C:\Users\56440\.rustup`、`D:\Users\56440\.rustup` | 不存在 |
| 常见 Rust 安装目录 | `AppData\Local\Programs\Rust stable *`、`Program Files\Rust stable *` 均不存在 |
| 常见 Tauri 目录 | `AppData\Local\Tauri`、全局 npm `@tauri-apps`、`tauri.cmd` 均不存在 |
| Rust/Tauri 注册表键 | `HKCU/HKLM\Software\Rust`、`Tauri` 及 WOW6432Node 均不存在 |
| 仓库 Cargo 工程/锁文件 | 没有 `Cargo.toml`、`Cargo.lock`、`src-tauri` 或 `tauri.conf.json` |
| 前端锁文件 | 只有现有 `gui/package-lock.json`；其中没有 `@tauri-apps` 或 Rust 依赖 |

这表示当前不存在已经安装的 Tauri 依赖，也不存在可报告为“已生成”的 Cargo.lock。现有前端锁文件属于 Electron 页面工程，阶段 1 应在新 Tauri 工程落地后保留它，并按实际新增依赖更新，而不是把空的或推测的锁文件提交进去。

## 稳定版本候选（拟固定，不是已安装版本）

版本元数据在 2026-10-18 通过官方 Tauri 发布页、crates.io/npm 元数据和 Rust 官方 stable channel 文件核对。以下是一组已经确认存在且未 yanked 的精确固定值；它们只是规划值，当前机器没有其中任何一个，仓库也没有 Cargo.lock：

| 层 | 拟固定版本 | 来源与说明 |
|---|---:|---|
| Rust stable MSVC | `1.99.1`，目标 `x86_64-pc-windows-msvc` | Rust 官方 stable channel 文件记录 `date=2026-10-15`、`1.99.1 (58cf8f9c3 2026-10-13)`；项目可将此精确版本写入 `rust-toolchain.toml`，Tauri 2.12 的 MSRV 为 1.90 |
| Tauri Rust 核心 | `tauri = 2.12.3` | crates.io 元数据确认存在且未 yanked，`rust_version=1.90` |
| Tauri Rust CLI | `tauri-cli = 2.12.2` | crates.io 元数据确认存在且未 yanked，`rust_version=1.90`；由项目级 npm CLI 包装器调用，不另装 cargo-tauri |
| 构建辅助 | `tauri-build = 2.7.2` | crates.io 元数据确认存在且未 yanked，`rust_version=1.90` |
| JS API（按需） | `@tauri-apps/api = 2.12.3` | npm 元数据确认版本存在；现有纯 JS 页面可用 Tauri `withGlobalTauri` 官方全局 API，因此不强制新增此依赖，只有采用模块导入时才加入 |
| Node CLI 包装器 | `@tauri-apps/cli = 2.12.2` | npm 元数据确认版本存在；作为项目级 devDependency 使用，其内置 Rust CLI 二进制为 2.12.2 |
| Tauri bundler | `tauri-bundler = 2.10.2`（由 Tauri CLI 间接使用） | 官方 Tauri Ecosystem Releases，2026-10-10；应用工程无需直接依赖它 |

本方案有意固定上述已确认的精确版本，不以网页后来显示的更高版本替换它们。阶段 1 安装时仍需按同一版本集合写入清单并生成锁文件；若届时发现 yanked、平台不可用或构建约束变化，应暂停并重新评审整套版本，不能只替换单个包。

版本状态明确如下：

- 上表全部是“拟固定”，没有一个可标记为已安装。
- 当前没有 `Cargo.lock`，因此没有已解析的 Rust 依赖版本。
- `gui/package-lock.json` 是既有 Electron 前端锁文件，不包含 Tauri 包；不能当作 Tauri 锁文件。
- 本阶段没有运行 npm/cargo 恢复、安装、更新、编译或测试命令。

## 到阶段 1 的最小后续清单与阻断

进入阶段 1 前只需要处理以下工具链项：

1. 在现有 Visual Studio Installer 实例补装并确认一个 Windows SDK（建议 Windows 10 SDK 10.0.19041.0），再用 `vswhere` 确认 SDK 组件和路径；保留现有 MSVC 14.29.30133 x64/x86 与 MSBuild 16.11.6.22506。
2. 安装 Rustup 的 `stable-msvc`，将目标固定为 x64 `x86_64-pc-windows-msvc`，按上面的候选版本或安装前重新核对的官方同线版本固定 Rust。
3. 在获得依赖安装授权后，创建 `gui/src-tauri` 最小工程；项目级只加入 `@tauri-apps/cli@2.12.2`，由它调用匹配的 `tauri-cli 2.12.2`，不另装全局 `cargo-tauri`。Rust 工程加入 `tauri = 2.12.3` 与 `tauri-build = 2.7.2`；页面优先配置 `withGlobalTauri`，只有需要模块导入时才加入 `@tauri-apps/api@2.12.3`，然后生成并提交对应 `Cargo.lock` 与前端锁文件变更。
4. 用隔离输出验证 Tauri bundler 是否能使用现有 NSIS 3.0.4.1/资源 3.4.1；若不能，再单独处理 Tauri 所需工具，不修改或删除现有 electron-builder 缓存。

阶段 0 阻断：Windows SDK、Rust MSVC 工具链、Tauri 依赖和 Cargo.lock 均缺失。本工具链子项未修改产品代码或系统配置；主任务发现的数据兼容问题及并发 dirty paths 变化见 phase0.md。

## 证据来源

- Tauri Ecosystem Releases：<https://tauri.app/release/>（核心、CLI、JS API、tauri-build 和 bundler 版本）
- Tauri 2.12 发布说明：<https://v2.tauri.app/blog/tauri-2.12/>（MSRV 1.90、Windows 7 支持边界）
- Tauri Windows 前置条件：<https://v2.tauri.app/start/prerequisites/>（MSVC、Windows SDK、WebView2、MSVC Rust host triple）
- Tauri 创建项目文档：<https://tauri.app/start/create-project/>（npm CLI 与 Cargo CLI 入口）
- Rust stable channel 元数据：<https://static.rust-lang.org/dist/channel-rust-stable.toml>（`date=2026-10-15`，`1.99.1`）
- Rust Forge 当前版本：<https://forge.rust-lang.org/>（Rust 稳定版发布流程参考）
- Rust 安装文档：<https://rust-lang.org/tools/install/>（Windows rustup、`%USERPROFILE%\\.cargo\\bin`、MSVC 前置条件）
- crates.io `tauri`：<https://crates.io/crates/tauri/2.12.3>（存在、未 yanked、rust_version 1.90）
- crates.io `tauri-cli`：<https://crates.io/crates/tauri-cli/2.12.2>（存在、未 yanked、rust_version 1.90）
- crates.io `tauri-build`：<https://crates.io/crates/tauri-build/2.7.2>（存在、未 yanked、rust_version 1.90）
- npm `@tauri-apps/api`：<https://www.npmjs.com/package/@tauri-apps/api>（2.12.3 版本元数据）
- npm `@tauri-apps/cli`：<https://www.npmjs.com/package/@tauri-apps/cli>（Node CLI 包元数据）

以上网页只用于读取版本元数据，没有下载软件包；本地命令只读取文件、目录、注册表和 `vswhere` 信息。
