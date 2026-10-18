# Tauri 2 桌面宿主设计

## 已确认决定

2026-10-18，用户明确选择“改为更贴近平安志的 Tauri 2”。生产路线确定为 Tauri 2 + Rust 薄宿主 + 共享 Evergreen WebView2，保留现有 Python/FastAPI 后端。

此前 WinForms/.NET Framework 4.8、手写 WebMessage 宿主与 FastAPI /ui 同源页面方案已被本决定取代。prototype/webview2-shell 保留为历史 POC，不扩展为生产宿主。2026-10-18 用户随后授权执行阶段 0，状态已为 in_progress；本轮只读核验、记录与数据副本保护，不进入阶段 1。

后续范围更新：独立 GPT-6 Luna / max 安装会话已完成工具链补齐，原会话只读验收通过。本会话继续只检查、规划；阶段 1 现已获用户授权，由 GPT-6 Astra / medium 新会话 01a14f09-c404-7681-b02e-402844ddbfe3 实施，仅限阶段 1 与隔离验证。安装前基线保留，安装后结果见 installation-review.md。

## 已确认的数据迁移策略（2026-10-18）

用户已确认：当前 portable 业务库无损复制到旧 userData/config/ui_workbench.db 永久位置，其他两库与原始备份保留，不自动合并；首次仅主题/导航折叠恢复当前 UI 默认值，之后正常持久化。实际迁移与产品代码尚未执行。

## 阶段 0 实测补充

- 安装后已具备 Rust/Cargo 1.99.1、SDK 10.0.19041、CLI 2.12.2；独立探针锁定 tauri 2.12.3/tauri-build 2.7.2 并完成检查，原会话只读验收。正式工程未创建，见 installation-review.md。
- 现有 portable 正在运行，其 SQLite 位于 Temp 解压目录；NSIS 与开发环境另有独立数据库。三份库已分别做一致性备份，未自动合并。
- 当前临时数据库路径不作为新版本持久目标。已确认保留资源 cwd、为数据库单独提供绝对路径输入，使用当前 portable 最新一致性快照导入永久 userData/config/ui_workbench.db；源库不删、已有目标不覆盖。截图/覆盖图/窗口文件仍维持永久旧路径。
- 两个 localStorage 展示偏好已定位；用户已接受首次默认策略，不再为这两个值引入 LevelDB 导入依赖。旧 profile 保留，后续 Tauri 偏好不得在每次启动时重置。
- 隔离探针的依赖锁定与编译检查已通过；正式项目依赖/宿主、NSIS 缓存复用、portable 封装及最终包大小仍未验证。

## 架构与职责

    现有 HTML/CSS/JS（Tauri 打包；http://tauri.localhost）
        ├─ Tauri invoke / 定向事件 → Rust 宿主（窗口、托盘、受限目录操作）
        └─ HTTP + WebSocket + token → 127.0.0.1:8000 FastAPI
                                            ↑
                         Rust 启动、健康等待并管理其 Python 后端进程

| 项目 | 生产选择 | 原因与边界 |
|---|---|---|
| 宿主 | Tauri 2 / Rust / Windows x64 MSVC | 与本机平安志已观察到的宿主路线一致；只承接 Electron 桌面职责，不重写业务。 |
| 前端 | 复用 gui/index.html、renderer.js、styles.css 和现有裁剪器 | 使用 frontendDist 打包受控的静态资源；不为迁移引入新前端框架或开发服务器。 |
| 页面来源 | http://tauri.localhost，固定 useHttpsScheme=false | 使用 Tauri 本地资源协议映射；这是 WebView 内的资源来源，不是新增的本机 TCP 服务。与既有 HTTP API/WS 协议匹配。 |
| 桌面桥接 | Tauri IPC、显式应用命令权限和最小 capabilities | 复用桌面框架能力；命令实现仍负责调用方、参数和路径校验。 |
| 后端 | 既有 Python/FastAPI 受管理子进程 | 继续使用 PyInstaller onedir；Rust 管理生命周期，页面不直接启动进程。 |
| 后端资源打包 | bundle.resources 明确映射完整 backend 目录 | 包括 yys-backend.exe、_internal、模型和图片，保持目录布局；默认由 Rust 标准进程接口启动已知路径。 |
| Runtime | 共享 Evergreen WebView2 | 不带 Fixed Version Runtime；不新增 .NET Framework 运行前提。 |
| 发行 | Tauri NSIS + 单独封装的单文件 portable x64 | 裸 Tauri EXE 不包含外置 Python onedir 资源；portable 需要完整载荷和稳定数据目录。 |
| 数据 | 复用已验证的旧业务数据路径，另设 WebView2 profile 子目录 | 不把 Tauri 默认 identifier 目录自动当作旧 Electron userData，也不复制平安志的应用标识。 |

Tauri CLI、Rust core、所需 JS API 和构建工具在实施前选定兼容的稳定版本；Cargo.lock 和现有前端锁文件纳入版本控制。不照抄平安志二进制中出现的版本号，不沿用 POC 的 NuGet 构建链。

## 启动、端口与退出

1. 在创建 WebView 前处理 Runtime 可用性；NSIS 安装阶段与 portable 原生入口均需要可辨认的缺失处理，错误提示不能依赖尚不可用的 WebView。
2. Rust 从系统加密随机源生成每次启动独立的 32 字节 token。开发模式保留 YYS_PYTHON/既有 Python 路径与项目根 cwd；打包模式从受控资源目录解析 backend，并保持实测确认的 cwd。
3. 向后端传递 YYS_UI_TOKEN、YYS_USER_DATA_DIR 和 PYTHONIOENCODING=utf-8。使用明确的程序路径、参数和工作目录，不拼接 shell 命令，也不允许页面提供这些值。
4. 启动前探测 127.0.0.1:8000；端口被占用时区分受保护后端和其他占用，显示明确错误。保持固定端口，不根据平安志的一次高位端口快照改为随机端口，不杀未知进程。
5. 启动本宿主管理的后端并以当前 token 轮询 /api/scripts；最多 30 秒、间隔 500 毫秒。就绪前不显示业务主窗口；后端提前退出、鉴权错误和超时分别报告。等待过程不得阻塞桌面事件循环。
6. 后端就绪后创建受信任的 main 窗口。renderer 通过受限的 desktop_bootstrap 命令取得 API 地址、当前 token 和就绪状态，再发 HTTP/WS 请求。刷新时可重新握手；token 不放进页面 URL、localStorage 或日志。
7. 普通关闭隐藏到托盘。明确退出和启动失败时终止本宿主创建的后端，退出等待上限为 5 秒，必要时终止受管进程树。Rust Child 被丢弃不会自动保证子进程结束；Windows 使用仅包含本次后端的进程归属记录和 Job Object 退出回收，验证宿主异常结束也不遗留后端。
8. 对当前后端是否存在可用的优雅停止方式先查实再复用；不能把单纯等待当成已发送关闭请求，也不为迁移新增通用远程进程控制 API。

PyInstaller onedir 不等于一个独立 EXE。bundle.resources 必须保留相邻依赖和生产资源；仅配置 externalBin 或复制 yys-backend.exe 不能证明后端可运行。当前选择资源目录 + Rust 受控启动即可，不额外给前端安装和开放通用 shell 插件。

## 前端来源、跨源请求与 CSP

### 资源与来源

- 正式 Rust 工程计划放在 gui/src-tauri，继续使用现有 GUI 源文件。构建时只将页面、脚本、样式、图标和现有裁剪器所需文件放入 frontendDist staging；不递归嵌入 backend、node_modules 全树或 src-tauri。
- Windows 生产来源固定为 http://tauri.localhost。useHttpsScheme 不随升级切换，否则 localStorage 等数据会换来源；本方案保留 HTTP，以兼容原有 http:// 和 ws:// 本机后端。
- FastAPI 仅继续提供业务 API、图片与事件流，不新增 /ui 静态页面服务，也不安装 Tauri localhost 插件提供另一套 UI HTTP 服务。
- 开发工具产生的 dev 来源必须单独记录并明确列入开发策略；不能把开发服务器来源的通过当作生产 Tauri 来源已通过。

### HTTP 与 WebSocket

- HTTP API 地址保持 http://127.0.0.1:8000；请求继续携带 X-YYS-UI-Token。图片预览沿用已有受保护 API 和 token query，错误页或日志不得泄漏 token。
- WebSocket 保持 ws://127.0.0.1:8000/ws/events，并沿用 token query、快照和事件恢复语义；不把业务事件流重写成 Tauri IPC。
- 在 HTTP CORS 白名单中精确加入 http://tauri.localhost，验证 OPTIONS 和实际鉴权请求。既有 Electron 回退/开发所需来源按当前契约保留；不扩大为 * 或任意 localhost 端口。
- WebSocket 单独检查 Tauri Origin 和 token，明确拒绝未知来源。CLI/离线测试中没有 Origin 的调用方是否需要兼容，以现有调用契约为依据，不默认允许所有空来源。
- Tauri IPC、API token、CORS 和 WS Origin 各自负责不同边界；通过一项不能代替其余校验。

### CSP

- 显式启用 CSP，限制脚本、样式和资源来自本地受控包。连接来源仅列出 Tauri IPC 所需的 ipc: / http://ipc.localhost，以及精确的 http://127.0.0.1:8000 和 ws://127.0.0.1:8000。
- 图片来源按现有截图/图片 API、blob: 和 data: 的实际使用逐项配置，不能用 img-src * 代替梳理。
- 现有页面的早期主题内联脚本、动态样式和裁剪器是兼容检查项；优先用 Tauri nonce/hash 或最小局部改动适配，不用关闭 CSP、放开任意脚本或 unsafe-eval 处理。
- 无需求时关闭 assetProtocol 的通用本地文件读取，图片继续走已校验的 FastAPI 资源 ID 路径；不为“打开目录”授权读取整个磁盘。
- 顶层和子框架导航限制在受信任的应用资源，拒绝外部弹窗、下载和新窗口。前端不获得创建任意窗口或导航到远端后仍使用本地命令的能力。

## IPC 与权限契约

保留一个小型 desktopBridge 兼容适配层供现有 renderer 调用，内部使用 Tauri 官方 invoke 和事件 API；不直接依赖 __TAURI_INTERNALS__ 私有接口。现有纯 JS 可使用官方全局 API，权限由 Rust 命令声明与 capabilities 限制，不因此授予所有桌面操作。

### 前端到 Rust 的允许命令

| 能力 | 允许输入/输出 | 约束 |
|---|---|---|
| desktop_bootstrap | 返回当前 API 地址、token、就绪状态 | 仅可信 main 窗口；返回值不落盘、不全局广播。 |
| window_action / 窗口状态读取 | minimize、toggle-maximize、close、maximized 状态 | 枚举校验；close 保持隐藏到托盘。 |
| restore_gui_focus | 无任意窗口标识参数 | 仅恢复当前 main。 |
| open_screenshot_directory | 无路径参数 | Rust 固定解析旧 userData/screenshots，沿原行为创建并打开目录。 |
| open_image_resource_directory | 仅 resource_id | 校验已知生产资源 ID、override 规则、文件存在和最终允许根目录。 |

- 所有应用命令使用显式权限声明，并只授予 main 的本地能力配置。Tauri 默认注册到 invoke_handler 的应用命令可能对所有应用窗口开放；实施必须使用 AppManifest::commands 生成权限并配置相应 permissions/capabilities，不能只写 capabilities 文件就假定自定义命令已隔离。
- Rust 命令还须验证调用窗口 label、当前来源、字段类型和允许值；不授予 remote capability，也不以窗口标题判断身份。
- 图片路径做规范化和真实路径包含性检查，拒绝绝对路径、..、重解析点逃逸和不存在资源；参数不得变成通用“打开任意文件”接口。
- 前端不开放通用 shell、文件系统、环境读取、进程启动或结束命令。后端启动在 Rust 生命周期内部完成，不注册给页面。
- 只按实际需要开放窗口拖动和事件监听权限；不要因为示例可用就照搬 core:default 或全部插件权限。

### Rust 到页面的定向事件

- 只向 main 发送 tray-command（pause/stop）和 window-state（maximized 等必要状态）。
- 托盘显示与退出由 Rust 处理；暂停/停止通过既有 renderer/API 动作执行并沿用其错误与运行状态反馈。
- 不用事件广播 token，不把“事件已发送”认定为暂停/停止已经成功。
- 页面监听/取消监听保持原语义，刷新不累积重复监听器。HTTP/WS 的业务事件继续由现有 FastAPI 提供。

## 窗口与托盘

- 使用 Tauri 无边框且可缩放窗口，默认 900×650、最小 800×600；明确采用逻辑像素，在 100%/150% DPI 下分别验证。
- 用框架的拖动区域/窗口拖动能力替换 Electron 的 -webkit-app-region。标题按钮、输入控件等交互区域不能变成拖动命中区域；保留最大化切换、最小化、边缘缩放与窗口状态回传。
- 正常窗口边界仍保存到原有 window-state.json，移动/缩放短 debounce 写入；不以最大化边界覆盖正常尺寸。
- 恢复时检测当前显示器工作区，副屏移除后回到可见屏幕；坐标、DPI 单位和尺寸校验必须和旧数据格式转换一致。
- 托盘图标、显示菜单、双击恢复、暂停、停止、关闭隐藏和明确退出沿用现有契约；退出时移除托盘并等待后端清理。
- 不为新壳引入独立窗口状态插件或数据库，除非现有小型状态文件确实无法满足要求。

## 用户数据兼容

- 上线前分别记录旧 NSIS 和 portable 的实际 backend cwd、config/ui_workbench.db、userData、screenshots、图片覆盖和 window-state.json；这些是对比基线。
- Rust 显式把 YYS_USER_DATA_DIR 映射到旧 Electron app.getPath('userData') 的实测目录，不能把 Tauri 新默认目录当作自动兼容，也不采用平安志的 com.yys.analysis 标识。
- 保留本项目已有应用身份、安装名和快捷方式约定；Tauri identifier 与旧数据目录解析分别验证。
- 新 WebView2 profile 放在旧业务 userData 的专属 WebView2 子目录，设置固定 dataDirectory；不混用或覆盖旧 Electron profile，不使用临时目录。
- 已知 yys-gui-theme 和 yys-gui-nav-collapsed 两个展示偏好采用用户确认的首次默认策略：仅当新 Tauri 偏好尚未建立时沿用现有 UI 默认值，已有新偏好则读取保存值；旧 Electron LevelDB 不改、不清空。不得扩展为重置其他用户数据。
- SQLite schema 保持原样，物理路径按已确认策略从旧 portable 临时库迁入永久 userData/config/ui_workbench.db。迁移前重新做只读源一致性快照，不能将阶段 0 的旧快照无提示当作最新库；源已丢失时明确报告并确认恢复来源。截图、图片覆盖和配置不因卸载、解压清理或更换宿主丢失。
- 未来增加仅用于桌面发行的绝对数据库路径配置，规划名 YYS_WORKBENCH_DB_PATH；显式 db_path 参数优先、然后该配置、最后现有 cwd 回退。此新增配置只影响数据库定位，不能扩大 api_token 或 user_data_dir 参数影响范围；当前尚未实现。
- 首次导入仅在目标不存在且来源明确时执行，采用不会覆盖既有目标的发布方式；并发出现目标或来源冲突则停止导入，正常运行已有有效目标库不重新导入。安装版和开发库分别保留，不自动合并。
- portable 程序载荷与永久数据库/profile 分开，版本化载荷可放在受限 portable-runtime 子目录；清理只针对经过绝对路径包含性核验的载荷，不能递归删除 userData 根。

## NSIS、portable 与 Runtime

### NSIS

- 使用 Tauri 2 的 NSIS 发行机制，保留用户态安装、可选路径、桌面/开始菜单快捷方式、升级及卸载数据边界；审阅原 gui/installer.nsh 的必要行为。
- Runtime 安装选择 downloadBootstrapper：缺失时由安装器提供 Evergreen 在线引导；不选择 fixedRuntime、内嵌 offlineInstaller 或 skip 来绕开缺失处理。
- 应用原生入口仍处理 Runtime 缺失、版本不足和初始化失败；安装器检查不能代替每次运行时的可辨认失败路径。
- Runtime 未安装且离线时提供单独安装 Microsoft Evergreen Standalone Installer 的说明；该安装器不默认塞入本产品发行包。

### 单文件 portable

- Tauri 的 Windows 标准安装目标不是 Electron portable。保留既有单文件 portable EXE 验收，另用最小的自解压/启动封装携带 Tauri 主程序和完整 backend 载荷，优先复用 NSIS 工具链；不再捆绑 Electron。
- 解压、启动、等待和清理必须区分版本化程序载荷与永久用户数据；数据库、截图、覆盖图和 profile 绝不放在会被清理的临时目录。
- portable 不通过安装器安装自身，也不注册启动所需的应用系统配置；共享 WebView2 Runtime 仍为外部前提。缺失时由原生入口提示官方安装路径、重试或退出。
- 单个裸 Tauri EXE 不能作为有外置 Python 后端的完整便携包；不能默默降低成 ZIP 目录。若封装无法同时满足兼容与体积门槛，回到规划决定，而不是宣布已交付。

### 大小与构建边界

- 两个最终发行文件都必须 bytes < 100000000，以实际字节数独立检查。
- 原先约 73 MiB 的总体压缩比估算，以及平安志约 61.2 MB 的已安装目录都不作为新发行包实测结果。
- 发布脚本目前会删除 dist、gui/build、dist-electron；实施前采用隔离 staging/output 或可恢复备份，并约束清理目标，不覆盖其他任务的产物。
- 工具链与隔离依赖探针已由获准的安装会话完成；原会话只检查和规划，不执行正式 Cargo/MSBuild/npm 产品构建或应用烟测，不创建正式宿主。

## 主要风险与回退

| 风险 | 对策 |
|---|---|
| 新增 Rust/Tauri 构建链 | 先核实本机已有工具并固定兼容版本；保留锁文件，不为迁移引入新的前端框架。 |
| 本地来源改变 | 固定 http://tauri.localhost 和 profile，验证 CORS、WS Origin、CSP 与已知偏好迁移。 |
| 自定义 IPC 命令未纳入权限控制 | 显式 AppManifest/权限声明 + main capability + Rust 调用方/参数检查，加入非授权窗口负样本。 |
| PyInstaller onedir 资源缺失 | 打包整个 backend 目录，保留相邻依赖；以隔离后端启动验收。 |
| 后端异常遗留或 8000 冲突 | 明确进程归属、鉴权就绪、超时与 Windows 退出回收，只管理本宿主创建的进程。 |
| portable 解压导致数据丢失 | 程序载荷和永久数据分开，重复运行/升级/清理往返验证；不以裸 EXE 代替完整包。 |
| Runtime 自动更新或缺失 | Win10/11 的已安装、在线缺失、离线缺失和失败矩阵；不内嵌 Fixed Version。 |
| 包大小超限 | 分别记录 NSIS/portable 实际 bytes，超限停止发布，不能用其他应用大小背书。 |

- 切换前保留可运行的 Electron NSIS/portable、对应提交和后端版本。
- 首发期不改变业务数据库 schema、不删除旧 Electron profile 和业务数据。
- 阶段性失败保持 Electron 发布路径可用；发布后故障先退出 Tauri 和其后端，再恢复保留的 Electron 包，不同时运行两套宿主争用 8000 端口。
- 回退前对 Tauri 永久库做最新一致性快照，明确旧后端的读取路径或受控导入步骤；旧 Electron 不会自动读到新永久库，不得丢弃迁移后的新增记录。截图和覆盖图保持原目录。展示偏好无需把新 Tauri localStorage 回写旧 Electron profile，旧 profile 保留其原有值。

## 平安志本地参考与验证边界（2026-10-18）

本地只读证据支持选择 Tauri/Rust、内嵌前端和共享 WebView2；没有取得其源码，不照搬未知的游戏集成、IPC 权限或本机端口用途。

### 本地实测证据

- 应用：平安志 0.1.0-beta.28；主程序为 D:/Users/56440/AppData/Local/平安志/yys-analysis.exe，本次检查主进程 PID 为 41464。
- 主程序为原生 x64 PE，CLR 数据目录 RVA 为 0；运行模块中未发现 clr、coreclr、mscoree，主程序中未发现 System.Windows.Forms 标记。
- 主程序包含 tauri-runtime-wry、__TAURI_INTERNALS__、src-tauri 下的 Rust 源路径，以及 tauri-2.11.5 crate 编译路径。结合原生 PE 与运行态模块，可确认主宿主采用 Tauri/Rust 路线。
- 该进程启动机器级 C:/Program Files (x86)/Microsoft/EdgeWebView/Application/155.0.4283.62/msedgewebview2.exe；安装目录中未发现 Fixed Version Runtime。
- WebView2 的 --user-data-dir 指向 C:/Users/56440/AppData/Local/com.yys.analysis/EBWebView，属于独立、持久的用户目录。
- 只筛选 localStorage 文件中的来源标记，发现 http://tauri.localhost；未输出任何存储值。这证明它实际使用过该 Tauri 本地来源，但不等同于读取了当前页面的实时 URL。
- 安装目录没有独立的 HTML/JS/CSS 或 app.asar；主程序内有 221 个去重的前端资源名标记，如 index.html、assets/AppShell-w_1cztHO.css。结合 Tauri 来源，强烈支持前端资源随原生程序嵌入/打包的判断；未解包核验每个资源内容。
- 当前后代进程均为 WebView2 子进程；未发现该主进程启动的独立 Python 后端。进程当前监听 127.0.0.1:56442；未请求该端口、未确认其用途，不能认定它是前端 HTTP 服务，也不能仅凭端口号断言动态分配策略。
- 主程序为 56,272,384 bytes；安装目录共 9 个文件、合计 61,202,769 bytes，含辅助工具与资源。这是已安装目录大小，不是原始安装包大小，也不代表本项目加上 Python 后端后的包大小。

### 与本方案的关系

| 项目 | 平安志证据 | 本方案选择 |
|---|---|---|
| 宿主 | Tauri 2 / Rust / Wry 编译标记 | 同路线，版本自行固定。 |
| 页面 | http://tauri.localhost 存储来源及内嵌资源标记 | 同来源模式，通过 frontendDist 打包现有 GUI。 |
| Runtime/profile | 共享机器级 WebView2，独立 EBWebView | 共享 Runtime，独立 profile，业务目录保留本项目旧路径。 |
| 后端 | 未观察到 Python 子进程；监听端口用途未知 | 因现有业务保留 Python/FastAPI，Rust 管理子进程。 |
| 桥接与安装 | 具体 capabilities、CSP、Runtime 缺失流程及 portable 未核实 | 根据本项目白名单、安全与发行契约设计并单独验收。 |

## 技术依据

- [Tauri Process Model](https://v2.tauri.app/concept/process-model/)
- [Tauri Configuration（frontendDist、useHttpsScheme、CSP）](https://v2.tauri.app/reference/config/)
- [Tauri Capabilities（含应用自定义命令默认权限说明）](https://v2.tauri.app/security/capabilities/)
- [Tauri CSP](https://v2.tauri.app/security/csp/)
- [Tauri Embedding Additional Files](https://v2.tauri.app/develop/resources/)
- [Tauri Embedding External Binaries](https://v2.tauri.app/develop/sidecar/)
- [Tauri Windows Installer](https://v2.tauri.app/distribute/windows-installer/)
- [Microsoft WebView2 Distribution](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution)
- [Microsoft Evergreen vs. Fixed Version](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/evergreen-vs-fixed-version)
