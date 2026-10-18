# 阶段 0 核验记录

日期：2026-10-18，Asia/Shanghai。任务为 in_progress，仍处阶段 0。初期只读核验后，用户授权独立会话补装工具链；安装现已完成并由原会话验收。原会话只检查、规划，没有进入阶段 1 产品代码开发，也没有启停工作台或游戏。

## 后续安装授权与分发

2026-10-18，用户在只读核验后允许补齐安装，并要求使用 GPT-6 Luna / max 新会话。安装会话 01a14ee9-f61e-7d82-bc25-b5f819aa2bf3（local）已完成并回报 install-report.md；原会话 01a14ebb-848c-73e3-8c01-5a3cdd91bb1e 已进行只读验收，结果见 installation-review.md。安装与隔离依赖探针在授权范围内；正式宿主与业务代码未开发。后文运行态路径和数据库大小仍保留初始快照，工具链表已更新为验收结果。

## 结论与门槛

初期只读核验、数据库副本保护和后续工具链安装均已完成；安装后已由原会话只读验收。工具门槛通过；用户现已回复“是”确认数据库迁移及首次展示偏好策略，因此阶段 0 门槛整体通过。实际迁移、正式产品开发和发行验证尚未执行。当前结论见 installation-review.md，安装原始记录见 install-report.md。

| 核验项 | 结果 |
|---|---|
| Git/改动范围基线 | 已记录，初始仅本任务目录；过程中出现其他来源的 OCR/测试修改，未触碰。 |
| 本机工具链 | 补装与验收通过：Rust/Cargo 1.99.1、Windows SDK 10.0.19041、CLI 2.12.2；原 MSVC 保留，NSIS 实际打包复用仍待后续验证。 |
| 版本矩阵 | 精确版本已安装/恢复并通过隔离探针；只有探针 Cargo.lock，尚无正式工程锁文件，未完成产品集成。 |
| OS/WebView2 | 本机为 Windows 11 Pro x64，10.0.22631；共享 Runtime 文件存在，未执行新宿主初始化。 |
| NSIS/portable/开发数据路径 | 已分别确认并做数据库一致性快照，原库保留，未合并。 |
| 两个展示偏好迁移 | 用户确认首次仅主题/折叠恢复默认，后续正常持久化；不做 LevelDB 导入，不修改旧 profile。 |
| 单文件 portable 方案 | 策略已明确：完整载荷与永久数据分开，当前 portable 库无损复制到旧 userData/config/ui_workbench.db，另两库保留不合并；封装实测留待后续实施。 |

Windows SDK 与 Rust/Tauri 工具阻断已解除，临时库迁入永久目录、导入来源和首次偏好策略也已获用户确认；本会话继续仅检查规划。以下运行态路径和数据大小仍是初次核验快照，不是安装后重新采集的应用状态。

## Git 与执行边界

- 分支：master，初始相对 origin/master ahead 32。
- 初始 HEAD：056b9f099cdee5070e14405c2e86d75f63a8577b。
- 初始未提交路径只有本任务目录中的 task.json、prd.md、design.md、implement.md、implement.jsonl、check.jsonl。
- 过程中出现以下非本轮操作产生的修改/新增，未回滚、暂存或提交：tests/common/test_lineup.py、yys/daily_activity_rewards/test_daily_activity_rewards.py、conftest.py、tests/common/ocr_cache.py、tests/common/test_ocr_cache.py。
- 最终复核 HEAD 已由其他操作推进到 d11c01f9730c4fa376da7dfaa1988e2a08f43986（test(perf): 缓存重复回放截图的 OCR 结果），master ahead 33；前述 OCR/测试改动及其质量规范已进入该提交，当前 Git 未提交项仅为本任务目录。本轮没有执行 git add/commit。
- 本轮自有 Git 变化限定在本任务目录；数据库快照在已被 .gitignore:20 的 build/ 规则忽略的目录，不包含在 Git 变化中。
- 未读取或输出实际 UI token、配置秘密和数据库业务记录内容；没有复制数据库到 Trellis 文档目录。

## 工具链与版本

完整路径、组件核验和版本来源见 phase0-toolchain.md。

| 项目 | 当前核验 |
|---|---|
| Node / npm | 24.13.0 / 11.6.2，Node 实际位于用户 Volta tools/image/node/24.13.0。 |
| Visual Studio | Community 2019 16.11.36422.26，MSVC 14.29.30133 的 x64/x86 工具存在。 |
| Windows SDK | 初查缺失，现已补装并复核 10.0.19041.0 的头文件、x64 库与 rc.exe。 |
| Rust/Cargo/rustup | 已安装到标准用户目录，Rust/Cargo 1.99.1；原会话使用绝对路径核验成功。 |
| Tauri | CLI 2.12.2 位于 build/tauri-tools；隔离依赖探针已锁定核心 2.12.3/build 2.7.2，正式工程及其 Cargo.lock 仍不存在。 |
| NSIS / 7-Zip | electron-builder 缓存 NSIS 3.0.4.1、资源 3.4.1 和 7-Zip 存在；未证明 Tauri bundler 可直接复用。 |
| 打包 Python | build/package-env/Scripts/python.exe 存在；pyvenv.cfg 标记 Python 3.11.11。未导入其业务库或运行构建验证。 |

已采用的精确版本：Rust 1.99.1 / x86_64-pc-windows-msvc、tauri 2.12.3、tauri-build 2.7.2、项目级 @tauri-apps/cli 2.12.2。隔离依赖检查和 SDK 链接探针由安装会话完成，原会话复核版本、锁文件和工件，未重复构建；这不等于正式宿主通过验证。

默认只安装项目级 Node CLI，不另装全局 cargo-tauri；@tauri-apps/api 2.12.3 是可用版本参考，现有纯 JS 可先用 withGlobalTauri 官方全局 API，不为此强制新增模块包。Cargo.lock 应在阶段 1 正式工程首次获准恢复依赖时生成，不预造锁文件。

## 当前发行物与运行态

| 项目 | 实测值 |
|---|---|
| 现有 NSIS EXE | dist-electron/阴阳师脚本工作台-1.0.0-x64.exe，178,086,348 bytes。 |
| 现有 portable EXE | dist-electron/阴阳师脚本工作台-1.0.0-portable.exe，177,871,780 bytes。 |
| 现有 backend 载荷 | win-unpacked/resources/backend 共 363 个文件，255,389,396 bytes。 |
| 当前启动入口 | 旧 Electron portable，启动器 PID 40364、主宿主 PID 41712。 |
| 当前 backend | PID 39216，位于下述 Temp 解压目录，监听 127.0.0.1:8000。 |
| 已安装 NSIS 目录 | D:/Program Files/新建文件夹/yys-script-manager。 |
| 旧安装注册信息 | HKLM/Software/5fdb831f-d9ac-50c9-9ea2-d81cdf968b5d 的 InstallLocation 为上述目录；卸载条目含 /allusers，不能只查 HKCU。 |

当前 backend 目录：

    C:/Users/56440/AppData/Local/Temp/3KrSKcQ9k6mJMbE4Pan6Dstn8JQ/resources/backend

- 通过既有 @electron/asar 库只读读取了 win-unpacked、当前 portable 解压目录、已安装 NSIS 三处 app.asar；main.js 均与仓库当前文件 SHA-256 一致：
  828f0ca8b8e54e9d551d915a2bf9d6d17045ae6e49719753c02988df52264cc6。
- 这些启动代码将 packaged backend cwd 设置为 backend EXE 的目录，将 YYS_USER_DATA_DIR 指向 app.getPath('userData')。
- cwd 结论来自实际运行包中的启动代码及对应数据库文件位置，未读取进程 PEB，也未注入或操控进程。
- 8000 端口已由用户运行的后端占用，未发送 API 请求、未抢占或终止该进程；新宿主运行检查仍需后续隔离。
- backend 最大载荷包括 cv2.pyd（74,215,424 bytes）、OpenBLAS（38,168,576 bytes）、FFmpeg（26,391,552 bytes）及 ONNX Runtime。更换壳不能代替后端载荷压缩实测。
- 当前两个 Electron 包均超过新方案 100,000,000 bytes 目标。它们不是 Tauri 发行结果；旧约 73 MiB 估算不作为新方案通过依据。

## 数据位置与一致性副本

| 用途 | 原始路径 | 当前大小 |
|---|---|---:|
| 开发 SQLite | F:/Users/56440/PythonProjects/yys-pc-script/config/ui_workbench.db | 2,990,080 bytes |
| 已安装 NSIS SQLite | D:/Program Files/新建文件夹/yys-script-manager/resources/backend/config/ui_workbench.db | 57,344 bytes |
| 当前 portable SQLite | 上述 Temp/backend/config/ui_workbench.db | 73,728 bytes |
| 共享业务 userData | C:/Users/56440/AppData/Roaming/yys-script-manager | 现有截图、窗口状态及 Electron profile |
| 截图库 | userData/screenshots | 当前 22 个文件，未输出图片内容 |
| 图片覆盖 | userData/image-overrides | 当前目录不存在；名称来自 win_util/image.py:50 |
| 窗口状态 | userData/window-state.json | 1316×692，x=3001、y=406 |
| 旧展示偏好 | userData/Local Storage/leveldb | 000003.log，1,077 bytes |
| 新 WebView2 profile | 拟定 userData/WebView2 | 当前未创建 |

源码锚点：gui/main.js:78（后端位置）、gui/main.js:89（cwd）、gui/main.js:99（环境）、ui_backend/app.py:60（相对数据库路径）、win_util/image.py:50（图片覆盖根）。

关键事实：YYS_USER_DATA_DIR 当前只影响截图与覆盖图等用户目录，并没有改变 SQLite 的 cwd 相对定位。因此共享 userData 并不意味着三种发行形态已经共享一个数据库。

为避免当前 portable 退出后清理解压目录而失去迁移依据，阶段 0 已用 SQLite 只读源连接和 backup API 为三份库分别做一致性快照，未移动或合并原库：

    build/webview2-stage0-backups/20261018T200008+0800/

| 快照文件 | bytes | 快照 quick_check | SHA-256 |
|---|---:|---|---|
| development-ui_workbench.db | 2,990,080 | ok | b2018c0d4134836f1ea7ff6a6017a0e69b088b4b020f36c9a997210ecce84b19 |
| installed-ui_workbench.db | 57,344 | ok | bb9cf7e0e899f4268d61a23743b7ce1a1c6a79ff417e070811ff96db5244082f |
| portable-ui_workbench.db | 73,728 | ok | 052c0c3c91fd6b328022319c53d11b1721727c4edf6e4851da09e843b8a7906c |

快照时刻是 2026-10-18 20:00:08 +08:00；之后旧应用新增的数据不会自动同步。manifest.json 仅存于同一被 Git 忽略的备份目录。未把业务数据写入提交候选文件。

## 偏好迁移结果

- 已确认 LevelDB 文件含 yys-gui-theme 和 yys-gui-nav-collapsed 两个已知键及 file:// 来源标记。
- 当前没有既有的 LevelDB Python/Node 读取库可复用。
- 仅从日志命中字符串不能证明最新有效值、压缩/删除记录或完整迁移，不能凭这种扫描生成生产配置。
- 原 Electron profile 位于永久 userData，已保持原样；后续可以验证受控导出/导入路径。
- 用户已确认首次 Tauri 启动仅主题和导航折叠采用默认值，之后正常持久化。该范围不扩展到其他用户数据；当前只更新规划，尚未重置任何实际值。

## portable 与数据修正建议

以下是阶段 0 得到的设计建议，不是已完成集成或已执行迁移：

1. 单文件 portable 载荷包含 Tauri EXE 与完整 backend 目录，优先复用 NSIS 自解压/启动工具链，不能把裸 Tauri EXE 当作交付。
2. 程序载荷可位于专门的版本化缓存，永久用户数据必须独立；任何退出/升级清理都不得覆盖永久数据根。
3. 保持后端 cwd 的资源解析契约；为 SQLite 单独提供明确的绝对路径选择，避免为了数据库改变所有资源和日志的 cwd。最小建议是新增仅用于桌面发行的数据库路径环境输入，保留 create_app(db_path=...) 的显式参数优先级与现有无配置回退；该接口尚不存在、未实现。
4. 用户已确认永久目标为旧 userData/config/ui_workbench.db。业务文件格式/schema 不改变；旧库只读备份并复制导入，不能自动删除旧文件。
5. 用户已选当前 portable 为首次迁移来源，安装版/开发库分别保留、不自动合并。正式执行前重新一致性快照；源不可用时不能静默使用旧快照或新建空库，目标已存在时禁止覆盖。
6. 当前已发现的临时库问题需要调整“原数据库实际路径永久保持不动”的旧文字；真正需要保持的是已有数据可读且无损。永久截图、覆盖图和窗口文件路径继续维持。
7. NSIS 升级需同时读取旧 HKLM/HKCU 安装信息，保留已安装目录及其作用域边界；不能因新配置默认用户态就忘记旧 allusers 安装。

这些策略现已确认，实际实现留待后续获准的实施会话；本阶段未修改 app.py、启动脚本或源用户数据库。

## 后续动作与未验证范围

- 已获授权的工具链安装与验收已完成，不重复申请或执行相同安装；后续正式工程需要创建自己的依赖清单和锁文件。
- 数据库永久路径、导入来源和首次展示偏好策略已确认，阶段 0 通过；本会话不执行实际迁移或阶段 1 代码开发。
- 后续验证 NSIS 缓存复用、portable 自解压/清理、Tauri 真正初始化、最终安装包字节数和 Win10/11 矩阵。
- 初始核验阶段执行了文件/注册信息/进程/端口读取、包内启动代码读取、版本元数据读取及数据库副本 quick_check；后续安装和隔离探针由独立会话完成。原会话仍只做检查、规划；没有产品开发、产品构建、工作台或游戏操作。
