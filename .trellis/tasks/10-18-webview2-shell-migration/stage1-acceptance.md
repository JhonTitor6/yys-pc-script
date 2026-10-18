# 阶段 1 验收记录

日期：2026-10-18（Asia/Shanghai）。对应任务：`webview2-shell-migration`。基于 `stage1-report.md` 的交付与代码级审阅，不替代报告中的实施过程记录。

## 结论

阶段 1 验收通过（附条件）。九项交付均落地且可复现；工程检查、契约测试、两次隔离烟测全部通过，未发现阻塞问题。

本轮同时修复了审阅发现的 3 项问题（写盘节流、恢复回退目标、导航/新窗口负样本），并复核后降级 1 项原判定。剩余风险与未验证边界见文末。

## 复验基线

- 仓库 `F:/Users/56440/PythonProjects/yys-pc-script`，分支 `master`，HEAD `d11c01f9730c4fa376da7dfaa1988e2a08f43986`（复验期间未变，提交见记录边界）。
- 工具链：Rust/Cargo 1.99.1、`x86_64-pc-windows-msvc`、tauri 2.12.3、tauri-build 2.7.2、tauri-runtime 2.12.2、wry 0.57.0、dunce 1.0.5、CLI 2.12.2。
- 全程未触碰 8000 端口（仍由 PID 39216 占用）、未启动真实后端、未运行普通宿主、未迁移或读取用户业务数据。
- 真实用户目录 `%APPDATA%\yys-script-manager` 的 `window-state.json` 修改时间保持为 18:06:39，证明烟测隔离有效。

## 复验结果

| 项目 | 结果 |
|---|---|
| `cargo test`（`--locked`） | 4/4 通过（含本轮新增的节流测试） |
| `cargo fmt --check` / `cargo check --locked` | 通过 |
| `node tests/gui/test_desktop_bridge.js` | 通过 |
| `node tests/gui/test_renderer_config.js` / `test_backend_detection.js` | 通过 |
| `node --check gui/renderer.js` / `tests/gui/tauri-smoke.js` | 通过 |
| `ruff check tests/gui/run_tauri_smoke.py` | 通过 |
| `git diff --check` | 通过 |
| 隔离烟测（默认） | 20 项检查通过，证据 `build/tauri-stage1-smoke/20261018-213405-296440`（端口 50115） |
| 隔离烟测（`--restore`） | 20 项检查通过，证据 `build/tauri-stage1-smoke/20261018-213416-330702`（端口 51825） |
| 图片资源 ID | 178 个，与 `win_util.image.production_image_ids` 逐项一致 |
| staging 受控性 | 仅 6 个白名单文件，5 个文件哈希与源一致，无符号链接 |
| 构建标记隔离 | 普通 12,740,608 bytes 无烟测标记；烟测 12,784,640 bytes 有标记 |

原生窗口证据（两次烟测一致）：900×650、最小 800×600、无边框、可缩放、左边框命中 HTLEFT、位于可见屏幕内。

烟测覆盖的新增项：`拒绝外部导航`、`拒绝新窗口`（均为本轮补充）。

## 审阅发现与处置

| # | 发现 | 处置 |
|---|---|---|
| 1 | `Moved/Resized/ScaleFactorChanged` 每个事件同步写盘，设计要求的 debounce 未实现 | 已修：250ms 时间节流，关闭与退出仍强制写入；新增单元测试 |
| 2 | 多屏不同 DPI 下坐标空间混用 | 复核后降级为风险（见下方说明），本轮不改 |
| 3 | 保存位置不可见时回退到显示器列表第一项，可能不是主屏 | 已修：用 `primary_monitor` 定位主屏下标；实测恢复落到主屏 |
| 4 | 导航/新窗口/下载缺少负样本 | 导航与新窗口已补；下载保留为代码审查项 |
| 5 | Rust 构建新增 Node 与 `gui/node_modules` 前置依赖未文档化 | 已在 `build.rs` 注明前置条件 |
| 6 | 图片覆盖白名单编译期固化，与后端运行时资源列表可能漂移 | 记录为阶段 2 风险，未改 |
| 7 | npm 审计 25 个漏洞（4 中危/20 高危/1 严重） | 未处理，维持报告结论 |

### 关于第 2 项（多 DPI）的复核说明

原判定为“逻辑/物理坐标空间混用”，复核后认为该描述过强：保存值是“物理坐标 / 保存时所在屏缩放”，与同一屏的逻辑工作区范围天然对齐，选择与钳制在同一块屏内自洽；多屏场景下真正残留的问题是**不同 DPI 的多块屏可能同时包含同一保存点，代码按列表顺序取首个匹配**，属于选择歧义而非单位混用。

因此不对恢复算法做无实机依据的改动，改由阶段 2 在真实多 DPI / 拔插矩阵中验证并给出统一方案。新增的 `fit(saved, screens, index)` 参数已把“钳制到哪块屏”从隐式选择变成显式输入，便于后续替换选择策略。

### 关于第 4 项的边界

下载拒绝（`on_download` 返回 false）未加自动化负样本：WebView2 的下载开始事件可能在请求发出后才触发，用假后端请求日志无法得到无歧义断言。该项仍只有代码审查，需要实机点一次下载链接确认。

## 本轮代码变更

- `gui/src-tauri/src/window_state.rs`
  - `save` 增加 `throttle` 参数与 `SAVE_INTERVAL`/`LAST_SAVE` 时间节流；带 `ponytail:` 注记说明“只节流、无尾随补写”的天花板与升级路径。
  - `fit` 改为接收显式显示器下标；新增 `contains`、`primary_index`；`restore` 在保存位置不可见时改回主屏。
  - 新增节流测试，扩充主屏下标与越界下标断言。
- `gui/src-tauri/src/main.rs`：三处 `window_state::save` 调用区分强制/节流。
- `tests/gui/tauri-smoke.js`：新增外部导航与新窗口的负样本。
- `gui/src-tauri/build.rs`：注明 Node 与 `gui/node_modules` 前置条件。

## 未验证边界（继承自阶段 1 报告，仍全部有效）

- 未构建/运行正式发行包，未做包体积与发行完整性声明。
- 未运行普通（非 smoke）宿主：真实 8000 后端、CSP 在真实后端下的表现、`ready=false` 首屏均未实机验证。
- 真实 `explorer.exe` 打开/选中行为未实机验证：烟测构建在 `open_directory` 中直接短路返回，`opened: true` 只证明路径校验。
- 未验证 Win10 22H2、真实多屏拔插、不同 DPI 往返、人工拖动/托盘点击、Runtime 缺失流程。
- Electron 回退包未重新构建或运行；renderer 改动在无 `bootstrap` 时保持旧行为，属代码级兼容判断。
- 一次页面初始化超时（阶段 1 实施期间）根因未确认；本轮两次烟测均未复现。

## 阶段 2 前置要求

1. 真实后端接入时同步验证：CORS/WS Origin、token 传递、CSP、图片与裁剪器。
2. 多 DPI / 多屏恢复按第 2 项给出统一方案并补实机矩阵。
3. 图片资源白名单改为与后端运行时列表一致，避免打包漂移。
4. 下载拒绝、真实 Explorer 启动补实机验证。
5. `ready=false` 阶段的主窗口展示策略（当前会显示壳并提示初始化失败）需在阶段 2 明确是否改为就绪后再显示。

## 记录边界

本轮按功能边界提交为两笔代码提交（`f593c78` 宿主与页面打包、`fd2509a` 契约与烟测），任务文档随本记录所在提交纳入；未推送、未归档。未修改 PRD、`design.md`、`implement.md` 或阶段 1 报告。任务状态仍为 in_progress，阶段 2 起需单独授权。
