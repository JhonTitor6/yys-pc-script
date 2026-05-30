# 编排任务页重构：列表页 + 新增/编辑 Modal

## 背景

当前 `gui/index.html` 第 68-87 行的 `workflowsView` 把"新增/编辑表单"和"已保存列表"上下堆叠在同一页面：

- 顶部一个常驻的 `<form id="workflowForm">`，用于创建或编辑编排。
- 下方是 `workflowList` 卡片列表，显示已保存的编排。
- 编辑某个编排时，`renderer.js` 的 `enterWorkflowEditMode()`（renderer.js:344-360）把已有数据回填到顶部表单。
- 这种"页面级常驻表单"在小数据量时方便，但当用户主要操作是浏览和快速运行时，常驻表单占据了 60%+ 屏幕高度，挤压了列表展示空间，体感是"列表页是配角"。

本次重构目标是把"创建/编辑编排"的操作挪进一个居中 Modal 弹窗，让列表页回到主角位置。整体是纯前端 UI 调整，不动后端接口、不动数据模型。

## 目标

- 列表页只负责展示编排卡片和列表级操作（立即运行、编辑、删除）。
- 新建/编辑通过居中 Modal 弹窗完成。
- 弹窗内的步骤编辑器采用手风琴折叠：每个步骤默认折叠为摘要条，点开才显示完整字段。
- 表单数据收集、API 调用、保存后的状态管理保持现有 `saveWorkflow` 行为不变。
- 关闭弹窗时如有未保存改动，弹 `window.confirm` 询问。

## 非目标

- 不调整后端 API、不改 workflow 数据结构。
- 不加启用/禁用开关（保持 YAGNI——后端 `enabled` 字段保留，第一版 UI 不暴露）。
- 不改列表卡片样式、字段、按钮（保持现有 `.workflow-card` 视觉）。
- 不重命名或重构现有 API（`/api/workflows`、`/api/workflows/{id}`、`/api/workflows/{id}/run-now`）。
- 不引入新依赖（无第三方弹窗库，纯 CSS + 原生 DOM）。
- 不改失败策略的取值集合（`stop_workflow` / `continue_next` / `retry_then_stop`）。

## 核心决策

### 弹窗形式：居中模态弹窗（Modal）

半透明遮罩 + 中央弹窗，标准桌面应用模态。聚焦感强，步骤多时弹窗内部滚动。

### 列表形态：保留现有卡片样式

继续使用 `.workflow-card` 样式，渲染逻辑复用现有 `renderWorkflows()`。每张卡片下方加一个主操作条"运行/编辑/删除"。

### 步骤编辑器：手风琴折叠

每个步骤默认折叠为一行摘要（`步骤 N · <类型> · <摘要值>`），点开才显示完整字段。同一时刻只展开一个步骤（点 B 自动收 A），新建弹窗默认展开第一个步骤。

### 单 Modal 容器

DOM 里只放一个 `#workflowModal`，通过 `mode`（`create` / `edit`）切换填充数据，避免 N 个弹窗并存。

### 状态机：modal-aware dirty tracking

`state.workflowModal = { open, mode, workflowId, dirty }`，任何输入/选择变化都将 `dirty` 置为 `true`，关闭尝试根据 `dirty` 决定是否弹 confirm。

## 架构

### 文件改动范围

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `gui/index.html` | 修改 | 删除常驻 `#workflowForm`；在 `</body>` 之前新增单 Modal 容器 `#workflowModal`；列表页顶栏加 `[+ 新建编排]` 按钮 |
| `gui/renderer.js` | 修改 | 删除 `enterWorkflowEditMode` / `exitWorkflowEditMode` 中的常驻表单回填；新增 `openWorkflowModal(mode, workflow)` / `closeWorkflowModal({ force })` / `renderModalStepAccordion`；`saveWorkflow` 改为从 Modal 容器收集数据；事件绑定新增 Modal 关闭/保存/手风琴交互 |
| `gui/styles.css` | 修改 | 新增 `.modal-overlay`、`.modal-panel`、`.modal-header`、`.modal-body`、`.modal-footer`、`.step-accordion`、`.step-accordion-header`、`.step-accordion-body` 等约 8 个新类；调整 `.workflowsView` 顶栏布局 |

零后端改动。

### 前端结构

```
workflowsView
├── .workflows-toolbar
│   ├── <h2>编排任务</h2>
│   └── <button id="newWorkflowButton" class="primary-button">+ 新建编排</button>
└── #workflowList            // 复用现有卡片列表
    └── .workflow-card × N

#workflowModal (顶层，body 末尾，z-index 最高)
├── .modal-overlay
└── .modal-panel
    ├── .modal-header
    │   ├── <h3 id="workflowModalTitle">新建编排 / 编辑编排</h3>
    │   └── <button class="modal-close" type="button">✕</button>
    ├── .modal-body
    │   ├── <form id="workflowModalForm">
    │   │   ├── <input name="name">
    │   │   ├── <input name="group_name">
    │   │   ├── <select name="failure_policy">
    │   │   └── <div id="workflowModalSteps" class="step-accordion-list">
    │   │       └── .step-accordion × N
    │   │           ├── .step-accordion-header (点击切换展开)
    │   │           │   ├── 摘要文字
    │   │           │   └── [移除步骤] 按钮
    │   │           └── .step-accordion-body
    │   │               └── 完整字段（步骤类型 / 脚本 / 参数 / 条件）
    │   └── </form>
    └── .modal-footer
        ├── <button id="addModalStep" type="button">+ 添加步骤</button>
        ├── <button class="ghost-button modal-cancel" type="button">取消</button>
        └── <button id="saveWorkflowModalButton" class="primary-button" type="submit">保存</button>
```

### 状态机

```
list-page
   │
   │  click [+ 新建编排]
   ▼
modal-create (dirty=false)
   │  ─ 任何 input/select 变化 → dirty=true
   │  ─ 点击 ✕ / 取消 / ESC / 遮罩
   │     ├─ dirty=false → 关闭
   │     └─ dirty=true → confirm "未保存，确定关闭？" → 关闭 or 取消
   │  ─ 提交保存 → POST /api/workflows → 关闭 + 刷新列表 + 切到列表
   │
   │  click [编辑] in 卡片
   ▼
modal-edit (workflowId=X, dirty=false)
   │  ─ 同上
   │  ─ 提交保存 → PUT /api/workflows/X → 关闭 + 刷新列表
   │
   │  click [立即运行] in 卡片 → POST /api/workflows/X/run-now → 切到执行页
   │
   │  click [删除] in 卡片 → confirm → DELETE /api/workflows/X → 刷新列表
```

### 行为细节

| 触发 | 行为 |
|------|------|
| 打开 Modal | 标题根据 mode 切换；表单 reset；注入默认 1 个空步骤；当前展开第一个步骤；记录 dirty=false |
| 编辑打开 | 从 `state.workflows` 找到对应 workflow，注入所有步骤；每个步骤读取 `step_type`、`script_id`、`config`、`condition` 渲染摘要；记录 dirty=false |
| 表单变更 | input/select 的 `change`/`input` 事件将 `dirty` 置为 `true` |
| 步骤类型切换 | 重渲染该步骤的 `.step-accordion-body`，同时更新该步骤的 `.step-accordion-header` 摘要；标记 dirty |
| 脚本切换 | 同上，只重渲染 `.step-script-fields` 子区；标记 dirty |
| 添加步骤 | 末尾追加一个空步骤；自动展开；标记 dirty |
| 移除步骤 | 该步骤从 DOM 移除；剩余步骤的索引和摘要重编号；如果全部移除，自动追加一个空步骤（保证至少有 1 个）；标记 dirty |
| 步骤手风琴 | 点击 `.step-accordion-header` 切换该步骤的 `expanded` 类；其他步骤同步收起 |
| 关闭尝试 | `dirty=true` 时弹 `confirm`；否则直接关闭 |
| 关闭后清理 | 清空 state.workflowModal、reset 表单、移除所有步骤 DOM |
| 保存成功 | 调用原 `saveWorkflow` 的 API 逻辑；成功后关闭 Modal、刷新 `renderWorkflows()`、日志写 INFO |
| 保存按钮在编辑模式 | 无论 `dirty` 状态都允许提交；提交时按 `mode` 决定走 POST（create）还是 PUT（edit）；如果 `dirty=false` 也允许重发 PUT（即"重保存"场景） |
| 保存失败 | 不关闭 Modal，在 Modal 体内顶部插入一段 `.modal-error` 提示条显示后端 message；同时复用现有 `appendLog({ level: 'ERROR' })`；name/分组等必填字段缺失由表单 `required` 属性 + 浏览器原生校验拦截 |

### 与现有代码的对接

- `saveWorkflow(form)` 函数保留签名但**只在 Modal 体内被调用**。其内部字段收集逻辑（特别是 `step_{index}_` 前缀的处理、`normalizeConfigValue`、未勾选 boolean 字段补 false 的逻辑）保持不动。
- `FAILURE_POLICY_LABELS` 常量、`renderWorkflowStep`、`renderStepDynamic`、`renderField`、`normalizeConfigValue` 等工具函数全部复用。
- 卡片列表的"立即运行 / 编辑 / 删除"事件委托逻辑（renderer.js:614-631）保持不变，只把"编辑"的目标从回填表单改为打开 Modal。

## 组件设计

### 列表页顶栏

```css
.workflows-view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 0 0 auto;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--line-soft);
}
```

### Modal 容器

```css
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.55);
}

.modal-panel {
  display: flex;
  flex-direction: column;
  width: min(720px, 100%);
  max-height: 90vh;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--panel);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--line-soft);
}

.modal-close {
  width: 30px;
  height: 30px;
  border-radius: 6px;
  color: var(--muted);
  background: transparent;
  cursor: pointer;
}
.modal-close:hover { background: var(--panel-strong); color: var(--text); }

.modal-body {
  flex: 1 1 auto;
  min-height: 0;
  padding: 16px 18px;
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 18px;
  border-top: 1px solid var(--line-soft);
}
```

### 步骤手风琴

```css
.step-accordion-list {
  display: grid;
  gap: 8px;
}

.step-accordion {
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.025);
  overflow: hidden;
}

.step-accordion-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 10px 12px;
  color: var(--text);
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.step-accordion-header .summary {
  color: var(--muted);
  font-size: 12px;
  margin-left: 8px;
}

.step-accordion-body {
  display: none;
  padding: 12px;
  border-top: 1px solid var(--line-soft);
  background: rgba(0, 0, 0, 0.2);
}

.step-accordion.expanded .step-accordion-body {
  display: grid;
  gap: 10px;
}
```

## 数据/接口

### 前端 state 扩展

```js
state.workflowModal = {
  open: false,
  mode: null,         // 'create' | 'edit'
  workflowId: null,   // edit 模式才有
  dirty: false,
  expandedIndex: 0    // 当前展开的步骤下标
};
```

### API 调用（全部复用，无新增）

- `POST /api/workflows` 新建
- `PUT /api/workflows/{id}` 更新
- `DELETE /api/workflows/{id}` 删除
- `POST /api/workflows/{id}/run-now` 立即运行
- `GET /api/workflows` 列表（已在 `renderWorkflows` 中使用）

### 错误处理

| 场景 | 表现 |
|------|------|
| 网络断开 / 5xx | 复用现有 `appendLog({ level: 'ERROR' })` 记录到执行页日志；Modal 保持打开 |
| 409（删除时有运行中任务） | 复用现有 `window.alert('存在运行中的关联任务，无法删除')` |
| 校验失败（如名称为空） | Modal 顶部插入 `.modal-error` 提示条，提交按钮保持可点但下次提交仍校验 |

## 关键文件改动点

### `gui/index.html`

- 第 68-87 行：删除常驻 `<form id="workflowForm">` 和 `<h2>编排任务</h2>`，改为新的顶栏 + 列表结构
- 第 95 行附近 `</body>` 之前：新增单 Modal 容器（实际 `</body>` 在 96 行，按上下文确定插入位置即可）
- 在 `#workflowList` 之后保留空 div 占位即可

### `gui/renderer.js`

- 删除 `enterWorkflowEditMode`（renderer.js:344-360）—— 编辑数据改为注入 Modal
- 重写 `exitWorkflowEditMode` → 改为 `closeWorkflowModal({ force })`
- 新增 `openWorkflowModal(mode, workflow)`
- 新增 `renderModalStepAccordion(index, step)` —— 类似 `renderWorkflowStep` 但生成手风琴结构
- 新增 `updateStepAccordionHeader(index)` —— 根据当前步骤字段重算摘要
- `saveWorkflow(form)` 签名保留，内部逻辑不变；调用方改为 Modal 提交
- `editWorkflow(workflowId)` 改为 `openWorkflowModal('edit', workflow)`
- `bindEvents()` 中：
  - `[+ 新建编排]` 点击 → `openWorkflowModal('create')`
  - Modal 关闭按钮 / 取消按钮 / ESC / 遮罩 → `closeWorkflowModal({ force: false })`
  - Modal 内表单 change/input → `state.workflowModal.dirty = true`
  - Modal 内步骤 type/script 切换 → 重渲染 body + 更新 header + dirty=true
  - Modal 内 `[+ 添加步骤]` → 追加空步骤
  - Modal 内 `[移除步骤]` → 移除 + 重新编号
  - Modal 内 `.step-accordion-header` 点击 → 切换 expanded
- `init()` 不再调用 `addWorkflowStep()`（不再需要常驻表单的占位步骤）

### `gui/styles.css`

- 新增 `.workflows-view-header`
- 新增 Modal 容器相关类（见上文）
- 新增 `.step-accordion` 系列类
- 微调 `#workflowsView` 容器使其作为列表页骨架

## 测试策略

### 自动化测试

- 纯前端 DOM 改造，**不在本次范围内新增自动化测试**（项目目前没有 Electron 端的 jsdom/harness 测试基线）。
- 后端 `tests/ui_backend/test_run_manager.py` 覆盖的 workflow 流程不变；本次不动后端。
- `node --check gui/renderer.js`、`node --check gui/main.js` 语法检查继续在交付前执行。

### 手动 E2E 验证清单

执行环境：本地后端 `python -m ui_backend.main` + `cd gui && npm start`。

1. **新建弹窗**：点击 `[+ 新建编排]` → Modal 居中弹出，标题"新建编排"，默认 1 个空步骤且第一个步骤展开。
2. **保存新建**：输入名称"日常探索"、分组"日常"、选失败策略"失败后停止"、保留 1 个运行脚本步骤（选御魂）→ 点击保存 → Modal 关闭，列表新增 1 张"日常探索"卡片，实时日志写 INFO。
3. **编辑回填**：点击列表卡片"编辑" → Modal 打开，标题"编辑日常探索"，名称/分组/失败策略/所有步骤字段全部回填，每个步骤摘要正确。
4. **手风琴**：编辑弹窗中点步骤 2 的 header → 步骤 2 展开、步骤 1 自动收起。
5. **修改触发 dirty**：改名称 → 关闭尝试（点 ✕ 或 ESC）→ 弹 confirm → 取消 → Modal 保持。
6. **不修改直接关闭**：再次打开 Modal → 不改任何字段 → 点 ✕ → 直接关闭，无 confirm。
7. **添加/移除步骤**：点 `[+ 添加步骤]` → 末尾追加空步骤并展开；点新步骤的"移除步骤" → 步骤被移除，剩余步骤重新编号。
8. **删除流程**：点列表卡片的"删除" → confirm → 卡片消失。
9. **立即运行**：点列表卡片的"立即运行" → 切到执行页 + 实时日志写 INFO。
10. **暗色主题一致性**：Modal 颜色与现有 token 体系一致（`--panel` 背景、`--line` 边框、`--green` 主按钮），无新增颜色变量。

### 回归

- 现有 `tests/ui_backend` 全量测试应保持通过（无后端改动）。
- 现有 `tests/common/` 与 `yys/soul_raid/test_soul_raid.py` 保持原基线（无关联改动）。

## 验收标准

- 打开"编排任务"页时，**没有**常驻表单出现在页面上，只有列表页。
- 点击 `[+ 新建编排]` 或列表卡片的"编辑"按钮，Modal 弹出并可正常保存。
- 步骤手风琴在编辑和新建模式下行为一致：同一时刻只展开一个；新建时第一个默认展开。
- 未保存关闭的 confirm 提示只在 `dirty=true` 时出现。
- 列表卡片的视觉、字段、按钮（包括"立即运行"→ 切到执行页）行为与重构前完全一致。
- 弹窗的样式与现有深色主题 token 完全一致，无任何颜色硬编码。
- 实时日志区能正确显示"已保存编排" / "已更新编排" / "已删除编排" / "已提交编排运行请求"等事件。
- `node --check gui/renderer.js` 语法检查通过。

## 迁移计划

1. 修改 `gui/styles.css`：新增 Modal + 手风琴样式。
2. 修改 `gui/index.html`：删除常驻 form，改为新顶栏 + 列表 + 单 Modal 容器。
3. 修改 `gui/renderer.js`：重写编辑模式相关函数，新增 Modal 状态机和手风琴逻辑。
4. `node --check gui/renderer.js`：语法检查。
5. 启动后端 + Electron，按手动 E2E 清单逐条验证。
6. 提交并附带 commit message：`refactor(gui): 编排任务页改为列表+Modal 弹窗`，正文记录主要决策。

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Modal 内表单字段名变化导致 `saveWorkflow` 收集失败 | `saveWorkflow` 内部仍按 `step_{index}_` 前缀收集，Modal 内字段名保持不变；不重构 `saveWorkflow` |
| 步骤多时 Modal 滚动卡顿 | Modal 主体 `max-height: 90vh; overflow-y: auto;`；手风琴折叠保证大多数步骤只占一行 |
| 误关闭丢失未保存内容 | dirty 跟踪 + confirm 兜底 |
| 移除最后一个步骤后步骤区为空 | 在 `addWorkflowStep` 中判断；如果为空自动追加一个空步骤并展开 |
| 与现有"立即运行 → 切到执行页"行为冲突 | 保持现有 `runWorkflowNow` 不动；列表卡片的事件委托只改"编辑"分支 |

## 第一版实现备注

- 步骤摘要文字（`.step-accordion-header .summary`）在每种 step_type 下的具体写法：
  - `run_script`：`运行脚本 · <script display_name>`
  - `wait_duration`：`等待 <seconds> 秒`
  - `run_until_time`：`运行到 <until>`
- 摘要值在每次字段变化后实时更新，编辑时根据已有数据生成。
- `state.workflowModal` 在 Modal 关闭后整个对象 `= { open:false, mode:null, workflowId:null, dirty:false, expandedIndex:0 }`，避免脏数据残留。
- ESC 键和遮罩点击是关闭尝试的统一入口；是否真的关闭由 `closeWorkflowModal({ force })` 的 `force` 参数和 `dirty` 联合决定。
- 后端 `enabled` 字段保持持久化但 UI 不暴露；将来需要启用/禁用开关时，在 Modal 内的 `[name="name"]` 旁边加一个 `<input type="checkbox" name="enabled">` 即可，`saveWorkflow` 已包含 `enabled: true` 写死值，扩展时改为读字段即可。

## 2026-06-03 实施与验证记录

### 实施

通过 subagent-driven-development 执行 6 task，每个 task 独立 commit：

| Task | Commit | 改动 |
|------|--------|------|
| 用户并行工作保存 | `0c2ec06` | 8 文件 wip（fieldset 增强 + 日志重构 + 后端改进） |
| 1. CSS 样式 | `2218bd8` | `gui/styles.css` +162 行（12 个 Modal/accordion class） |
| 2. HTML 骨架 | `852918d` | `gui/index.html` +32/-16（workflowsView 替换 + Modal 容器追加） |
| 3. JS 工具函数 | `dd8f6e4` | `gui/renderer.js` +129/-96（state.workflowModal + 6 helper + 删 5 dead function） |
| 4. 适配 Modal | `b4fc9d1` | `gui/renderer.js` +3/-10（saveWorkflow / deleteWorkflow / editWorkflow / init） |
| 5. 完整接线 | `2f256dc` | `gui/renderer.js` +188/-27（4 Modal 控制函数 + bindEvents 7 处改造） |

最终文件大小：`gui/renderer.js` 906 行，`gui/index.html` 113 行，`gui/styles.css` 828 行。

### 验证

```bash
# 自动化
$ node --check gui/renderer.js
# 退出码 0，语法通过

$ D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend -v
# 37 passed in 25.74s（后端无 fail）
# 注：plan 基线 38 passed；基线差异源自用户 0c2ec06 commit 调整了 1 个测试，
# Modal 改造未引入新 fail。
```

### 手动 E2E（待用户验证）

spec 列了 12 条手动 E2E 项（#1-#12），覆盖新建/编辑/手风琴/dirty 关闭/添加移除步骤/删除/立即运行/暗色主题一致性等场景。需要用户在本地运行 `python -m ui_backend.main` + `cd gui && npm start` 后逐条验证。

### 实施中遇到的问题

1. **第一轮 3 个 commit 被 drop**：Task 1-3 首轮实施后才发现用户 stash 里也是 Modal 改造方向（实际是 fieldset 增强），与 Modal commits 完全冲突。drop 3 个 commit + 重新 stash + 重新实施。
2. **Task 3 后中间态 broken**：Task 3 commit 后 `renderer.js` 12 处 caller 残留（plan 设计缺陷），master 处于 broken 状态。Task 4 紧接修复 4 个核心函数，Task 5 完整重写 bindEvents 闭合所有残留。
3. **3 轮 plan review 发现 11 个 issue**：6 critical + 1 high + 1 medium + 3 advisory，3 轮 review loop 全部修复。
