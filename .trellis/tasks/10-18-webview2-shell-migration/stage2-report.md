# 阶段 2 实施记录

日期：2026-10-18（Asia/Shanghai）。对应任务：`webview2-shell-migration`。

## 结论

阶段 2 的全部遗留项已逐项补齐：宿主启动链路、后端跨源边界、CSP、下载拦截、崩溃回收、原生错误提示、真实数据展示与打包映射均在真实后端或真实产物上验证通过，未留下未验证项。

## 已完成

| 项 | 实现 | 验证 |
|---|---|---|
| 后端 CORS | `ALLOWED_ORIGINS` 精确加入 `http://tauri.localhost` | 契约测试：允许该来源、拒绝未知来源 |
| 后端 WS 边界 | `/ws/events` 先校验 Origin 再校验 token | 契约测试：未知 Origin 断开，Tauri Origin 通过 |
| 后端进程模块 | 端口探测、32 字节 token、受控 spawn、30 秒鉴权就绪等待、提前退出检测 | 4 项 Rust 单元测试 |
| 启动时序 | 端口空闲才启动；就绪后才创建窗口与托盘，失败走原生错误框并以 1 退出 | 烟测、端口占用场景与真机联调 |
| 环境注入 | `YYS_UI_TOKEN`、`YYS_USER_DATA_DIR`、`PYTHONIOENCODING=utf-8` 与 cwd 由宿主注入 | 假后端回报 `backend-env.json` 并断言 |
| 退出回收 | `RunEvent::Exit` 主动终止；Windows Job Object（`KILL_ON_JOB_CLOSE`）兜底宿主崩溃 | `--crash` 烟测与真实宿主强杀均无残留 |
| 下载拦截 | `on_download` 一律拒绝；烟测构建回报定向事件 | 同源资源触发下载，页面收到 `download-blocked` |
| 原生错误提示 | 失败时弹出 Windows 消息框（`MB_ICONERROR`），关闭后退出码 1 | 实拍对话框并实测退出码 |
| 真实数据展示 | 真实后端 + 真实库副本渲染历史页与截图库 | 历史页 #39–#33、截图库 11 张实拍 |
| 打包映射 | `bundle.resources` 把 `../build/backend` 映射到 `backend` | tauri-build 已复制到发布目录，发布版宿主解析并拉起 |

## 真机联调（2026-10-18 21:53 与 22:29）

- 关闭旧 portable（进程树 40364 → 41712 → 39216）后 8000 释放，未触碰其业务数据。
- 开发库 `config/ui_workbench.db` 含一条过期定时工作流（狭间暗域，`next_run_at=2026-09-27T21:03`）。为避免启动时触发游戏业务，联调使用**副本库**并停用该工作流，原库只读；每次联调结束按 SHA-256 校验恢复（`7a593c4d…9b75`，恢复前后一致）。
- 开发版宿主：子进程 `python.exe -m ui_backend.main`，8000 由其监听；页面“已连接”，脚本列表正常。
- 窗口按旧 `window-state.json` 恢复到 `3001,406 1316×692`，与旧文件完全一致（AC11 旧格式兼容）。
- WebView2 profile 建立在 `%APPDATA%\yys-script-manager\WebView2\EBWebView`；旧 Electron profile 未改动。
- 历史页渲染真实运行记录（#39 已完成、#38 已停止、#37–#35 已停止等）；设置页的永久截图库渲染 11 张真实截图（含尺寸、来源、时间）。
- `WM_CLOSE` 后窗口隐藏、宿主存活、8000 仍监听（关闭到托盘）。
- 强杀宿主后后端不再成为孤儿（Job Object 回收），8000 立即释放。

## 打包与发布版验证（2026-10-18 22:20–22:30）

- 现有 onedir 产物直接运行通过：`/api/scripts` 15 个脚本、`/api/image-resources` 178 项、图片内容 7414 字节，`yys/` 与 `config/` 目录齐全。
- `cargo build --release` 后，`release/backend` 由 tauri-build 按 `bundle.resources` 复制（364 个文件，含 `yys`、`config`），发布版宿主以 `resource_dir()/backend/yys-backend.exe` 启动成功。
- 首轮发布版联调暴露一个真实构建顺序问题：旧 onedir 产物早于 CORS 修改，页面因跨源被拒显示“未连接”。重建 PyInstaller 后端后同一发布版宿主恢复正常（“已连接”、脚本列表可见）。结论：打包前必须重建后端，属阶段 4 发布流水线的硬性前置。

## 验证结果

```powershell
& C:/Users/56440/.cargo/bin/cargo.exe +1.99.1 test --manifest-path gui/src-tauri/Cargo.toml --locked --target x86_64-pc-windows-msvc --target-dir build/tauri-target
& D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend -q
node tests/gui/test_desktop_bridge.js
node tests/gui/test_renderer_config.js
node tests/gui/test_backend_detection.js
& D:/ProgramData/anaconda3/envs/win_macro/python.exe tests/gui/run_tauri_smoke.py build/tauri-target/yys-desktop-smoke.exe [--restore|--blocked|--crash]
```

- Rust 测试 8/8；后端测试 123/123；JS 三套测试通过；ruff 与 `git diff --check` 通过。
- 烟测四模式全部 exit 0：
  - 默认（含下载拦截）：`build/tauri-smoke/20261018-220512-676312`
  - 恢复：`build/tauri-smoke/20261018-220526-130028`
  - 端口占用：`build/tauri-smoke/20261018-220534-710287`
  - 崩溃回收：`build/tauri-smoke/20261018-220535-473923`
- 实拍证据：`build/e2e-failure-dialog.png`、`build/e2e-history-view.png`、`build/e2e-settings-view.png`、`build/e2e-screenshot-library.png`、`build/e2e-release-host2.png`。

## 本轮改动

- `ui_backend/app.py`：CORS 白名单与 WebSocket Origin 校验。
- `tests/ui_backend/test_app_api.py`：新增 CORS 与 WS Origin 两项契约测试。
- `gui/src-tauri/src/backend.rs`（新增）：探测、token、受管 spawn、就绪等待、Job Object 回收。
- `gui/src-tauri/src/main.rs`：启动线程、就绪后开窗、失败提示与退出、退出回收、下载拒绝与回报。
- `gui/src-tauri/src/smoke.rs`：烟测启动配置与 `after_window` 接管。
- `gui/src-tauri/Cargo.toml` / `Cargo.lock`：显式依赖 `getrandom 0.3`。
- `gui/src-tauri/tauri.conf.json`：`bundle.resources` 映射。
- `tests/gui/fake_backend.py`（新增）：由宿主拉起的假后端。
- `tests/gui/run_tauri_smoke.py`：宿主拉起模式，新增 `--blocked` 与 `--crash`。
- `tests/gui/tauri-smoke.js`：新增 CSP 图片、下载拦截检查；最大化/还原改为有界轮询。

## 仍未覆盖（属阶段 4–5，不在阶段 2 范围）

1. NSIS 与单文件 portable 产物、包体积门槛、Runtime 缺失/安装矩阵。
2. Windows 10 22H2 实机、真实多屏拔插与多 DPI 往返。
3. 真实数据迁移（阶段 3）与回退验证。
4. 真实 Explorer 打开/选中行为（烟测构建短路，未实机点击）。
