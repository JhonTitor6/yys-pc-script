# GUI 运行工作台实施计划

## 1. 前置门槛

- [ ] `08-08-gui-shell-theme` 已通过验收并形成独立提交。
- [ ] 已确认提交 `6421685` 的阶段、继续等待、人工接管与关联重试仍在当前基线中。
- [ ] 记录现有运行页、进度页、证据栏和日志行为及定向测试结果。

## 2. 预计影响文件

- `gui/index.html`
- `gui/styles.css`
- `gui/renderer.js`
- `tests/gui/test_renderer_config.js`
- `tests/gui/` 下最小运行展示纯逻辑测试（按实际边界决定）

仅在现有 API 无法表达父 PRD 已要求的真实数据时才触及 `ui_backend`，并先回到规划更新契约。

## 3. 有序步骤

### Step 1：锁定运行展示契约

- [ ] 为 `available_actions` 到按钮可见性、空闲/运行/终态优先级写最小纯逻辑测试，注释标明父 PRD AC4 与本任务 S2-AC3/S2-AC6。
- [ ] 把 action→endpoint 保持为单一映射，覆盖 `continue_waiting` 和 `manual_takeover`。
- [ ] 记录 REST 刷新与 WebSocket snapshot 对 current run 的同源行为。

### Step 2：任务列表与单一配置面板

- [ ] 将脚本卡片内表单移动为单一详情区，任务列表只保留身份/分类/状态。
- [ ] 保留 schema 通用渲染和配置类型归一化，增加可见说明与验证反馈。
- [ ] 实现宽屏次级侧栏、窄屏抽屉及键盘焦点管理。

### Step 3：状态自适应运行现场

- [ ] 空闲时突出任务配置；启动成功后折叠任务区并突出运行现场。
- [ ] 运行中重开任务区时说明修改只影响下一次运行。
- [ ] 终态显示结果摘要、证据/错误和再次运行或历史入口。

### Step 4：合并进度与详情标签

- [ ] 把原进度页的阶段、计数、来源、快照并入运行页后再删除进度入口和重复节点。
- [ ] 移除固定右侧证据栏，首屏保留失败摘要与最新证据缩略图。
- [ ] 实现时间线/证据/日志标签，保留日志级别筛选和真实 `capture_error`。

### Step 5：恢复操作与重连回归

- [ ] 验证暂停、恢复、停止、继续等待、重试、跳过、人工接管按钮矩阵。
- [ ] 验证刷新与 WebSocket 重连恢复相同页面状态和操作权限。
- [ ] 验证顶部紧急停止与运行页停止使用同一控制路径。

## 4. 验证

```powershell
node --check gui/renderer.js
node tests/gui/test_renderer_config.js
node tests/gui/test_backend_detection.js
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_app_api.py tests/ui_backend/test_run_observability.py tests/ui_backend/test_run_manager.py tests/ui_backend/test_scheduler.py -v
git diff --check
```

真实 Electron 在 800×600、900×650、1280×720 和浅色/深色下验证 S2-AC1 至 S2-AC9。

## 5. 回滚点

- 先保留原运行 DOM 到新运行现场完成契约验证，再删除重复结构。
- 原进度页仅在信息迁移完成后删除。
- 如时间线数据不足，保留真实阶段记录的最小版本，不解析日志伪造事件。
- 不回滚阶段 1 的主题与应用框架，不覆盖恢复任务改动。
