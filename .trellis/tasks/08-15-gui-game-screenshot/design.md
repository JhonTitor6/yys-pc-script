# GUI游戏截图技术设计

## 1. Design Decisions

- 截图数据以 `<userData>/screenshots` 下的 PNG 和同名 JSON 元数据为持久化真源；运行证据表只保存关联，避免为了重装保留而迁移整个工作台数据库。
- 空闲截图复用 `WindowsEnvironment(capture_mode="foreground")`；运行中截图只复制脚本缓存。
- 自动连续未知检测复用 `EventBaseScript` 已有每轮 `triggered_event` 结果，但不启用 `RunGuard` 的停机语义。
- 裁剪使用本地固定版本 `cropperjs@2.1.1`（MIT），不增加前端构建器、不使用 CDN。
- 完整帧先持久化再打开裁剪器；取消裁剪也保留调试现场。

## 2. Persistent Model

```text
<userData>/screenshots/YYYY-MM-DD/
├── <screenshot-id>.png
└── <screenshot-id>.json
```

元数据最小字段：

```json
{
  "id": "稳定随机 ID",
  "created_at": "ISO-8601",
  "kind": "full|crop",
  "trigger": "manual|unknown_scene|script_error|entry_error|stop_timeout",
  "width": 1136,
  "height": 640,
  "source_id": null,
  "run_id": null,
  "script_id": null,
  "stage": null
}
```

- 图片和 JSON 都使用临时文件加 `os.replace()` 写入。
- 列表通过扫描 JSON 得出，当前规模采用线性扫描；若未来真实数据量造成可测延迟，再增加索引。
- 删除明确截图时删除 PNG/JSON；运行证据行保留并显示文件不可用。资源覆盖保存的是独立重编码副本，不引用截图文件。

## 3. Capture Paths

### 3.1 Idle manual capture

1. 后端确认没有活动 run。
2. 创建前台模式 `WindowsEnvironment`，恢复并激活游戏窗口。
3. 有界等待约 0.5 秒，`capture_screen()` 再次验证前台句柄并仅抓客户区。
4. 验证尺寸、非空和标准差不低于现有录制首帧契约。
5. 永久保存完整 PNG。
6. Renderer 在 `finally` 中通过 preload IPC 请求主进程恢复并聚焦 GUI。

### 3.2 Running manual/automatic capture

- `RunManager` 根据当前 run 取得脚本，读取 `image_finder.screenshot_cache` 局部引用并立即 `.copy()`。
- 不调用 `update_screenshot_cache()`、`capture_screenshot()` 或任何环境捕获方法。
- 缓存为 `None`、空数组、尺寸无效或近似纯色时返回失败；绝不回退到前台或桌面捕获。
- 复制完成后才进行 PNG 编码和磁盘写入，脚本持有的数组不传给 GUI、不被裁剪修改。

## 4. Automatic Triggers

### 4.1 Deterministic errors

把现有启动失败、入口失败、脚本异常、停止超时统一改为调用截图服务，并把 `_read_script_screenshot()` 拆成“只复制缓存”的无副作用函数。失败仍写 `capture_error`，不制造伪成功记录。

### 4.2 Consecutive unknown scene

- `EventBaseScript` 增加可选识别结果观察回调；每轮在 `triggered_event` 产生后报告布尔值。
- `RunManager` 为活动脚本安装闭包，维护 `consecutive_unknown` 和 `captured_for_episode`。
- 已识别：计数归零并重新布防。
- 未识别：递增；恰好到 3 且本轮未保存时复制缓存并异步持久化一次；后续未知不重复。
- 回调不改变 stop/pause 状态，不调用 `RunGuard.note_iteration()`，也不申请动作预算。
- 缓存复制在脚本线程内完成以固定当时画面；PNG 编码、写盘和证据发布在独立后台任务中完成，避免阻塞识别循环。

## 5. Backend API and Events

- `POST /api/screenshots/capture`：手动捕获并返回完整帧元数据。
- `GET /api/screenshots`：列出永久截图。
- `GET /api/screenshots/{id}/content`：返回 PNG。
- `POST /api/screenshots/{id}/crops`：接收 Cropper.js 输出的 PNG 二进制，校验并保存裁剪图。
- `DELETE /api/screenshots/{id}`：删除明确截图。

自动或手动保存成功后发布 `screenshot_saved` WebSocket 事件；关联 run 时同时追加现有 `run_evidence` 并发布规范化 run 快照。截图 API 继续受 UI token 保护，不接受客户端绝对路径。

## 6. GUI and Cropper

- 运行页提供始终可用的“截图”工具按钮，它不属于 `available_actions`。
- 设置页资源条目提供“截图并替换”，把资源 ID 绑定到本次裁剪会话。
- 手动捕获成功后打开可关闭对话框，显示完整帧和 Cropper.js 矩形选区；对话框支持 Esc、明确焦点、键盘操作与 800×600 可滚动布局。
- 使用 Cropper.js 的 canvas 输出生成原图像素裁剪 Blob，不自行维护预览缩放比例公式。
- 全局入口只显示“保存裁剪图”；资源入口额外显示“替换当前资源”，确认后把同一 Blob 发给资源覆盖 API。
- 自动事件只显示 toast 并更新证据页提示，不自动切页或打开对话框。

## 7. Validation and Compatibility

- 复用 `RecordingSession._validate_first_frame()` 的近似纯色判定逻辑；若直接调用会形成不合适依赖，则提取一个最小共享校验函数并保持录制行为不变。
- Cropper.js 加入 `gui/package.json` 的固定生产依赖，并确认 electron-builder 打包离线资源。
- 现有运行控制仍只服从 `available_actions`；截图不改变状态机、日志推断或恢复动作权限。
- 截图元数据通过 run ID 关联现有日志/快照，不复制日志包。

## 8. Risks and Rollback

- 风险：自动证据保存阻塞脚本。防护：脚本线程只复制数组，编码/写盘在后台。
- 风险：自动回调在 run 结束后落盘。防护：保存使用稳定 run ID，结束后仍可追加证据；发布前重新读取 run，不改终态。
- 风险：前台截图意外抓桌面。防护：激活后验证 `GetForegroundWindow()`，只按客户区屏幕坐标抓取。
- 回滚：移除截图 API/观察回调后，现有运行证据与事件循环恢复原行为；永久截图文件保持可手工读取。
