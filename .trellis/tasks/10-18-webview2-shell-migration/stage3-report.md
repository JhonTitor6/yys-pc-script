# 阶段 3 实施记录

日期：2026-10-18（Asia/Shanghai）。对应任务：`webview2-shell-migration`。

## 结论

阶段 3 已完成并在真实环境执行：数据库路径改为“显式参数 → `YYS_WORKBENCH_DB_PATH` → cwd 回退”，首次启动把旧 portable 库一致性复制到永久 userData，重复启动不再导入；退出回收、失败路径、偏好持久化与回退快照工具均已验证。

## 已完成

| 项 | 实现 | 验证 |
|---|---|---|
| 数据库路径优先级 | `resolve_db_path`：显式 `db_path` → `YYS_WORKBENCH_DB_PATH` → 原 cwd 回退 | 6 项契约测试 |
| 首次迁移 | 只读打开源库 + SQLite backup API，先写临时文件、`quick_check` 通过后原子替换 | 迁移/不覆盖/源缺失三类测试 |
| 不覆盖与不静默建空库 | 目标存在返回 `target-exists`；配置了来源但文件缺失直接报错且不建库 | 测试覆盖 |
| 宿主注入 | `YYS_WORKBENCH_DB_PATH=<userData>/config/ui_workbench.db`，不再依赖 cwd | 真实迁移实测 |
| 后端日志 | stdout/stderr 追加到 `userData/logs/backend.log`，启动失败提示带日志路径 | 代码与启动路径 |
| 退出回收 | `stop` 先终止并最多等待 5 秒，超时交 Job Object | 既有 `--crash` 与真实强杀 |
| 超时失败 | 端口有不响应进程时按 30 秒上限失败，不假就绪 | 新增单元测试（有界超时） |
| 偏好策略 | 首次使用浅色默认；改为深色后重启仍为深色；旧 Electron profile 不动 | 实拍 + LevelDB 哈希比对 |
| 回退工具 | `scripts/snapshot_workbench_db.py` 生成一致性快照并打印 SHA-256 | 实测 73,728 bytes，哈希与源库一致 |

## 真实迁移结果

- 源：旧 portable 库 `%TEMP%\…\resources\backend\config\ui_workbench.db`，73,728 bytes，SHA-256 `651c5c9a…86d8`。与阶段 0 快照（`052c0c3c…906c`）不同，说明旧应用在快照后仍有写入，因此迁移时重新做了只读快照，没有复用旧快照。
- 目标：`%APPDATA%\yys-script-manager\config\ui_workbench.db`，此前不存在。
- 迁移后：`quick_check=ok`，`runs=5`、`run_logs=26`，历史页实拍显示 #5–#1（地域鬼王，4 条错误 + 1 条人工接管）。
- 源库未被修改（哈希保持 `651c5c9a…86d8`）。
- 第二次启动（不带来源配置）目标库哈希保持 `8f487d78…e7ee`，未重复导入、未覆盖。

## 偏好与回退

- 首次启动为浅色；在设置页切到深色后重启仍是深色，说明只影响主题与导航折叠这两个键，且后续持久化正常。
- 旧 Electron 的 `Local Storage/leveldb` 六个文件哈希在联调前后完全一致，未被新宿主改写。
- 截图、图片覆盖、`window-state.json` 仍留在旧 userData 路径，迁移只写 `config/ui_workbench.db`。
- 回退到 Electron 不会自动读取新永久库。正确做法：运行 `scripts/snapshot_workbench_db.py` 生成快照，把快照放到旧宿主 cwd 的 `config/ui_workbench.db`（或让旧后端指向该文件）再启动；不能宣称旧 Electron 自动兼容新路径。

## 验证结果

```powershell
& C:/Users/56440/.cargo/bin/cargo.exe +1.99.1 test --manifest-path gui/src-tauri/Cargo.toml --locked --target x86_64-pc-windows-msvc --target-dir build/tauri-target
& D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend -q
& D:/ProgramData/anaconda3/envs/win_macro/python.exe tests/gui/run_tauri_smoke.py build/tauri-target/yys-desktop-smoke.exe
& D:/ProgramData/anaconda3/envs/win_macro/python.exe scripts/snapshot_workbench_db.py
```

- Rust 测试 9/9（新增超时用例）；后端测试 129/129（新增 6 项）；默认烟测通过；ruff 与 `git diff --check` 通过。
- 实拍：`build/e2e-migrated-history.png`（迁移后历史页）、`build/e2e-theme-persisted.png`（重启后深色）。

## 本轮改动

- `ui_backend/storage/workbench_db.py`（新增）：路径解析、旧库迁移与状态常量。
- `ui_backend/app.py`：按新优先级解析路径，启动时执行迁移，暴露 `app.state.db_path/migration`。
- `tests/ui_backend/test_workbench_db.py`（新增）：6 项契约测试。
- `gui/src-tauri/src/backend.rs`：注入 `YYS_WORKBENCH_DB_PATH`；后端日志落盘；`stop` 改为最多等待 5 秒；新增超时测试。
- `gui/src-tauri/src/main.rs`：启动失败提示附带后端日志路径。
- `scripts/snapshot_workbench_db.py`（新增）：回退前一致性快照工具。

## 未覆盖与后续

1. Renderer 初始化失败目前只在单元层覆盖（未就绪零请求、握手守卫），没有做端到端故障注入。
2. 迁移来源通过 `YYS_LEGACY_DB_PATH` 一次性指定；安装器/portable 自动传入来源属于阶段 4。
3. 真实 NSIS/portable 产物、体积门槛与 Runtime 矩阵仍属阶段 4–5。
