# GUI 现代化工作台总体实施计划

## 1. 实施原则

- 父任务只做需求管理、阶段编排和最终集成评审，不直接执行大范围代码修改。
- 三个子任务按 `gui-shell-theme` → `gui-run-workbench` → `gui-secondary-views` 顺序实施和验收。
- 用户审阅规划并明确要求开始实现后，只启动当前拥有下一交付物的子任务，不启动父任务。
- 不新增前端依赖或构建链；优先使用现有 DOM、CSS、JavaScript、Node `assert` 与项目测试。
- 每阶段保持应用可启动、可回滚，并保留此前已有行为的原子回归断言。

## 2. 开始前基线检查

阶段 1 开始前必须完成：

1. 重新读取 `git status --short` 和三个 GUI 文件的差异。
2. 确认当前 GUI 仍包含已归档 `08-08-universal-entry-recovery` 在提交 `6421685` 中交付的行为。
3. 验证“继续等待 3 分钟”、人工接管关联重试、暂停、恢复、停止等现有恢复动作仍在当前源码和测试中。
4. 记录当前 Node 与 UI 后端定向测试基线，不把已有失败归因于 GUI 重构。

建议基线命令：

```powershell
node --check gui/main.js
node --check gui/renderer.js
node tests/gui/test_backend_detection.js
node tests/gui/test_renderer_config.js
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_app_api.py tests/ui_backend/test_p1_workbench.py tests/ui_backend/test_run_observability.py -v
```

## 3. 阶段顺序

### 阶段 1：视觉基础与应用框架

执行 `.trellis/tasks/08-08-gui-shell-theme/implement.md`：

- 建立浅色默认双主题和语义设计令牌。
- 替换图标符号，完成可折叠导航、顶部状态栏和响应式应用骨架。
- 保持现有页面内容与运行操作可达，不提前重写运行/工作流/历史业务。
- 在 800×600、900×650、1280×720 验证主题、布局和键盘焦点。

验收后提交独立 commit，再进入阶段 2。

### 阶段 2：运行工作台

执行 `.trellis/tasks/08-08-gui-run-workbench/implement.md`：

- 改为任务列表 + 单一详情/配置面板。
- 实现空闲/运行/终态的内容优先级。
- 合并原进度页，移除固定证据右栏，接入时间线/证据/日志标签。
- 回归所有 `available_actions`，尤其是继续等待和人工接管关联重试。

验收后提交独立 commit，再进入阶段 3。

### 阶段 3：工作流、历史与设置

执行 `.trellis/tasks/08-08-gui-secondary-views/implement.md`：

- 将工作流长模态框替换为独立编辑视图和 dirty 离开保护。
- 将历史卡片替换为响应式紧凑表格与独立详情。
- 完成设置页主题入口、Toast 反馈和跨页运行状态收敛。
- 执行完整视觉、交互和契约回归。

验收后提交独立 commit，再回到父任务进行集成评审。

## 4. 父任务最终验收

### 自动检查

```powershell
node --check gui/main.js
node --check gui/renderer.js
node tests/gui/test_backend_detection.js
node tests/gui/test_renderer_config.js
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/ -v
git diff --check
```

如阶段中新增 GUI Node 测试，将它们加入上述列表；不创建空测试占位。

### 真实 Electron 视觉验收

在浅色和深色主题下分别检查 800×600、900×650、1280×720：

- 一级导航展开/折叠、顶部状态栏和主题切换。
- 空闲任务选择与配置启动。
- 运行中阶段、进度、暂停/恢复/停止及跨页返回运行。
- 等待超时、继续等待、人工接管、错误证据和关联重试。
- 工作流新建/编辑/未保存离开。
- 历史筛选、分页、详情进入/返回上下文恢复。
- 键盘导航、可见焦点、减少动效和无横向滚动。

需要真实后端或运行数据的检查使用受控测试数据；涉及真实游戏输入时仍需用户单独明确授权。

## 5. 验收映射

| 父 PRD | 主要阶段 |
| --- | --- |
| AC2、AC3a、AC3b、AC7、AC7a | 阶段 1 |
| AC1、AC1b、AC1c、AC4、AC5a、AC6 | 阶段 2 |
| AC1a、AC5、AC5b、AC5c、AC5d | 阶段 3 |
| AC3、AC8、AC9 | 三阶段 + 父任务集成评审 |

## 6. 风险与回滚点

| 风险 | 缓解 |
| --- | --- |
| 后续改版回退已归档恢复能力 | 以 `6421685` 为行为基线，逐项回归继续等待、人工接管和关联重试 |
| 视觉重排破坏运行动作 | `available_actions` 单一真源 + 恢复动作回归矩阵 |
| 800×600 信息拥挤 | 每阶段都在最小窗口验收，不把适配拖到最后 |
| 主题切换出现闪烁或状态分叉 | 页面加载前恢复主题，顶部和设置页共用一个主题函数 |
| 工作流草稿误丢失 | 独立 dirty 状态与所有离开路径测试 |
| 历史详情返回丢上下文 | 进入详情前保存筛选、页码、滚动位置并做回归检查 |
| 大范围一次性回滚困难 | 三阶段独立提交，每阶段保持可运行 |

## 7. 开始实现前检查

- [ ] 用户已审阅父任务及三个子任务的 `prd.md`、`design.md`、`implement.md`。
- [ ] 父 PRD 已完成收敛检查，无开放问题和临时 brainstorm 段落。
- [ ] 已确认当前 GUI 包含 `6421685` 的恢复行为，且工作树中的任何新差异都已单独记录。
- [ ] 用户明确要求开始实施后，先启动 `08-08-gui-shell-theme`。
- [ ] 实施前加载 `trellis-before-dev`；每阶段完成后加载 `trellis-check`。
- [ ] 当前使用 Codex inline 工作流，不需要填充子代理 JSONL 清单。
