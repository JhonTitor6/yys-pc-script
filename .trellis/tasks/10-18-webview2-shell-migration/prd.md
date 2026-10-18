# 使用 Tauri 2 与 Evergreen WebView2 替换 Electron 桌面壳

## 目标

用轻量的 Windows 原生宿主替换 Electron，同时保留现有工作台页面、FastAPI 后端和用户可见行为。共享 Evergreen WebView2 Runtime 是运行前提；宿主缺少 Runtime 时应给出明确安装路径。安装包不得携带 Fixed Version Runtime。

阶段 0 已通过。用户现授权 GPT-6 Astra / medium 新会话实施阶段 1，包含本阶段代码、必要依赖恢复、编译测试与隔离假后端宿主烟测；本会话继续只检查规划。阶段 2 真实后端接入、实际数据迁移、发行包构建与游戏操作不自动包含。

## 规划审阅记录

- 2026-10-18：用户要求“继续，分发阶段一，使用gpt6 astra 中”；阶段 1 已分发至 01a14f09-c404-7681-b02e-402844ddbfe3（GPT-6 Astra / medium），结果记录 stage1-report.md。本会话只检查规划；不自动实施后续阶段。

- 2026-10-18：用户回复“是”，确认当前 portable 业务库迁入永久 userData/config/ui_workbench.db，其他两库保留且不合并；首次 Tauri 启动仅主题和导航折叠恢复默认。阶段 0 的剩余策略门槛通过；本会话仍只检查规划，不执行迁移或开发代码。

- 2026-10-18：安装会话完成回报；原会话直接复核版本、SDK、探针锁文件/工件与数据库备份哈希，工具链门槛通过；该轮尚待决的数据库与偏好策略已在随后用户确认中解决，正式代码开发仍不在本会话范围。

- 2026-10-18：用户允许补齐安装，并要求由新会话 GPT-6 Luna / max 执行；安装完成通知本会话检查、规划。本会话不进行产品代码开发。安装会话 01a14ee9-f61e-7d82-bc25-b5f819aa2bf3，结果写入 install-report.md。

- 2026-10-18：用户回复“同意”，按通过当前规划与 Windows 10 22H2 最低测试基线记录。
- 2026-10-18：用户明确选择“改为更贴近平安志的 Tauri 2”；生产宿主确定为 Tauri 2 + Rust，保留 Python/FastAPI 后端，替代此前的 WinForms/.NET Framework 生产建议。
- 原规划阶段仅允许任务文档；2026-10-18 用户进一步明确要求“进行阶段0”，任务按流程进入 in_progress，授权限于阶段 0，不自动扩展到阶段 1。
- 阶段 0 证据与尚未通过的门槛见 phase0.md，工具链明细见 phase0-toolchain.md。

## 范围

- 采用 Tauri 2 + Rust 薄宿主和共享 Evergreen WebView2；现有 HTML/CSS/JS 作为 Tauri 本地资源打包，Python/FastAPI 作为宿主管理的子进程保留。
- 替换 Electron 的进程启动、窗口、托盘、前端到宿主通信和打包职责。
- 继续使用现有 gui 页面和 FastAPI 业务后端，只修改实现宿主迁移必需的页面来源、CORS、静态资源打包和桥接代码。
- 保持现有 NSIS 安装包和单文件 portable x64 EXE 两种发行形态；portable 必须封装完整后端资源，不能用裸 Tauri EXE 或 ZIP 目录替代。
- 验证 SQLite 数据库、截图、图片覆盖、窗口状态和本地偏好设置的兼容性。
- 保留可执行的 Electron 回退方案。

## 不在范围内

- 重写业务 API、运行管理、调度、游戏自动化流程或前端布局。
- 引入 Fixed Version WebView2 Runtime。
- 本会话不开发产品代码；阶段 1 实施会话只进行该阶段必要编译测试及隔离假后端烟测，不操作真实工作台/游戏、不迁移用户数据、不打包正式发行物。
- 更改数据库 schema、自动合并不同来源的业务库或清理用户数据；已确认的单库无损复制到永久目录属于未来实施范围，本回合不执行。

## 约束与现状

- 现有生产宿主位于 gui/main.js 和 gui/preload.js，页面位于 gui/index.html、gui/renderer.js、gui/styles.css。
- 宿主目前在本机 127.0.0.1:8000 启动 FastAPI，生成每次启动唯一的 UI token，并等待带 token 的真实接口就绪后才显示页面。
- 开发模式以项目根目录为后端 cwd；打包模式以 yys-backend.exe 所在目录为 cwd。后端依赖相对路径 config 和 yys/logs。
- YYS_USER_DATA_DIR 指向 Electron 的 userData 目录，截图和用户图片覆盖保存在该目录下。SQLite 数据库由后端按 cwd 下的 config/ui_workbench.db 定位。
- renderer 使用 HTTP 请求头 X-YYS-UI-Token，并通过 ws://127.0.0.1:8000/ws/events?token=... 建立事件流。
- 当前本地页面经 file:// 加载；FastAPI CORS 白名单含 null、file:// 和本机来源。renderer 的 localStorage 目前保存主题和导航栏折叠偏好。
- 现有桌面行为包括无边框窗口、900×650 默认尺寸、800×600 最小尺寸、窗口位置/大小恢复、关闭时隐藏到托盘、托盘显示/暂停/停止/退出，以及打开截图和图片覆盖文件夹。
- 当前发布输出为 NSIS 与 portable x64。已有整体压缩比约 73 MiB 的估算不是 WebView2 最终集成包的实测值。
- prototype/webview2-shell 是独立 WinForms POC；目标 .NET Framework 4.7.1、WebView2 SDK 1.0.4191.47，已完成编译和 ready→ping→pong 烟测；它没有接入工作台和后端。

## 需求

- R1：生产宿主确定为 Tauri 2 + Rust，Windows x64 使用共享 Evergreen WebView2；不增加 .NET Framework 生产运行前提，现有 WinForms POC 仅保留为历史验证。
- R2：保持后端单实例启动、8000 端口冲突检测、鉴权健康等待、启动超时和失败提示；不终止未知占用端口的进程。
- R3：保持后端可执行文件解析、开发/打包 cwd、YYS_UI_TOKEN、YYS_USER_DATA_DIR 和 UTF-8 环境；退出时有界清理后端，不遗留宿主启动的进程。
- R4：宿主能力只开放有限白名单：启动信息读取、窗口操作、托盘显示/暂停/停止/退出，以及打开截图目录和指定图片资源目录；启动信息只向可信主窗口交付当前 API 地址和 token。
- R5：以 Tauri IPC、显式命令权限和 capabilities 约束可信主窗口；校验调用窗口、页面来源和参数。图片目录参数只能是已知资源 ID，解析后的路径必须位于允许根目录内。
- R6：Windows 生产页面固定使用 Tauri 本地来源 http://tauri.localhost；继续使用现有本机 HTTP API 和 ws:// 事件流，通过精确 CORS、WebSocket Origin、token 和 CSP 处理跨源。来源协议不能随版本随意切换而丢失 localStorage。
- R7：当前 portable 业务库通过一致性快照无损复制到旧 userData/config/ui_workbench.db 永久位置；其他两库保留不合并，原库不删、已有目标不覆盖。截图、图片覆盖和窗口状态路径保持；首次仅主题/导航折叠使用既有默认值，后续正常持久化。
- R8：检测 Evergreen Runtime；Runtime 缺失时提示安装并允许重试。NSIS、portable 和离线说明均不得依赖包内 Fixed Version Runtime。
- R9：NSIS 与 portable x64 在 Windows 10 和 Windows 11 上验证；Runtime 已安装、缺失且可联网、缺失且离线三种状态均有可预测结果。
- R10：按字节检查最终 NSIS 与 portable 安装产物，每个发行文件必须严格小于 100,000,000 bytes。
- R11：规划分阶段交付、主要风险和 Electron 回退办法；规划与实施保持两个独立审核阶段。
- R12：保留 PyInstaller onedir 后端的完整目录、依赖和图片资源；Tauri 不重写业务 API，也不把后端直接暴露为前端可任意启动的进程。固定 Rust/Tauri 构建依赖并保留锁文件。

## 原有行为必须保持的原子验收断言

- AC1：宿主启动时只启动一个后端；只有后端鉴权健康检查成功后才显示工作台页面。
- AC2：8000 端口被其他进程占用时显示可辨认的错误，不接管或终止该进程；已存在后端也不能被误认作本宿主启动的后端。
- AC3：开发和打包模式均使用正确的后端可执行文件、cwd、YYS_UI_TOKEN、YYS_USER_DATA_DIR 与 PYTHONIOENCODING。
- AC4：健康等待超时或后端提前退出时，不显示假正常页面，并能退出或重试。
- AC5：所有现有 HTTP API 继续发送 X-YYS-UI-Token；WebSocket 事件流继续通过当前路径和 token 建立并能恢复页面状态。
- AC6：工作台现有脚本、运行记录、配置、工作流、截图和图像资源页面不改变其后端调用结果或业务语义。
- AC7：首次 Tauri 启动允许主题和导航折叠恢复当前 UI 的默认值；已在 Tauri 保存后再次启动应恢复保存值，不得每次重置，也不得清空旧 Electron profile、数据库或截图。
- AC8：截图库仍读写原有 userData/screenshots；打开截图目录时目录存在且被系统文件管理器打开。
- AC9：图片替换、恢复和预览继续使用原有用户覆盖目录；打开目录只能定位到被验证的图片资源，路径穿越或任意路径输入被拒绝。
- AC10：窗口保持无边框、900×650 默认尺寸、800×600 最小尺寸；标题栏拖动、边缘缩放、最小化、最大化切换和关闭均可用。
- AC11：窗口移动或尺寸变化后保存当前正常窗口边界；启动时恢复可见屏幕内的窗口，显示器布局改变后窗口不能遗留在不可见屏幕区域。
- AC12：关闭按钮仍隐藏到托盘；托盘双击或“显示工作台”恢复窗口；暂停和停止仍触发现有后端动作；明确选择“退出”才结束后端。
- AC13：页面只能访问获准本地来源；未知导航、弹窗、下载和外部来源消息不会得到宿主权限。
- AC14：Tauri IPC 使用有限命令集合；错误格式、未知命令、非授权窗口、错误来源或越权参数均无副作用，自定义命令也必须有显式权限约束。
- AC15：Runtime 存在时使用已安装的 Evergreen Runtime；缺失时显示安装说明，安装后重试能启动；离线缺失时不误报成功。
- AC16：发行目录中不包含 Fixed Version Runtime 二进制；Runtime 更新由 Evergreen 安装机制维护。
- AC17：NSIS 安装包和 portable x64 均保留快捷方式/启动入口所承诺的行为、用户数据路径和卸载/升级边界。
- AC18：对最终 NSIS 和 portable 文件逐个读取字节数，且都满足 bytes < 100000000；不能用 MiB 估算代替。
- AC19：回退到 Electron 发布版时，数据库、截图和图片覆盖仍可读取；回退不依赖 WebView2 profile。
- AC20：正式宿主使用 Tauri 2/Rust，不要求 .NET Framework；前端资源由 Tauri 打包，生产页面实际来源为 http://tauri.localhost，FastAPI 不承担新增 /ui 页面服务。
- AC21：来自可信 Tauri 页面、携带正确 token 的 API/WS 请求成功；其他来源、缺失或错误 token 被拒绝。CORS 预检和 CSP 允许既有截图、图片和裁剪器正常工作。
- AC22：能力配置仅授权主窗口；自定义命令权限和 IPC 调用方检查均通过负样本验证，前端不获得通用 shell、文件系统或后端进程启动权限。
- AC23：单文件 portable 在普通用户权限下解出并启动完整后端资源；重启、版本升级和退出清理不丢失数据库或把用户数据留在临时解压目录。
- AC24：首次导入使用当前 portable 的最新一致性快照，目标为永久 userData/config/ui_workbench.db；原库及安装版/开发版库保持不变，记录来源，不自动合并。
- AC25：永久目标已存在时不覆盖，正常启动复用已有有效库；源库不可用或初始状态存在冲突时明确报告，不能静默使用过期快照或空库代替。
- AC26：只对 yys-gui-theme 和 yys-gui-nav-collapsed 采用首次默认策略；截图、图片覆盖、窗口状态及其他业务设置不随之重置。
- AC27：显式 create_app(db_path=...) 优先于新增桌面数据库路径配置，无配置时保持既有 cwd 回退；api_token、user_data_dir 的原职责和调用契约不改变。
- AC28：回退前保留 Tauri 永久库的最新一致性快照，明确旧版数据库读取方式；不能宣称旧 Electron 自动读取新库，也不能丢弃迁移后新增的记录。

## 验收矩阵

- 操作系统：Windows 10 x64（至少 22H2）和 Windows 11 x64；记录每台机器的完整版本号。
- 安装包：NSIS 与 portable x64。
- Runtime：Evergreen Runtime 已安装；未安装但网络可用并完成安装；未安装且离线；取消安装或安装失败。
- 存储：已有数据库、截图、图片覆盖、主题/折叠偏好升级路径；首次启动空数据路径。
- 安全：错误页面来源、外部导航、伪造/畸形 IPC、非授权窗口、缺失 capability、未知命令、路径穿越和不存在的资源 ID。
- 窗口与托盘：多屏移动后拔除副屏、DPI 缩放、最大化恢复、关闭到托盘、托盘暂停/停止/退出。

## 规划完成标准

- prd.md、design.md 和 implement.md 已完成并通过用户审阅。
- 当前已启动阶段 0，task.json 为 in_progress；阶段 1 须先通过阶段 0 工具与数据门槛。
- 工具链已验收，数据库迁移与首次偏好策略已确认，阶段 0 门槛通过；实际迁移、产品构建和阶段 1 代码开发均未执行，本会话继续仅检查规划。
