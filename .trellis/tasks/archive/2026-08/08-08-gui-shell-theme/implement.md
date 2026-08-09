# GUI 视觉基础与应用框架实施计划

## 1. 前置门槛

- [ ] 确认当前 GUI 包含提交 `6421685` 的恢复行为，且开始实施前没有未记录的重叠差异。
- [ ] 记录 `gui/index.html`、`gui/renderer.js`、`gui/styles.css` 当前差异。
- [ ] 运行现有 GUI Node 与 UI 后端定向测试并记录基线。

## 2. 预计影响文件

- `gui/index.html`
- `gui/styles.css`
- `gui/renderer.js`
- `tests/gui/` 下最小主题/壳层状态测试（仅在现有测试无法覆盖时新增）

默认不修改 `gui/main.js`、后端与数据库；若新增 GUI 文件，必须同步 `gui/package.json` 的打包列表。

## 3. 有序步骤

### Step 1：主题纯逻辑与令牌

- [ ] 先写主题非法值归一化、默认浅色和持久化同步的最小 Node 检查，对应 S1-AC1。
- [ ] 增加加载前主题恢复和共享 `setTheme`。
- [ ] 将现有颜色收敛为浅色/深色语义令牌，清除组件内新增硬编码色。
- [ ] 加入 focus-visible、reduced-motion 和状态非颜色提示。

### Step 2：导航与图标

- [ ] 用本地 SVG symbol 替换一级导航字体符号。
- [ ] 将导航收敛为运行、工作流、历史、设置，加入文字标签和折叠控制。
- [ ] 实现 800×600 自动折叠和宽屏用户偏好恢复。
- [ ] 保持原进度内容临时可达，为阶段 2 合并预留，不提前删除功能节点。

### Step 3：顶部状态栏

- [ ] 展示当前页面、连接状态、current run 摘要和查看运行入口。
- [ ] 仅在 `available_actions` 含 `stop` 时显示紧急停止，复用同一控制函数。
- [ ] 加入顶部主题快捷按钮并与主题状态同步。

### Step 4：响应式壳层与视觉检查

- [ ] 去除固定四栏所需的永久右侧列，为后续阶段保留主工作区。
- [ ] 在 800×600、900×650、1280×720 检查导航、顶栏、旧页面内容和滚动。
- [ ] 分别检查浅色/深色、键盘焦点和减少动效。

## 4. 验证

```powershell
node --check gui/renderer.js
node --check gui/main.js
node tests/gui/test_backend_detection.js
node tests/gui/test_renderer_config.js
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_app_api.py tests/ui_backend/test_run_observability.py -v
git diff --check
```

如新增 Node 测试，加入以上命令。真实 Electron 启动后按 S1-AC1 至 S1-AC7 完成人工视觉检查。

## 5. 回滚点

- 主题逻辑与令牌可独立回滚。
- 导航/顶部壳层提交前保证旧 view 仍可切换；若失败，回滚壳层而不触碰业务渲染函数。
- 不删除恢复任务新增按钮、阶段文案或 endpoint 映射。
