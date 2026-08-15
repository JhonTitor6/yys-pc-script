# GUI 工作流、历史与设置实施计划

## 1. 前置门槛

- [ ] `08-08-gui-shell-theme` 与 `08-08-gui-run-workbench` 已验收并各自提交。
- [ ] 记录工作流 CRUD/调度、历史分页/详情、manual retry、设置主题的当前测试基线。
- [ ] 确认前两阶段在三个目标窗口尺寸和双主题下没有阻塞性布局问题。

## 2. 预计影响文件

- `gui/index.html`
- `gui/styles.css`
- `gui/renderer.js`
- `tests/gui/` 下最小工作流 dirty/历史上下文/主题同步纯逻辑测试
- 仅在筛选契约确实缺失时影响 `ui_backend/app.py`、repositories 与对应测试

## 3. 有序步骤

### Step 1：工作流子视图与 dirty 契约

- [ ] 先写 dirty 离开守卫的纯逻辑测试，覆盖返回、一级导航、取消离开、保存成功。
- [ ] 把 modal 内表单迁移到主工作区 editor 子视图，复用步骤渲染和保存逻辑。
- [ ] 保存期间禁用重复提交；失败保留草稿和展开状态。
- [ ] 验证立即运行、启用/停用、删除和所有失败策略字段。

### Step 2：历史表格与筛选

- [ ] 将卡片列表替换为语义表格/响应式行，保留现有状态过滤和分页。
- [ ] 接入任务和时间筛选；先复用现有接口，若跨页准确筛选必须扩展 API，则先补后端契约测试。
- [ ] 实现窄屏两行摘要和键盘可进入的行操作。

### Step 3：历史独立详情

- [ ] 进入详情前保存筛选、页码和滚动位置，返回后恢复。
- [ ] 按运行摘要、配置、步骤时间线、证据、日志组织详情，遮蔽敏感配置。
- [ ] 保留 manual 关联重试并验证新 run 与原 run 的关系。

### Step 4：设置与反馈

- [ ] 设置页增加外观主题选择并复用共享主题函数。
- [ ] 只展示真实有效的连接/应用信息，不增加空壳设置。
- [ ] 建立单一可访问 Toast 容器，替换零散 alert/仅日志反馈中适合短提示的部分；危险确认仍保留确认对话。
- [ ] 确认不新增通知抽屉。

### Step 5：父任务整体验收

- [ ] 回归运行、工作流、历史、设置四页和顶部状态栏。
- [ ] 验证浅色/深色与三个目标窗口尺寸。
- [ ] 验证键盘、焦点、减少动效、无横向滚动和危险操作确认。
- [ ] 运行完整 GUI Node 与 UI 后端测试，记录任何既有失败。

## 4. 验证

```powershell
node --check gui/renderer.js
node --check gui/main.js
node tests/gui/test_backend_detection.js
node tests/gui/test_renderer_config.js
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/ -v
git diff --check
```

如新增 Node 或后端筛选测试，加入以上命令。真实 Electron 按 S3-AC1 至 S3-AC9 和父 PRD AC1-AC9 验收。

## 5. 回滚点

- 新工作流 editor 通过保存与 dirty 验证前不删除旧 modal 路径。
- 新历史表格/详情完成上下文恢复前不删除旧列表展示。
- 如筛选 API 扩展失败，回滚扩展并明确保留现有可验证筛选范围，不在前端伪装全量筛选。
- 不回滚阶段 1/2 或当前工作树中无关改动。
