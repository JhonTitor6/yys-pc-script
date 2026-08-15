# GUI游戏截图实施计划

## Dependency

- 先完成 `08-15-gui-image-resource-persistence` 的 `YYS_USER_DATA_DIR` 和资源覆盖 API；截图裁剪替换直接复用该接口。

## Order

1. 增加截图持久化服务：完整帧/裁剪图 PNG、同名 JSON、原子写入、列表、读取和显式删除。
2. 为 `RunManager` 增加只复制活动脚本缓存的无副作用路径，并把现有确定性失败证据迁移到截图服务；保留原错误码和 run 终态。
3. 在 `EventBaseScript` 增加可选识别结果观察回调；由 `RunManager` 实现三轮未知、每段一次、识别恢复重置及后台保存。
4. 增加空闲前台捕获 API和 GUI 恢复焦点 IPC；确保成功与失败均执行恢复 GUI 的 `finally`。
5. 增加截图库 API、WebSocket `screenshot_saved` 事件和运行证据关联。
6. 固定安装 `cropperjs@2.1.1`，在原生 HTML/CSS/JS 中实现预览、矩形选区、裁剪保存、资源确认替换和可访问对话框。
7. 在运行页加入独立截图按钮，在设置资源项接入“截图并替换”；自动截图只 toast/证据提示。
8. 执行 Python、Node、视觉交互和真实打包离线验证。

## Expected Files

- `win_util/event.py`
- `win_util/environment/windows.py`（仅在现有能力需要小型只读补充时）
- `yys/common/recording/session.py`（只在提取共享帧校验时）
- `ui_backend/runs/manager.py`
- `ui_backend/app.py`
- `ui_backend/screenshots.py`（单个窄服务）
- `gui/main.js`
- `gui/preload.js`
- `gui/package.json`
- `gui/package-lock.json`
- `gui/index.html`
- `gui/renderer.js`
- `gui/styles.css`
- `tests/common/test_event_screenshot_trigger.py`
- `tests/ui_backend/test_screenshot_api.py`
- `tests/ui_backend/test_run_observability.py`
- `tests/gui/test_backend_detection.js`

## Validation

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_event_screenshot_trigger.py tests/common/test_recording_session.py tests/ui_backend/test_screenshot_api.py tests/ui_backend/test_run_observability.py tests/ui_backend/test_run_manager.py -v
node --check gui/main.js
node --check gui/preload.js
node --check gui/renderer.js
node tests/gui/test_backend_detection.js
node tests/gui/test_renderer_config.js
git diff --check
```

手工/打包验收：

- 空闲截图：最小化游戏后触发，验证恢复、前台客户区截图和 GUI 回焦。
- 运行截图：记录截图前后 run 快照、焦点和输入记录，确认完全一致。
- 自动截图：离线驱动未知/未知/未知/未知/已知/未知/未知/未知序列，确认仅两张。
- 裁剪：800×600、常规 DPI 与高 DPI 各验证一次像素尺寸；断网运行打包程序确认 Cropper.js 可用。
- 重装：保留 `userData`，安装新包后验证完整帧、裁剪图和元数据可浏览。

## Risk and Rollback Points

- 不把自动截图接到 `RunGuard`，避免触发既有停机保险丝。
- 不让失败证据读取调用缓存更新或前台捕获。
- 截图删除只删除截图文件/元数据，不级联运行记录和资源覆盖。
- 现有 `config/run_evidence/` 是用户未提交数据，不移动、不删除、不纳入任务提交。
