# Tauri 2 桌面壳实施计划

> 阶段 0 已通过；用户于 2026-10-18 将阶段 1 分发到 01a14f09-c404-7681-b02e-402844ddbfe3（GPT-6 Astra / medium）。实施会话可完成阶段 1 产品代码及必要编译测试、隔离宿主烟测；原会话只检查规划，阶段 2–5 不自动开始。

安装检查结果：独立 GPT-6 Luna / max 会话已完成补装和隔离探针，原会话已只读验收。工具链门槛通过；数据库与首次展示偏好策略现已由用户确认，阶段 0 通过。本会话只检查、规划，不开展产品代码开发。详情见 installation-review.md。

## 阶段 0：实施前基线

结果与原始路径见 [phase0.md](./phase0.md)，工具/版本证据见 [phase0-toolchain.md](./phase0-toolchain.md)。

- [x] 记录当前分支、HEAD 与 dirty paths；非本任务的新 OCR/测试修改已单独识别，未触碰。
- [x] 工具链已补齐并验收：Rust/Cargo 1.99.1、SDK 10.0.19041、CLI 2.12.2，保留原 MSVC/Node；NSIS 缓存实际复用在打包阶段验证。
- [x] 固定版本已准备并通过隔离探针：Rust 1.99.1、tauri 2.12.3、tauri-build 2.7.2、CLI 2.12.2；探针 Cargo.lock 不代替尚未创建的正式工程锁文件。
- [x] 记录 Win10 22H2 / Win11 支持基线和本机 Win11 22631、共享 Runtime 155.0.4283.62；未执行 Runtime 初始化。
- [x] 分别核实 NSIS/portable/开发数据库及永久 userData，读取真实 app.asar 证据，为三份库完成只读源一致性快照；快照 quick_check 均为 ok。
- [x] 用户确认首次仅主题/导航折叠恢复既有 UI 默认值，旧 profile 保留、后续新偏好正常持久化；无需为这两个值引入 LevelDB 迁移依赖。
- [x] 确认 portable 程序载荷与永久数据分开；当前 portable 库通过最新一致性快照复制到旧 userData/config/ui_workbench.db，其他两库保留不合并，目标不覆盖。实际迁移、封装和清理验证属于后续阶段，尚未执行。

阶段 0 门槛通过：工具链已验收、迁移策略已确认。当前本会话只检查规划，不自动开始阶段 1，不执行实际数据迁移。

## 阶段 1：Tauri 生产宿主和静态页面

执行者：新会话 01a14f09-c404-7681-b02e-402844ddbfe3。本阶段使用隔离假后端与独立测试 profile；不改真实 Python 后端、不访问现有 8000 端口、不迁移用户数据。具体完成情况由 stage1-report.md 提供证据后再更新勾选，分发不等于完成。

- [ ] 在 gui/src-tauri 建立最小 Tauri 2/Rust Windows x64 工程；历史 WinForms POC 保留，不再作为生产入口。
- [ ] 在获准恢复依赖后按阶段 0 精确版本生成 Cargo.lock/更新前端锁文件；不能提交虚构的锁文件。
- [ ] 将既有 HTML/CSS/JS、图标和裁剪器依赖放入受控 frontendDist staging；不嵌入整个 node_modules 或 backend。
- [ ] 使用 http://tauri.localhost，固定 useHttpsScheme=false；不增加 FastAPI /ui 或另一套 UI HTTP 服务。
- [ ] 用薄 desktopBridge 适配 Tauri 官方 invoke/事件 API，保留现有 renderer 调用语义，不依赖私有 __TAURI_INTERNALS__。
- [ ] 实现窗口和托盘契约、窗口状态文件兼容、DPI/多屏恢复；优先使用 Tauri 的原生能力。
- [ ] 为 desktop_bootstrap、窗口、焦点、截图目录和资源目录等有限命令声明权限；使用 AppManifest::commands 和 main capabilities，Rust 同时验证调用方和参数。
- [ ] 事件仅定向到 main，不广播 token；不给页面通用 shell、文件系统或后端启动权限。
- [ ] 为 IPC 白名单、非授权窗口、路径包含性和重复监听留下最小有效检查。

实施阶段验证：Cargo 静态检查和必要单元测试；宿主最小烟测只连接隔离/假的后端，不触发游戏业务。

## 阶段 2：Python 后端与跨源初始化

- [ ] 通过 bundle.resources 明确映射完整 PyInstaller onedir 后端目录；验证 _internal、模型和图片资源的相对布局。
- [ ] Rust 使用固定受控路径和参数启动后端，继续注入 YYS_UI_TOKEN、YYS_USER_DATA_DIR、PYTHONIOENCODING；开发/打包 cwd 与旧版本比对。
- [ ] 保留 127.0.0.1:8000 启动前探测、鉴权 /api/scripts 健康等待、30 秒期限和提前退出错误。
- [ ] 后端就绪再显示业务主窗口；renderer 先 invoke desktop_bootstrap，得到 API 地址/token 后才发 HTTP/WS 请求，刷新可重新握手。
- [ ] 保留 HTTP 请求头 token、图片 API token query、ws:// 事件快照和恢复协议，不将业务 API 重写为 Tauri commands。
- [ ] HTTP CORS 精确加入生产 Tauri 来源；开发/回退来源依已有契约分别处理。WebSocket 校验 Origin 和 token。
- [ ] 显式 CSP 仅允许必要的 Tauri IPC、HTTP API、WS 和图片来源；验证早期主题脚本、动态样式、blob/data 图片和裁剪器，不能通过禁用 CSP 解决。
- [ ] 禁止外部导航、新窗口和下载；验证错误来源、错误 token、未知命令和越权资源 ID 被拒绝。

实施阶段验证：相关 FastAPI API/WS/CORS 用例、Rust IPC 负样本及生产来源下的图片/裁剪器检查；开发页面通过不能替代生产来源验证。

## 阶段 3：数据、进程和退出

- [ ] SQLite schema 保持，当前 portable 库重新一致性快照后无损导入永久 userData/config/ui_workbench.db；源与另两库保留不合并。目标存在不覆盖，源失效不静默使用旧快照或空库。
- [ ] 绝对数据库路径配置只影响数据库定位，显式 db_path 优先、无配置仍按原 cwd 回退；api_token/user_data_dir 行为保持。
- [ ] 配置、截图、图片覆盖和 window-state.json 的永久路径保持；回退前保留最新 Tauri 数据库快照并明确旧版读取办法。
- [ ] 将旧 Electron userData 与新 Tauri identifier/profile 分开处理；固定新的 WebView2 dataDirectory，不覆盖旧 profile。
- [ ] 按已确认策略只在首次初始化主题/折叠默认值，随后复用新偏好，保留旧 profile；对数据副本验证持久化、重启和回退可读性。
- [ ] 验证端口占用、后端鉴权错误、超时、提前退出、renderer 初始化失败；只管理本宿主实际创建的进程。
- [ ] 实现正常退出、启动失败和异常宿主退出的进程回收，必要时使用 Windows Job Object；退出等待最多 5 秒。
- [ ] 验证关闭隐藏仍保留后端，托盘暂停/停止走既有动作，明确退出后才终止后端；不能仅凭 Rust Child drop 宣称清理成功。

实施阶段验证：进程生命周期与数据副本升级/回退往返；只运行隔离后端和离线契约检查，不自动执行游戏。

## 阶段 4：NSIS 与单文件 portable

- [ ] 用 Tauri NSIS 替换 Electron 构建，保留现有安装目录、用户态安装、可选路径、快捷方式及 gui/installer.nsh 中必要的数据保护行为。
- [ ] 设置 downloadBootstrapper 处理缺失 Evergreen；不携带 Fixed Version、不嵌入完整离线 Runtime 安装器、不用 skip 掩盖缺失。
- [ ] 提供运行时缺失/初始化失败的原生提示、官方安装入口、重试和退出；portable 路径不能依赖 NSIS 安装过程。
- [ ] 另行封装 portable.exe：优先复用 NSIS 工具，将 Tauri EXE 与完整后端解出后启动并等待退出，保持单文件交付。
- [ ] 解压目录的版本更新和清理不触碰永久数据库、截图、覆盖图、窗口文件与 WebView2 profile；普通用户、含空格路径和任意启动目录均可运行。
- [ ] 更新 scripts/build_release.ps1 等发布入口，保留 -Target all/nsis/portable 接口；先隔离 staging/output 或备份旧产物，再允许构建清理。
- [ ] 在两类包均通过前保留可回退的 Electron 构建资料；最终移除不再需要的 Electron 发布依赖，保留裁剪器等仍使用的前端依赖。

实施阶段验证：必须检查最终发行文件清单和有效启动。裸 EXE 成功不等于 portable 已交付；任一完整包达不到 bytes < 100000000 就停止发布。

## 阶段 5：验收矩阵与发布门槛

- [ ] Windows 10 x64 22H2 与 Windows 11 x64：NSIS/portable × Runtime 已安装、缺失可联网、缺失离线、安装取消/失败；记录完整版本。
- [ ] NSIS 首次安装、从 Electron 升级、路径变更和卸载数据保留。
- [ ] portable 多启动目录、普通权限、重复启动、重复解压、升级与退出清理；数据库/profile 不落入临时清理范围。
- [ ] 生产 http://tauri.localhost 来源、精确 CORS、WS token/Origin、CSP、截图和图片替换/恢复/裁剪。
- [ ] 非授权窗口、缺失能力、伪造 IPC、外部导航、畸形参数、路径穿越和不存在资源。
- [ ] 窗口 900×650 默认、800×600 最小、拖动/缩放、最大化恢复、DPI、多屏拔除、托盘显示/暂停/停止/退出。
- [ ] 旧 SQLite、截图、图片覆盖、窗口文件和两个偏好迁移；Electron 回退读取同一业务数据。
- [ ] 保留 PRD AC1–AC28 的逐项结果，未做的 Windows 实机或包验证标注未做。
- [ ] 两个最终 EXE 分别读取实际字节数，均严格小于 100,000,000 bytes；不引用平安志安装目录或旧估算作为验收。

当前父进程 PATH 尚未刷新；后续可重开终端，或使用 C:/Users/56440/.cargo/bin/cargo.exe 与 build/tauri-tools 下 CLI 的绝对路径。不要因此误判工具未安装。

以下命令仅供未来实施阶段，在对应文件和依赖已准备且获准构建后使用：

    cargo check --manifest-path gui/src-tauri/Cargo.toml --locked
    cargo test --manifest-path gui/src-tauri/Cargo.toml --locked
    python -m pytest tests/ui_backend/test_app_api.py tests/ui_backend/test_screenshot_api.py -q

测试需按实际修改范围补充 IPC、WS、存储和进程契约，避免仅重复待实现代码的字面逻辑。发布构建使用改造后的既有入口与明确的打包 Python 环境，不在无环境变量时自动覆盖日常开发依赖。

## 预计涉及范围与回滚点

- 新宿主：gui/src-tauri 的 Rust、Cargo/锁文件、Tauri 配置、permissions/capabilities。
- 前端接入：gui/index.html、renderer.js、styles.css 及一个小型桥接适配；只改宿主交互与初始化。
- 后端：ui_backend/app.py 的 CORS/WS Origin 等必要边界；存储、业务运行和调度契约不重构。
- 发行：gui/package.json/锁文件、gui/installer.nsh、scripts/build_release.ps1、scripts/sync-backend.js、build_backend.spec 中经查明确有必要的部分；只修改实际需要的文件。
- 阶段 1–3 不通过，保留 Electron 发布路径并回到设计或实现修正。
- 阶段 4–5 包大小、便携封装、数据或安全断言失败，停止分发 Tauri 产物，不能降低成其他发行形态宣布完成。
- 首发问题先退出 Tauri 及其后端，再恢复已保留的 Electron NSIS/portable；不删 SQLite、截图或图片覆盖。
- 提交按功能边界拆分且只包含本任务文件；提交、推送和任务归档仍需相应明确授权。
