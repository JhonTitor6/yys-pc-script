# 阶段 2 实施记录

日期：2026-10-18（Asia/Shanghai）。对应任务：`webview2-shell-migration`。

## 结论

阶段 2 的宿主启动链路、后端跨源边界与 CSP 已在真实 Python 后端上完成联调并通过；打包映射、下载拒绝与异常退出回收仍留待后续阶段。

## 已完成

| 项 | 实现 | 验证 |
|---|---|---|
| 后端 CORS | `ALLOWED_ORIGINS` 精确加入 `http://tauri.localhost` | 契约测试：允许该来源、拒绝未知来源 |
| 后端 WS 边界 | `/ws/events` 先校验 Origin 再校验 token | 契约测试：未知 Origin 断开，Tauri Origin 通过 |
| 后端进程模块 | 新增 `backend.rs`：端口探测、32 字节 token、受控 spawn、30 秒鉴权就绪等待、提前退出检测、终止回收 | 4 项 Rust 单元测试 |
| 启动时序 | 端口空闲才启动；就绪后才在主线程创建窗口与托盘，失败走原生错误框并以 1 退出 | 烟测、端口占用场景与真机联调 |
| 环境注入 | `YYS_UI_TOKEN`、`YYS_USER_DATA_DIR`、`PYTHONIOENCODING=utf-8` 与 cwd 由宿主注入 | 假后端回报 `backend-env.json` 并断言 |
| 退出回收 | `RunEvent::Exit` 终止本宿主创建的子进程 | 烟测断言假后端 PID 已消失 |
| 打包映射 | `bundle.resources` 把 `../build/backend` 映射到 `backend` | 仅配置，未构建验证 |
| 烟测升级 | 宿主真实拉起假后端、端口占用失败路径、CSP 图片放行 | 三种模式全部通过 |

## 真机联调（2026-10-18 21:53）

- 关闭旧 portable（进程树 40364 → 41712 → 39216）后 8000 释放，未触碰其业务数据。
- 开发库 `config/ui_workbench.db` 含一条过期定时工作流（狭间暗域，`next_run_at=2026-09-27T21:03`）。为避免启动时触发游戏业务，联调使用**副本库**并停用该工作流，原库全程只读；联调结束按 SHA-256 校验恢复（`7a593c4d…9b75`，恢复前后一致）。
- 普通构建宿主启动后：子进程为 `python.exe -m ui_backend.main`，8000 由该子进程监听；窗口标题“阴阳师脚本工作台”。
- 页面实拍：连接状态显示“已连接”，脚本列表与工作台布局正常，说明 HTTP 鉴权与 CORS 通过、WebSocket 以 Tauri Origin + token 建立成功。
- 窗口按旧 `window-state.json` 恢复到 `3001,406 1316×692`，与实际旧文件完全一致，验证 AC11 的旧格式兼容。
- WebView2 profile 建立在 `%APPDATA%\yys-script-manager\WebView2\EBWebView`；旧 Electron profile（`Local Storage` 等）未被改动。
- 发送 `WM_CLOSE` 后窗口隐藏、宿主存活、8000 仍监听，验证“关闭到托盘、后端保留”。
- 强制结束宿主后后端成为孤儿进程（本次手工回收），确认异常退出回收仍需阶段 3 的 Job Object 方案，当前不宣称已覆盖。

## 验证结果

```powershell
& C:/Users/56440/.cargo/bin/cargo.exe +1.99.1 test --manifest-path gui/src-tauri/Cargo.toml --locked --target x86_64-pc-windows-msvc --target-dir build/tauri-target
& D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend -q
node tests/gui/test_desktop_bridge.js
node tests/gui/test_renderer_config.js
node tests/gui/test_backend_detection.js
& D:/ProgramData/anaconda3/envs/win_macro/python.exe tests/gui/run_tauri_smoke.py build/tauri-target/yys-desktop-smoke.exe
& D:/ProgramData/anaconda3/envs/win_macro/python.exe tests/gui/run_tauri_smoke.py build/tauri-target/yys-desktop-smoke.exe --restore
& D:/ProgramData/anaconda3/envs/win_macro/python.exe tests/gui/run_tauri_smoke.py build/tauri-target/yys-desktop-smoke.exe --blocked
```

- Rust 测试 8/8 通过（新增 backend 4 项）。
- 后端测试 123/123 通过（新增 CORS 与 WS Origin 两项）。
- JS 桥接、renderer 配置、后端探测三套测试通过。
- 烟测三模式全部 exit 0：默认 `build/tauri-smoke/20261018-214733-385214`、恢复 `build/tauri-smoke/20261018-214745-943576`、端口占用 `build/tauri-smoke/20261018-214754-931291`。
- 默认烟测断言：宿主以真实启动路径拉起假后端、注入四项环境、就绪后才建窗、页面 21 项检查通过（含“CSP 允许后端图片”）、WS 带 Origin 与 token 建立、退出后子进程不存活。
- 构建标记：普通 12,743,680 bytes 无标记；烟测 12,807,680 bytes 有标记。

## 本轮改动

- `ui_backend/app.py`：CORS 白名单与 WebSocket Origin 校验。
- `tests/ui_backend/test_app_api.py`：新增 CORS 与 WS Origin 两项契约测试。
- `gui/src-tauri/src/backend.rs`（新增）：探测、token、spawn、就绪等待、回收。
- `gui/src-tauri/src/main.rs`：启动线程、就绪后开窗、失败提示与退出、退出回收。
- `gui/src-tauri/src/smoke.rs`：烟测启动配置与 `after_window` 接管；标记更名为 `YYS_TAURI_SMOKE_ONLY`。
- `gui/src-tauri/Cargo.toml` / `Cargo.lock`：显式依赖 `getrandom 0.3`。
- `gui/src-tauri/tauri.conf.json`：`bundle.resources` 映射。
- `tests/gui/fake_backend.py`（新增）：由宿主拉起的假后端。
- `tests/gui/run_tauri_smoke.py`：改为宿主拉起模式，新增 `--blocked`。
- `tests/gui/tauri-smoke.js`：新增 CSP 图片放行检查。

## 未完成与后续

1. **打包映射未验证**：`bundle.resources` 只写入配置，需要 PyInstaller 后端产物和一次打包才能验证 `_internal`、模型与图片的相对布局（属阶段 4）。
2. **异常退出回收**：强杀宿主会遗留后端进程，需要阶段 3 的进程归属记录与 Windows Job Object。
3. **下载拒绝仍只有代码审查**：WebView2 下载开始事件可能在请求发出后触发，用假后端日志无法得到无歧义断言。
4. **失败提示为原生消息框**：`--blocked` 只在烟测构建验证了文件记录与退出码，真实消息框未实机确认。
5. **真实数据展示**：联调用的是停用定时工作流的副本库，未在真实库上验证运行历史与截图页面的完整展示。
