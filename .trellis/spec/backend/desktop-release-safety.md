# Tauri 桌面发行的数据与鉴权安全契约

## 1. 适用范围

修改首次数据库迁移、桌面后端日志或 NSIS 便携载荷生命周期时适用。阶段 5 的 F1/F2/F3 已证明，基础启动成功不能替代并发、更新和日志边界验收。

## 2. 接口

- `migrate_legacy_database(target: Path, source: Path | None) -> str`。
- `resolve_db_path(db_path=None)`：显式参数 → `YYS_WORKBENCH_DB_PATH` → cwd。
- `ui_backend.main.RedactTokenFilter.filter(record: logging.LogRecord) -> bool`。
- `python tests/gui/check_portable_package.py --output build/tauri-stage5/portable-regression.json`。
- `python tests/gui/run_tauri_smoke.py <smoke-exe> --displays`。

## 3. 不变契约

- 已存在的目标库不覆盖、不合并。每个迁移者使用独立的同目录临时文件，SQLite backup 和完整性检查完成并关闭句柄后才发布。
- 使用 `os.link(staging, target)` 原子、不覆盖发布；目标在复制期间出现时抛出 `FileExistsError`。目标卷不支持硬链接时明确失败，不降级成覆盖。异常路径同样关闭句柄、只清理本次临时文件。
- 数据库 schema、参数优先级、API token 与 `user_data_dir` 职责保持不变。
- 日志过滤覆盖 Uvicorn 访问日志与连接日志，包括 URL 中 `?token=` 和 `&token=`；保留访问日志五元组供 AccessFormatter 格式化，不通过清空 args 隐藏日志错误。
- HTTP token 仍必需；未知 HTTP Origin 不额外返回拒绝，只不给 CORS 允许头。WebSocket 的浏览器 Origin 白名单与 token 双重校验保持（2026-10-19 用户确认）。
- 便携版每次完整解压到独立 `$PLUGINSDIR/runtime`，不复用同版本旧缓存；`ExecWait` 结束后离开载荷 cwd，让 NSIS 清理临时目录。永久库、截图、覆盖图及 WebView2 profile 始终位于 APPDATA。
- 不清理历史 portable-runtime 缓存来修复当前包，更不能递归清理永久 userData。

## 4. 验证与错误矩阵

| 条件 | 要求 |
|---|---|
| 入口已有目标库 | 返回 target-exists，内容不变 |
| 发布前并发出现目标库 | 明确冲突失败，保留胜者，双方临时副本独立 |
| 来源损坏/缺失 | 明确失败，不发布空目标，不留下打开的副本 |
| 正确 token + 未知 HTTP Origin | 正常业务状态，不返回 CORS 允许头 |
| 缺失/错误 token | HTTP/WS 拒绝 |
| 错误浏览器 WS Origin | 拒绝，即便 token 正确 |
| HTTP 图片或 WS URL 含 token | 日志保留路径、状态，值替换为 [REDACTED] |
| 相同版本的新便携包 | 使用本包完整载荷，每次独立解压 |
| 便携宿主退出 | 临时载荷清理，永久数据保留 |
| 多屏测试 | 记录真实工作区、缩放和实际窗口尺寸；100% 双屏不能记成混合 DPI 通过 |
| 空 Runtime 目录初始化失败 | 只证明实际初始化失败路径，不能记成整机真实 Runtime 缺失通过 |

## 5. 正确、基础与错误样例

- 正确：两个迁移者竞争同一目标，胜者数据保留，后者明确失败。
- 基础：只验证入口已有目标不覆盖，仍不能证明没有发布竞争。
- 错误：复制前后各加一次 exists 检查，再 os.replace；检查与覆盖之间仍存在竞争。
- 正确：同版本新包逐次解出完整载荷；错误：只检查两个 EXE 就跳过依赖目录。

## 6. 必需回归

- `pytest tests/ui_backend/test_workbench_db.py tests/ui_backend/test_logging.py tests/ui_backend/test_app_api.py`。
- 数据库断言来自 AC24/25/27：竞争胜者、独立副本、异常清理、原 schema/优先级。
- 日志断言覆盖真实 AccessFormatter，以及直接字符串、元组和字典的连接日志。
- `check_portable_package.py` 用真实 NSIS/最小宿主证明同版本更新、不同 cwd、重复启动、不同临时路径和退出清理；仍需完整发行包实测。
- 当前支持的真实 Win10/11、Runtime 安装与缺失、显示器和 DPI 矩阵必须分别留证；用户延后或环境不可用只记待验。

## 7. 错误与正确对照

```python
# 错误：发布前有并发目标时会覆盖新数据。
os.replace(staging, target)
# 正确：同卷原子发布；冲突及不支持的文件系统都明确报错。
os.link(staging, target)
```

实现依据：[NSIS 临时目录与 cwd 清理契约](https://nsis.sourceforge.io/Docs/Chapter4.html)、[WebView2 进程环境覆盖](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/webview2-idl)。
