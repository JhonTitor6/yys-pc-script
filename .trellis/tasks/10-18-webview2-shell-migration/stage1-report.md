# 阶段1实施报告

日期：2026-10-18（Asia/Shanghai）。对应任务：`webview2-shell-migration`。

## 结论与边界

阶段1九项实现已完成，正式工程检查、单元测试、既有 GUI 回归及隔离 WebView2 烟测通过。未实施阶段2–4，不表示完整工作台迁移或发行验收通过。

本会话依据本轮委派和用户“继续”的阶段1授权执行；任务文档中较早的“只授权阶段0”记录未擅自改写。未修改任务元数据、PRD、设计、总实施清单或父会话验收记录。未提交、推送、归档。

开始和结束 HEAD 均为 `d11c01f9730c4fa376da7dfaa1988e2a08f43986`，分支 `master`。开始工作区只有 `.trellis/tasks/10-18-webview2-shell-migration/` 未跟踪。其他会话文件未回滚。

## 九项交付对应

| 实施清单 | 本阶段结果 |
|---|---|
| 正式 Tauri 2/Rust 工程 | 新增 `gui/src-tauri`，Windows x64 MSVC；历史 WinForms POC 保留。 |
| 精确版本与真实锁文件 | `rust-toolchain.toml` 固定 1.99.1；Cargo 固定 tauri 2.12.3、tauri-build 2.7.2；正式 Cargo.lock 从 crates.io 解析生成，未复制探针锁文件。gui 清单/锁文件加入 CLI 2.12.2。 |
| 受控 frontendDist | `scripts/stage-tauri.cjs` 仅复制 HTML、renderer、styles、bridge、icon、cropper.min.js 六个文件；不复制 backend 或整个 node_modules。拒绝 staging 额外文件和链接。另生成 Rust 内嵌的生产图片 ID 清单，未把图片资源树放进页面包。 |
| 固定本地来源 | Rust `use_https_scheme(false)`；真实 WebView2 检查为 `http://tauri.localhost`；没有新增 UI HTTP 服务或 FastAPI 路由。 |
| 薄 desktopBridge | 使用官方 `window.__TAURI__.core.invoke` / `event.listen`，无私有接口；保留旧方法和同步返回清理函数的契约，处理异步订阅尚未完成便清理的竞态。已有 Electron preload 存在时不覆盖。 |
| 窗口、托盘、状态 | 无边框、原生缩放、900×650 默认、800×600 最小；标题拖动/双击最大化、最小化、焦点恢复、关闭隐藏、托盘显示/双击恢复、暂停/停止定向事件、明确退出。兼容旧四字段 window-state.json；按目标显示器 DPI 转物理坐标，裁入可见工作区，正常窗口边界持久化。 |
| 有限命令与授权 | `AppManifest::commands` 声明六个命令并生成显式权限；main capability 仅授予六个应用命令及 event listen/unlisten。Rust 校验 main label、当前页面 URL、枚举动作、生产资源 ID 与真实路径包含性。 |
| 定向事件与最小权限 | window-state / tray-command 仅发送至 main WebviewWindow，不广播 token；页面没有 shell/fs/进程启动权限。顶层导航只接受受控首页，拒绝新窗口、下载；CSP 限制本地资源、IPC 和精确后端来源。 |
| 最小有效检查 | Rust 三项契约测试、JS 桥接检查、真实 WebView2 负样本和窗口检查已运行。覆盖非授权窗口、错误来源、未知命令、错误参数、目录穿越/兄弟前缀/符号链接逃逸、重复监听清理。 |

## 本阶段后端行为

- 普通构建不启动 Python，也不探测、请求或接管 8000。bootstrap 返回 `ready=false` 和明确未接入原因，renderer 在握手就绪前拒绝所有业务 fetch；暂停/停止托盘项禁用。
- 生产 API 地址仍是 `http://127.0.0.1:8000`。renderer 的 API/token 初始化适配已就位，HTTP token 和 WS URL 语义保持；实际 Python 生命周期与 CORS/WS Origin 改造仍属阶段2。
- 隔离模式只存在于显式 Cargo `smoke-test` feature，读取本仓库忽略的 build 子目录中的测试配置，拒绝 8000 和非 loopback 地址；普通构建没有测试端口替换或脚本注入入口。
- 烟测 Python 服务只提供空业务数据和假的 WS 握手，不导入 ui_backend 或游戏业务，不执行脚本。测试器检查二进制的 smoke-only 标记后才运行，避免误启动普通构建写入旧用户目录。
- 烟测中资源目录“打开”执行路径验证并返回结果，不启动资源管理器；真实 Explorer 行为尚未实机验证。生产实现使用 Windows 系统目录下的 explorer.exe，参数为规范化后的受限目录/文件。

## 依赖与资源

- Rust/Cargo：1.99.1；目标 `x86_64-pc-windows-msvc`。
- tauri：2.12.3；tauri-build：2.7.2；本地 `gui/node_modules/.bin/tauri.cmd --version`：2.12.2。
- 复用官方全局 JS API，无新增前端框架或 JS API 包。Electron 与原发行依赖保留。
- `dunce 1.0.5` 已是 Tauri 依赖，本工程显式复用其 Windows canonicalize，以消除交给资源管理器的扩展路径前缀，同时保留真实路径包含性检查。
- 补装同一 1.99.1 工具链的 rustfmt；未改系统 PATH、MSVC 或 SDK。
- `npm install --prefix gui --package-lock-only --ignore-scripts --registry https://registry.npmjs.org/` 更新锁文件；随后 `npm install --prefix gui --ignore-scripts --registry https://registry.npmjs.org/ --no-audit --no-fund` 恢复本地 CLI（新增两个包）。未执行 Electron 安装脚本或 audit fix。
- npm 的锁文件安装输出报告 25 项漏洞（4 moderate、20 high、1 critical）；本轮未做漏洞归因/依赖升级，不将其计为已解决。
- staging 生成 178 个生产图片 ID。通过只抽取 `win_util/image.py` 的既有常量和 `production_image_ids` 函数进行离线比对，列表完全一致，无需导入游戏模块。

## 实际验证命令和结果

以下从仓库根执行；当前会话 Rust 路径未刷新，所以使用绝对路径。编译缓存/产物均在忽略目录。

```powershell
& C:/Users/56440/.cargo/bin/cargo.exe +1.99.1 generate-lockfile --manifest-path gui/src-tauri/Cargo.toml
& C:/Users/56440/.cargo/bin/cargo.exe +1.99.1 check --manifest-path gui/src-tauri/Cargo.toml --locked --target x86_64-pc-windows-msvc --target-dir build/tauri-target
& C:/Users/56440/.cargo/bin/cargo.exe +1.99.1 test --manifest-path gui/src-tauri/Cargo.toml --locked --target x86_64-pc-windows-msvc --target-dir build/tauri-target
& C:/Users/56440/.cargo/bin/cargo.exe +1.99.1 fmt --manifest-path gui/src-tauri/Cargo.toml -- --check
node tests/gui/test_desktop_bridge.js
node tests/gui/test_renderer_config.js
node tests/gui/test_backend_detection.js
node --check gui/renderer.js
& D:/ProgramData/anaconda3/envs/win_macro/python.exe -m ruff check tests/gui/run_tauri_smoke.py
git diff --check
```

最终结果均通过。Rust 三项测试包括真实目录、符号链接逃逸及旧窗口状态离屏恢复。JS 测试验证未就绪时零 fetch、重复清理、挂载/卸载、原 Electron 桥接保留、拖动动作映射和权限白名单。现有两组 GUI 测试未更改且通过。

烟测编译/运行：

```powershell
& C:/Users/56440/.cargo/bin/cargo.exe +1.99.1 build --manifest-path gui/src-tauri/Cargo.toml --locked --features smoke-test --target x86_64-pc-windows-msvc --target-dir build/tauri-target
Copy-Item -LiteralPath build/tauri-target/x86_64-pc-windows-msvc/debug/yys-desktop.exe -Destination build/tauri-target/yys-desktop-smoke.exe
$env:PYTHONIOENCODING = 'utf-8'
& D:/ProgramData/anaconda3/envs/win_macro/python.exe tests/gui/run_tauri_smoke.py build/tauri-target/yys-desktop-smoke.exe
# 离屏旧窗口文件场景
& D:/ProgramData/anaconda3/envs/win_macro/python.exe tests/gui/run_tauri_smoke.py build/tauri-target/yys-desktop-smoke.exe --restore
```

实际成功证据：

| 场景 | 证据目录（仓库根相对路径） | 测试端口 |
|---|---|---|
| 最终默认启动 | `build/tauri-stage1-smoke/20261018-211209-605440` | 52145 |
| 离屏旧状态恢复，含原生最小尺寸与边缘检查 | `build/tauri-stage1-smoke/20261018-211047-602598` | 51870 |
| 阴影修复后的恢复检查 | `build/tauri-stage1-smoke/20261018-210852-721736` | 63230 |

每个目录保留 report.json、other.json、native.json、requests.json、host.log、独立 WebView2 profile、截图/图片测试目录和窗口状态；测试 token 配置在结束时删除。上述所有端口均来自本次假后端的独立 bind(0)，不成为生产回退策略。

最终默认/恢复烟测均验证：生产来源、裁剪器加载、bootstrap、假后端初始化和 WS token/Origin、未知命令/非法参数/shell 调用拒绝、非授权窗口拒绝、正负图片 ID、截图库目录、最大化/还原、监听清理、最小化/焦点恢复、关闭隐藏后的恢复、暂停/停止定向事件及 URL 无 token。原生查询为 900×650、最小 800×600、无边框、可缩放、左边缘命中 HTLEFT、位于可见屏幕内。

最后另执行不带 smoke feature 的 `cargo build ... --locked`，成功生成普通宿主，但未运行它。普通宿主 12,735,488 bytes，保存的烟测宿主 12,780,544 bytes。这些是 debug 裸宿主，不是 NSIS/portable 发行产物，不能用于最终 100 MB 包门槛验收。

## 验证中发现和修正

1. 当前 Tao 0.37.1 对无边框且保留原生阴影的 `set_inner_size` 加入隐藏非客户区补偿；旧状态恢复实测把 650 高变为 680。新宿主关闭原生阴影，保留无边框与原生边缘缩放；恢复场景及原生 HTLEFT 检查通过。没有用硬编码减 30 像素修补。
2. 首次测试固定等待 500ms 过短，改为有界等待页面初始化。另有一次 10 秒等待未完成；该次请求只到 workflows，未捕获产品异常，不能断言其确切根因。后续增加初始化消息采集并连续完成恢复/默认场景，成功记录如上；失败记录保留，后续若复现应继续查浏览器/测试服务时序。
3. 烟测 CSP 使用精确独立端口替换生产固定端口，未关闭 CSP或放宽为任意本地端口；当前版本的 Csp 为显式 Policy 枚举，编译时已按精确版本 API 修正。

## 修改文件范围

- 新增 `gui/src-tauri/{Cargo.toml,Cargo.lock,rust-toolchain.toml,build.rs,tauri.conf.json,.gitignore}`、`capabilities/main.json`、`src/{main,policy,window_state,smoke}.rs`。
- 新增 `gui/desktop-bridge.js`、`scripts/stage-tauri.cjs`。
- 局部修改 `gui/index.html`、`gui/renderer.js`、`gui/package.json`、`gui/package-lock.json`；Electron 打包清单包含新 bridge 文件，旧入口不变。
- 新增 `tests/gui/test_desktop_bridge.js`、`tests/gui/tauri-smoke.js`、`tests/gui/run_tauri_smoke.py`。
- 任务目录仅新增本报告。无 ui_backend、游戏业务、WinForms POC、旧 Electron main/preload、发行脚本或用户数据变更。

## 尚未验证或后续依赖

- 未请求/抢占/停止旧 portable 的 8000 端口，未运行真实 Python 后端或游戏；未读取/迁移/清理旧数据库、profile、截图或图片覆盖；阶段0备份未触碰。
- 实机仅本机 Win11 22631、已安装 Evergreen Runtime；Win10、真实多屏拔插/不同 DPI 往返、人工鼠标拖动、系统托盘菜单实际点击、Explorer 文件选中、Runtime 缺失/安装流程未验证。已有离屏恢复、目标 DPI 换算单元逻辑和原生尺寸/边缘查询不能替代完整实机矩阵。
- 托盘暂停/停止在烟测中验证了定向事件；假后端没有当前运行，不验证真实业务暂停/停止结果。后端接入后仍须验证这两条业务调用链。
- 阶段2需实现真实后端受控启动与鉴权就绪、精确 CORS/WS Origin、真实图片/裁剪流程；阶段3需完成迁移、数据往返、后端归属及退出回收；阶段4–5需完成发行包和跨系统验收。
- 本阶段正常未就绪行为有静态/JS检查，普通构建只编译未运行，以免触碰旧 userData；所有宿主运行均为隔离 smoke feature。
- 未构建正式 NSIS/portable，未清理 Electron 依赖，未进行包大小或发行完整性声明。

下一步由父会话检查本报告和 diff，决定是否验收阶段1并安排阶段2；本会话不自动推进任务状态。
