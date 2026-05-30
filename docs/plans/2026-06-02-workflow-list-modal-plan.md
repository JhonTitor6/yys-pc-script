# 编排任务页重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `gui/workflowsView` 从"常驻表单 + 列表"重构为"列表页 + 居中 Modal 弹窗"；步骤编辑器改为手风琴折叠；零后端改动。

**Architecture:** 单 Modal 容器（`#workflowModal`）+ `state.workflowModal` 状态机（mode/dirty/expandedIndex）；CSS 增量追加 8 个新类，HTML 删除常驻 form、改顶栏、加 Modal 骨架；JS 拆出 `openWorkflowModal` / `closeWorkflowModal` / `renderModalStepAccordion` / `updateStepAccordionHeader` 四个工具函数，复用现有 `saveWorkflow` 的字段收集与 API 调用。

**Tech Stack:** 原生 HTML/CSS/JavaScript（无构建）、FastAPI 后端无改动、Electron 壳无改动、pytest 回归。

---

## 设计来源

- 设计规格：`docs/specs/2026-06-02-workflow-list-modal-design.md`
- 现有实现：`gui/index.html`（97 行）、`gui/renderer.js`（720 行）、`gui/styles.css`（667 行）
- 现有 API：`ui_backend/app.py` 中 `GET/POST /api/workflows`、`PUT/DELETE /api/workflows/{id}`、`POST /api/workflows/{id}/run-now`

## 文件结构

修改现有文件：

```text
gui/styles.css         # 追加 8 个新 CSS 类（不删除任何现有类）
gui/index.html         # 删除 #workflowForm，追加 .workflows-view-header 顶栏与 #workflowModal 容器
gui/renderer.js        # 替换 enterWorkflowEditMode/exitWorkflowEditMode，新增 4 个工具函数
```

零后端改动，零新增文件，零新增依赖。

### 改动范围核对

| 区域 | 现状（保留） | 改动 |
|------|------------|------|
| `#workflowList` 渲染 | `renderWorkflows()` | 不动 |
| 列表卡片"立即运行/编辑/删除"事件委托 | `renderer.js:614-631` | 仅"编辑"分支改为 `openWorkflowModal('edit', ...)` |
| 失败策略/字段渲染 | `FAILURE_POLICY_LABELS`、`renderField`、`renderStepDynamic`、`renderWorkflowStep` | 全部复用 |
| `saveWorkflow(form)` 字段收集 + API 调用 | `renderer.js:271-341` | 函数签名与内部逻辑保留；调用方改为 Modal 提交 |
| `addWorkflowStep` / `deleteWorkflow` / `runWorkflowNow` | `renderer.js:264-268 / 403-419 / 429-434` | 不动 |
| `init()` 启动流程 | `renderer.js:708-719` | 移除 `addWorkflowStep()` 默认步骤占位调用 |

---

## Task 1: 追加 Modal 与手风琴的 CSS 样式

**Files:**
- Modify: `gui/styles.css`（在第 666 行 `@media` 之前追加新样式块）

- [ ] **Step 1: 打开 `gui/styles.css`**

定位到第 665 行（`.workflow-actions` 块结束的空行）之后、第 666 行 `@media (max-width: 960px)` 之前。

- [ ] **Step 2: 追加新样式块**

在 `.workflow-actions` 块之后（`margin-top: 8px;` 行的下一个空行）插入以下 CSS。**严格使用现有 token（`--panel` / `--line` / `--green` 等），不引入新颜色变量**：

```css
/* 编排任务列表页顶栏：标题 + 新建按钮 */
.workflows-view-header {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--line-soft);
}

.workflows-view-header h2 {
  margin: 0;
}

/* 居中 Modal 容器 */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.55);
}

.modal-overlay[hidden] {
  display: none;
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
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--line-soft);
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
}

.modal-close {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 6px;
  color: var(--muted);
  background: transparent;
  cursor: pointer;
  font-size: 16px;
}

.modal-close:hover {
  color: var(--text);
  background: var(--panel-strong);
}

.modal-body {
  flex: 1 1 auto;
  min-height: 0;
  padding: 16px 18px;
  overflow-y: auto;
}

.modal-body form {
  display: grid;
  gap: 12px;
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

.modal-footer .spacer {
  flex: 1 1 auto;
}

/* Modal 内的错误提示条 */
.modal-error {
  padding: 8px 12px;
  border: 1px solid #6e3535;
  border-radius: 6px;
  color: #ffb8b8;
  background: #2a1818;
  font-size: 13px;
}

/* 步骤手风琴 */
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
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 10px 12px;
  border: 0;
  color: var(--text);
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.step-accordion-header .summary {
  margin-left: 10px;
  color: var(--muted);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1 1 auto;
}

.step-accordion-header .remove-step {
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

- [ ] **Step 3: 验证 CSS 不破坏现有布局**

```bash
cd "F:/Users/56440/PythonProjects/yys-pc-script" && node --check gui/renderer.js
```

预期：退出码 0（renderer.js 没改，语法应通过）。如果报错，**撤销本次 CSS 修改**（CSS 不应影响 JS 语法检查；如果 JS 报错说明动了别处）。

- [ ] **Step 4: Commit**

```bash
cd "F:/Users/56440/PythonProjects/yys-pc-script" && \
  git add gui/styles.css && \
  git commit -m "feat(gui): 追加 Modal 弹窗与步骤手风琴的 CSS 样式

- 新增 .workflows-view-header / .modal-overlay / .modal-panel / .modal-header
  / .modal-body / .modal-footer / .modal-close / .modal-error
- 新增 .step-accordion / .step-accordion-header / .step-accordion-body
- 全部使用现有 token，无新增颜色变量
- 不动现有样式

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: 重构 workflowsView 的 HTML 骨架

**Files:**
- Modify: `gui/index.html`（替换第 68-87 行的 `<section id="workflowsView">` 整个块；并在第 95 行 `<script>` 之前追加 Modal 容器）

- [ ] **Step 1: 替换 workflowsView 整个 section**

在 `gui/index.html` 中，将第 68-87 行的：

```html
      <section id="workflowsView" class="view">
        <h2>编排任务</h2>
        <form id="workflowForm" class="workflow-editor">
          <input type="hidden" name="workflow_id" value="">
          <label><span>名称</span><input name="name" value="日常探索突破"></label>
          <label><span>分组</span><input name="group_name" value="日常"></label>
          <label><span>失败策略</span>
            <select name="failure_policy">
              <option value="stop_workflow">失败后停止</option>
              <option value="continue_next">失败后继续</option>
              <option value="retry_then_stop">重试后停止</option>
            </select>
          </label>
          <div id="workflowSteps" class="workflow-steps"></div>
          <button type="button" id="addWorkflowStep" class="ghost-button">添加步骤</button>
          <button type="submit" id="saveWorkflowButton" class="primary-button">保存编排</button>
          <button type="button" id="cancelEditButton" class="ghost-button" hidden>取消编辑</button>
        </form>
        <div id="workflowList" class="workflow-list"></div>
      </section>
```

整段替换为：

```html
      <section id="workflowsView" class="view">
        <header class="workflows-view-header">
          <h2>编排任务</h2>
          <button id="newWorkflowButton" type="button" class="primary-button">+ 新建编排</button>
        </header>
        <div id="workflowList" class="workflow-list"></div>
      </section>
```

- [ ] **Step 2: 追加 Modal 容器**

在 `gui/index.html` 第 95 行（`<script src="./renderer.js"></script>`）之前，追加以下 Modal 骨架。**注意 id 命名必须与 JS 一致**（`#workflowModal` / `#workflowModalTitle` / `#workflowModalForm` / `#workflowModalSteps` / `#addModalStep` / `#saveWorkflowModalButton` / `#closeWorkflowModalButton` / `#cancelWorkflowModalButton`）：

```html
  <div id="workflowModal" class="modal-overlay" hidden>
    <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="workflowModalTitle">
      <div class="modal-header">
        <h3 id="workflowModalTitle">新建编排</h3>
        <button id="closeWorkflowModalButton" type="button" class="modal-close" aria-label="关闭">✕</button>
      </div>
      <div class="modal-body">
        <form id="workflowModalForm" class="workflow-editor">
          <input type="hidden" name="workflow_id" value="">
          <label><span>名称</span><input name="name" required></label>
          <label><span>分组</span><input name="group_name"></label>
          <label><span>失败策略</span>
            <select name="failure_policy">
              <option value="stop_workflow">失败后停止</option>
              <option value="continue_next">失败后继续</option>
              <option value="retry_then_stop">重试后停止</option>
            </select>
          </label>
          <div id="workflowModalSteps" class="step-accordion-list"></div>
        </form>
      </div>
      <div class="modal-footer">
        <button id="addModalStep" type="button" class="ghost-button">+ 添加步骤</button>
        <span class="spacer"></span>
        <button id="cancelWorkflowModalButton" type="button" class="ghost-button">取消</button>
        <button id="saveWorkflowModalButton" type="submit" class="primary-button" form="workflowModalForm">保存</button>
      </div>
    </div>
  </div>
```

- [ ] **Step 3: 验证 HTML 语法**

```bash
cd "F:/Users/56440/PythonProjects/yys-pc-script" && \
  node -e "
    const html = require('fs').readFileSync('gui/index.html', 'utf8');
    const opens = (html.match(/<(?!\!|br|hr|img|input|meta|link)([a-zA-Z][a-zA-Z0-9]*)/g) || []).length;
    const closes = (html.match(/<\/[a-zA-Z][a-zA-Z0-9]*>/g) || []).length;
    console.log('open tags:', opens, 'close tags:', closes);
    if (opens !== closes + 1) { process.exit(1); }  // 容忍 1 个自闭合不匹配
  "
```

预期：打印 `open tags: NN close tags: NN`，退出码 0。

- [ ] **Step 4: Commit**

```bash
cd "F:/Users/56440/PythonProjects/yys-pc-script" && \
  git add gui/index.html && \
  git commit -m "refactor(gui): 编排任务页改为列表+新建按钮+Modal 容器

- workflowsView 删除常驻 form 与标题改为顶栏 [标题 + +新建按钮]
- body 末尾追加 #workflowModal 容器（含表单、步骤区、错误条、底部按钮）
- 原 form id 全部移除：#workflowForm/#workflowSteps/#addWorkflowStep
  /#saveWorkflowButton/#cancelEditButton
- 新增 id 与 JS 工具函数一一对应：#workflowModal / #workflowModalTitle
  /#workflowModalForm / #workflowModalSteps / #addModalStep
  /#saveWorkflowModalButton / #closeWorkflowModalButton
  /#cancelWorkflowModalButton / #newWorkflowButton

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: 在 renderer.js 增加 state.workflowModal 与 4 个工具函数

**Files:**
- Modify: `gui/renderer.js`（state 区域新增 modal 字段；删除 `enterWorkflowEditMode` 整段；新增 4 个工具函数）

- [ ] **Step 1: 扩展 state**

在 `gui/renderer.js` 第 5-13 行的 `const state = { ... }` 中找到 `editingWorkflowId: null,` 这一行（**当前存在**），在其后插入：

```js
  workflowModal: {
    open: false,
    mode: null,          // 'create' | 'edit'
    workflowId: null,    // edit 模式才有
    dirty: false,
    expandedIndex: 0
  },
```

不要删除原有的 `editingWorkflowId: null,`——保留以避免破坏未提交到 master 的其他 worktree 分支（本任务范围内不引用它，但删它属于无关改动，遵循 CLAUDE.md "只改必须改的"）。

- [ ] **Step 2: 删除 enterWorkflowEditMode 整段**

删除 `gui/renderer.js` 第 344-360 行（`enterWorkflowEditMode` 函数整体）。**这是 spec 要求的：编辑改为打开 Modal**。删除前用 Read 工具确认起始行（`// 进入编辑模式：把已有编排数据回填到表单`）和结束行（`state.editingWorkflowId = workflow.id;` 后的 `}`）。

实际删除范围（17 行）：

```js
// 进入编辑模式：把已有编排数据回填到表单
function enterWorkflowEditMode(workflow) {
  const form = document.getElementById('workflowForm');
  form.querySelector('[name="workflow_id"]').value = workflow.id;
  form.querySelector('[name="name"]').value = workflow.name || '';
  form.querySelector('[name="group_name"]').value = workflow.group_name || '';
  form.querySelector('[name="failure_policy"]').value = workflow.failure_policy || 'stop_workflow';
  document.getElementById('workflowSteps').innerHTML = '';
  for (const step of (workflow.steps || [])) {
    addWorkflowStep(step);
  }
  if ((workflow.steps || []).length === 0) {
    addWorkflowStep();
  }
  document.getElementById('saveWorkflowButton').textContent = '更新编排';
  document.getElementById('cancelEditButton').hidden = false;
  state.editingWorkflowId = workflow.id;
}

```

注意：包括空行和注释。

- [ ] **Step 2.5: 删除 3 个死函数**

CLAUDE.md 规则："When your changes create orphans: Remove imports/variables/functions that YOUR changes made unused." 此次重构后，3 个函数在 `gui/renderer.js` 中无任何调用方，删除避免后续误解：

- **`addWorkflowStep`**（约 line 263-268）：原为常驻表单追加步骤。重构后无 caller，且函数体内引用 `document.getElementById('workflowSteps')` 已是 null，运行时调用会抛错。
- **`renderWorkflowStep`**（约 line 199-220）：原为常驻表单的步骤渲染。重构后无 caller（被 `renderModalStepAccordion` 替代）。
- **`renderStepDynamic`**（约 line 222-261）：原为常驻表单的步骤动态字段渲染。重构后无 caller（被 `renderModalStepBody` 替代）。

定位后整段删除 3 个函数及其上方注释。删除范围参考：

```js
// 渲染单个步骤的 fieldset 容器
function renderWorkflowStep(index, step = {}) {
  // ... 22 行
}

// 根据步骤类型渲染动态字段区
function renderStepDynamic(index, stepType, scriptId, config, condition) {
  // ... 40 行
}

// 追加新的空步骤或从已有 step 数据创建
function addWorkflowStep(step = {}) {
  // ... 5 行
}
```

确认删除后：`grep -n "addWorkflowStep\|renderWorkflowStep\|renderStepDynamic" gui/renderer.js` 应**无任何输出**。

- [ ] **Step 3: 替换 exitWorkflowEditMode 为新的工具函数区**

将 `gui/renderer.js` 中 `exitWorkflowEditMode` 函数（第 362-372 行附近）替换为以下 5 个新函数（**保留** `exitWorkflowEditMode` 名字作兼容？**不**，按 spec 它已无用，直接删除）：

找到 `exitWorkflowEditMode` 整段（11 行）：

```js
// 退出编辑模式：清空表单恢复保存状态
function exitWorkflowEditMode() {
  const form = document.getElementById('workflowForm');
  form.reset();
  form.querySelector('[name="workflow_id"]').value = '';
  document.getElementById('workflowSteps').innerHTML = '';
  addWorkflowStep();
  document.getElementById('saveWorkflowButton').textContent = '保存编排';
  document.getElementById('cancelEditButton').hidden = true;
  state.editingWorkflowId = null;
}
```

整段删除。

- [ ] **Step 4: 在 renderWorkflows() 之前插入新工具函数**

找到 `async function renderWorkflows() {`（在删除的 `exitWorkflowEditMode` 之后）。在它之前插入以下 4 个新函数 + 2 个辅助函数：

```js
// Modal 状态机：单个工具函数
function resetWorkflowModalState() {
  state.workflowModal = {
    open: false,
    mode: null,
    workflowId: null,
    dirty: false,
    expandedIndex: 0
  };
}

// 根据当前 step 字段生成手风琴 header 的摘要文字
function buildStepSummary(step) {
  const stepType = step.step_type || 'run_script';
  if (stepType === 'run_script') {
    const script = findScript(step.script_id);
    const name = script?.display_name || step.script_id || '未选脚本';
    return `运行脚本 · ${name}`;
  }
  if (stepType === 'wait_duration') {
    return `等待 ${step.condition?.seconds ?? 30} 秒`;
  }
  if (stepType === 'run_until_time') {
    return `运行到 ${step.condition?.until ?? '21:00'}`;
  }
  return stepType;
}

// 渲染单个步骤的手风琴
// 注意：HTML 规范禁止 button 嵌套 button；用 div 包裹 header 三件套
function renderModalStepAccordion(index, step = {}) {
  const stepType = step.step_type || 'run_script';
  const scriptId = step.script_id || (state.scripts[0]?.script_id || '');
  const expanded = index === state.workflowModal.expandedIndex;
  return `
    <div class="step-accordion${expanded ? ' expanded' : ''}" data-step-index="${index}">
      <div class="step-accordion-header" data-accordion-toggle="${index}">
        <span class="step-index-label">步骤 ${index + 1}</span>
        <span class="summary" data-step-summary="${index}">${escapeHtml(buildStepSummary(step))}</span>
        <button type="button" class="ghost-button remove-step" data-remove-step="${index}">移除</button>
      </div>
      <div class="step-accordion-body">
        <label class="field">
          <span>步骤类型</span>
          <select name="step_type" data-step-type-select="${index}">
            <option value="run_script"${stepType === 'run_script' ? ' selected' : ''}>运行脚本</option>
            <option value="wait_duration"${stepType === 'wait_duration' ? ' selected' : ''}>等待</option>
            <option value="run_until_time"${stepType === 'run_until_time' ? ' selected' : ''}>运行到指定时间</option>
          </select>
        </label>
        <div data-step-dynamic="${index}">
          ${renderModalStepBody(index, stepType, scriptId, step.config || {}, step.condition || {})}
        </div>
      </div>
    </div>
  `;
}

// 渲染手风琴 body：与原 renderStepDynamic 一致但 name 前缀改成 step_{index}_
function renderModalStepBody(index, stepType, scriptId, config, condition) {
  if (stepType === 'run_script') {
    const scriptOptions = state.scripts.map((s) => `
      <option value="${escapeHtml(s.script_id)}"${s.script_id === scriptId ? ' selected' : ''}>${escapeHtml(s.display_name || s.script_id)}</option>
    `).join('');
    const selectedScript = findScript(scriptId);
    const schemaFields = (selectedScript?.config_schema || []).map((field) => {
      const html = renderField(field, config);
      return html.replace(`name="${escapeHtml(field.key)}"`, `name="step_${index}_${escapeHtml(field.key)}"`);
    }).join('');
    return `
      <label class="field">
        <span>脚本</span>
        <select name="script_id" data-step-script-select="${index}">${scriptOptions}</select>
      </label>
      <div class="step-script-fields">${schemaFields}</div>
    `;
  }
  if (stepType === 'wait_duration') {
    const seconds = condition.seconds ?? 30;
    return `
      <label class="field">
        <span>等待秒数</span>
        <input name="seconds" type="number" min="0" value="${escapeHtml(seconds)}">
      </label>
    `;
  }
  if (stepType === 'run_until_time') {
    const until = condition.until ?? '21:00';
    return `
      <label class="field">
        <span>目标时间（HH:MM）</span>
        <input name="until" type="time" value="${escapeHtml(until)}">
      </label>
    `;
  }
  return '';
}

// 更新指定步骤的 header 摘要（不改展开状态）
function updateStepAccordionHeader(index) {
  const accordion = document.querySelector(`.step-accordion[data-step-index="${index}"]`);
  if (!accordion) return;
  const step = collectStepFromDom(index);
  const summaryEl = accordion.querySelector(`[data-step-summary="${index}"]`);
  if (summaryEl) summaryEl.textContent = buildStepSummary(step);
}

// 从 DOM 读取单个步骤的当前值（用于更新摘要）
function collectStepFromDom(index) {
  const accordion = document.querySelector(`.step-accordion[data-step-index="${index}"]`);
  if (!accordion) return {};
  const stepTypeSelect = accordion.querySelector('[data-step-type-select]');
  const stepType = stepTypeSelect?.value || 'run_script';
  const step = { step_type: stepType, config: {}, condition: {} };
  if (stepType === 'run_script') {
    const scriptSelect = accordion.querySelector('[data-step-script-select]');
    step.script_id = scriptSelect?.value || '';
    const prefix = `step_${index}_`;
    const fields = {};
    accordion.querySelectorAll('input, select').forEach((input) => {
      if (input.name?.startsWith(prefix)) {
        fields[input.name.slice(prefix.length)] = input.type === 'checkbox' ? input.checked : input.value;
      }
    });
    step.config = fields;
  } else if (stepType === 'wait_duration') {
    const secondsInput = accordion.querySelector('input[name="seconds"]');
    step.condition.seconds = Number(secondsInput?.value || 0);
  } else if (stepType === 'run_until_time') {
    const untilInput = accordion.querySelector('input[name="until"]');
    step.condition.until = untilInput?.value || '';
  }
  return step;
}

```

- [ ] **Step 5: 验证 JS 语法**

```bash
cd "F:/Users/56440/PythonProjects/yys-pc-script" && node --check gui/renderer.js
```

预期：退出码 0，无错误。如果报 `Cannot find name` 或语法错误，回退本次修改。

- [ ] **Step 6: Commit**

```bash
cd "F:/Users/56440/PythonProjects/yys-pc-script" && \
  git add gui/renderer.js && \
  git commit -m "refactor(gui): 引入 6 个 Modal/手风琴工具函数并删除旧编辑函数

- state.workflowModal 新增（open/mode/workflowId/dirty/expandedIndex）
- 删除 enterWorkflowEditMode 与 exitWorkflowEditMode（原 17+11 行）
- 新增：
  * resetWorkflowModalState 状态机重置
  * buildStepSummary 步骤摘要生成
  * renderModalStepAccordion 单步骤手风琴渲染
  * renderModalStepBody 单步骤 body 字段渲染（与原 renderStepDynamic 行为一致）
  * updateStepAccordionHeader 摘要更新
  * collectStepFromDom 从 DOM 读步骤当前值

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: 改造 editWorkflow / 改写 saveWorkflow 调用方 / 调整 init 启动

**Files:**
- Modify: `gui/renderer.js`（修改 `editWorkflow`、`saveWorkflow`、`init`）

- [ ] **Step 1: 修改 editWorkflow 函数**

找到 `editWorkflow(workflowId)` 函数（约第 422-427 行）：

```js
// 编辑编排：从缓存中找到对应数据后进入编辑模式
function editWorkflow(workflowId) {
  const workflow = state.workflows.find((w) => w.id === Number(workflowId));
  if (!workflow) return;
  enterWorkflowEditMode(workflow);
  switchView('workflows');
}
```

整段替换为：

```js
// 编辑编排：打开 Modal 并注入数据
function editWorkflow(workflowId) {
  const workflow = state.workflows.find((w) => w.id === Number(workflowId));
  if (!workflow) return;
  openWorkflowModal('edit', workflow);
}
```

注意：删除 `switchView('workflows')` 调用——因为 Modal 是顶层遮罩，无需切换 view。

- [ ] **Step 2: 修改 saveWorkflow 适配新 Modal DOM**

`saveWorkflow(form)` 函数（renderer.js:271-341）当前用 `document.querySelectorAll('.step-fieldset')` 选择步骤容器，**而新 DOM 不再生成 `.step-fieldset`（改为 `.step-accordion`）**。同时函数尾部第 339 行的 `exitWorkflowEditMode()` 在 Step 2 删除旧函数后会抛 ReferenceError。

打开 `gui/renderer.js` 找到 `async function saveWorkflow(form) {` 起始位置（renderer.js:271）做两处修改：

**2a) 第 273 行的选择器**：

```js
  const fieldsets = [...document.querySelectorAll('.step-fieldset')];
```

改为：

```js
  const fieldsets = [...document.querySelectorAll('.step-accordion')];
```

变量名 `fieldsets` 保持不变（只是来源元素类型换了），后续代码不用改。

**2b) 删除第 339 行的 `exitWorkflowEditMode()` 调用**：

```js
  exitWorkflowEditMode();
  await renderWorkflows();
```

改为（仅删除第 339 行；第 340 行 `await renderWorkflows()` 也删除——Modal 关闭后的列表刷新由 Task 5 Step 2c 提交回调统一处理）：

```js
```

整段删除两行后，`saveWorkflow` 函数以 `return; }` 结束（`appendLog` 之后直接到 `}`）。

- [ ] **Step 3: 修改 deleteWorkflow 删除 exitWorkflowEditMode 调用**

`deleteWorkflow` 函数（renderer.js:402-419）当前第 408-410 行检查 `state.editingWorkflowId` 并调用 `exitWorkflowEditMode()`。删除后这两行会引用已删除函数（即使 `editingWorkflowId` 已无 setter 也是个悬挂调用）：

```js
    if (state.editingWorkflowId === Number(workflowId)) {
      exitWorkflowEditMode();
    }
```

改为：直接删除整个 `if` 块（3 行），保留 `await renderWorkflows();`。修改后函数体：

```js
async function deleteWorkflow(workflowId) {
  if (!window.confirm('确认删除该编排任务？')) return;
  try {
    await apiDelete(`/api/workflows/${workflowId}`);
    appendLog({ level: 'INFO', message: `已删除编排: ${workflowId}` });
    await renderWorkflows();
  } catch (error) {
    if (error.status === 409) {
      window.alert('存在运行中的关联任务，无法删除');
    } else {
      appendLog({ level: 'ERROR', message: error.message });
    }
  }
}
```

- [ ] **Step 4: 修改 init 移除默认 addWorkflowStep**

找到 `init()` 函数（renderer.js:708-719）：

```js
async function init() {
  state.scripts = await apiGet('/api/scripts');
  state.selectedScriptId = state.scripts[0]?.script_id || null;
  renderScripts();
  bindEvents();
  addWorkflowStep();                  // ← 删
  await renderWorkflows();
  await refreshCurrentRun();
  connectEvents();
}
```

删除 `addWorkflowStep();` 这一行（行首 2 空格缩进）。删除后函数体保留其它 7 行不变。

- [ ] **Step 5: 验证 JS 语法**

```bash
cd "F:/Users/56440/PythonProjects/yys-pc-script" && node --check gui/renderer.js
```

预期：退出码 0。

- [ ] **Step 6: Commit**

```bash
cd "F:/Users/56440/PythonProjects/yys-pc-script" && \
  git add gui/renderer.js && \
  git commit -m "refactor(gui): editWorkflow 改调 openWorkflowModal 并清理 init

- editWorkflow 改为调 openWorkflowModal('edit', workflow)
  删除 switchView('workflows')（Modal 是顶层遮罩无需切 view）
- init 移除 addWorkflowStep() 默认占位调用
- saveWorkflow 选择器从 .step-fieldset 改为 .step-accordion（DOM 改造同步）
  删除函数尾部 exitWorkflowEditMode()/renderWorkflows() 调用
  （关闭与刷新由 Task 5 Modal submit 回调统一处理）
- deleteWorkflow 删除 editingWorkflowId 守卫与 exitWorkflowEditMode() 残留调用

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: 新增 openWorkflowModal / closeWorkflowModal 与完整事件绑定

**Files:**
- Modify: `gui/renderer.js`（在 `renderWorkflows` 之前插入 `openWorkflowModal` / `closeWorkflowModal` / `addModalWorkflowStep` / `removeModalWorkflowStep`；重写 `bindEvents` 中的 workflow 相关部分）

- [ ] **Step 1: 在 renderModalStepAccordion 之前插入 Modal 开关函数**

找到 `// Modal 状态机：单个工具函数`（在 Task 3 步骤 4 插入），在 `function resetWorkflowModalState()` 之前，插入以下 4 个新函数（**位置**：紧贴 `resetWorkflowModalState` 之上）：

```js
// 打开 Modal：mode = 'create' | 'edit'，edit 模式需传 workflow 对象
function openWorkflowModal(mode, workflow = null) {
  const modal = document.getElementById('workflowModal');
  const titleEl = document.getElementById('workflowModalTitle');
  const form = document.getElementById('workflowModalForm');
  const stepsContainer = document.getElementById('workflowModalSteps');

  // 1) 重置 state
  resetWorkflowModalState();
  state.workflowModal.open = true;
  state.workflowModal.mode = mode;
  state.workflowModal.workflowId = workflow?.id ?? null;

  // 2) 设置标题
  titleEl.textContent = mode === 'edit' ? '编辑编排' : '新建编排';

  // 3) 重置表单 + 注入数据
  form.reset();
  form.querySelector('[name="workflow_id"]').value = workflow?.id ?? '';
  if (workflow) {
    form.querySelector('[name="name"]').value = workflow.name || '';
    form.querySelector('[name="group_name"]').value = workflow.group_name || '';
    form.querySelector('[name="failure_policy"]').value = workflow.failure_policy || 'stop_workflow';
  }

  // 4) 渲染步骤
  stepsContainer.innerHTML = '';
  const initialSteps = (workflow?.steps || []).length > 0 ? workflow.steps : [{}];
  initialSteps.forEach((step, i) => {
    stepsContainer.insertAdjacentHTML('beforeend', renderModalStepAccordion(i, step));
  });
  state.workflowModal.expandedIndex = 0;

  // 5) 显示 Modal
  modal.hidden = false;
}

// 关闭 Modal：force=true 跳过 dirty 校验；force=false 走 confirm 流程
function closeWorkflowModal({ force = false } = {}) {
  if (!force && state.workflowModal.dirty) {
    const ok = window.confirm('有未保存的修改，确定关闭？');
    if (!ok) return;
  }
  const modal = document.getElementById('workflowModal');
  const form = document.getElementById('workflowModalForm');
  const stepsContainer = document.getElementById('workflowModalSteps');
  modal.hidden = true;
  form.reset();
  form.querySelector('[name="workflow_id"]').value = '';
  stepsContainer.innerHTML = '';
  resetWorkflowModalState();
}

// 添加步骤到 Modal
function addModalWorkflowStep() {
  const container = document.getElementById('workflowModalSteps');
  const index = container.children.length;
  container.insertAdjacentHTML('beforeend', renderModalStepAccordion(index, {}));
  state.workflowModal.expandedIndex = index;
  state.workflowModal.dirty = true;
  // 收起其它步骤
  [...container.children].forEach((el, i) => {
    el.classList.toggle('expanded', i === index);
  });
}

// 从 Modal 移除步骤
function removeModalWorkflowStep(index) {
  const container = document.getElementById('workflowModalSteps');
  if (container.children[index]) {
    container.children[index].remove();
  }
  // 全部移除则追加一个空步骤（addModalWorkflowStep 已自动展开）
  if (container.children.length === 0) {
    addModalWorkflowStep();
    return;
  }
  // 如果删的是当前展开的，重设到 0；否则保持原值
  if (state.workflowModal.expandedIndex === index) {
    state.workflowModal.expandedIndex = 0;
  } else if (state.workflowModal.expandedIndex > index) {
    state.workflowModal.expandedIndex -= 1;
  }
  // 重新编号：data-step-index / data-* / name / 标题 / expanded
  [...container.children].forEach((el, i) => {
    el.dataset.stepIndex = i;
    const header = el.querySelector('.step-accordion-header');
    if (header) {
      const firstSpan = header.querySelector('.step-index-label');
      if (firstSpan) firstSpan.textContent = `步骤 ${i + 1}`;
    }
    // 同步 data-* 属性
    el.querySelectorAll('[data-step-type-select], [data-step-script-select], [data-accordion-toggle], [data-remove-step], [data-step-summary], [data-step-dynamic]').forEach((node) => {
      for (const attr of node.attributes) {
        if (attr.name.startsWith('data-') && /\d+/.test(attr.value)) {
          attr.value = attr.value.replace(/\d+/, String(i));
        }
      }
    });
    // 同步 name 属性：把 name="step_OLD_xxx" 中的 OLD 改为 i
    el.querySelectorAll('[name^="step_"]').forEach((node) => {
      node.name = node.name.replace(/^step_\d+_/, `step_${i}_`);
    });
    // 同步 .expanded class
    el.classList.toggle('expanded', i === state.workflowModal.expandedIndex);
  });
  state.workflowModal.dirty = true;
}

```

- [ ] **Step 2: 重写 bindEvents 中的 workflow 相关事件**

找到 `bindEvents` 函数（约 renderer.js:589-706 行）。具体改动如下：

**2a) 修改 `[+ 新建编排]` 按钮**：原本没有，需要新增。`bindEvents` 函数体开头（line 590 后）插入：

```js
  document.getElementById('newWorkflowButton').addEventListener('click', () => {
    openWorkflowModal('create');
  });
```

**2b) 替换 `addWorkflowStep` 绑定**（renderer.js:605）：

```js
  document.getElementById('addWorkflowStep').addEventListener('click', addWorkflowStep);
```

改为：

```js
  document.getElementById('addModalStep').addEventListener('click', addModalWorkflowStep);
```

**2c) 替换 `workflowForm` 提交绑定**（renderer.js:607-612）：

```js
  document.getElementById('workflowForm').addEventListener('submit', (event) => {
    event.preventDefault();
    saveWorkflow(event.target).catch((error) => {
      appendLog({ level: 'ERROR', message: error.message });
    });
  });
```

改为：

```js
  document.getElementById('workflowModalForm').addEventListener('submit', (event) => {
    event.preventDefault();
    const form = event.target;
    saveWorkflow(form)
      .then(() => {
        closeWorkflowModal({ force: true });
        renderWorkflows();
      })
      .catch((error) => {
        appendLog({ level: 'ERROR', message: error.message });
        // 在 Modal 顶部插入错误条
        const body = document.querySelector('#workflowModal .modal-body');
        let errEl = body.querySelector('.modal-error');
        if (!errEl) {
          errEl = document.createElement('div');
          errEl.className = 'modal-error';
          body.insertBefore(errEl, body.firstChild);
        }
        errEl.textContent = `保存失败：${error.message}`;
      });
  });
```

**2d) 替换 `cancelEditButton` 绑定**（renderer.js:680）：

```js
  document.getElementById('cancelEditButton').addEventListener('click', exitWorkflowEditMode);
```

改为：

```js
  document.getElementById('closeWorkflowModalButton').addEventListener('click', () => closeWorkflowModal());
  document.getElementById('cancelWorkflowModalButton').addEventListener('click', () => closeWorkflowModal());
```

**2e) 在 `bindEvents` 末尾追加 Modal 内的事件委托**（约 line 705 之后、函数 `}` 之前）：

```js
  // Modal 内表单 change/input/click 事件委托
  // 关键：监听目标必须是 #workflowModalForm（覆盖 name/group_name/failure_policy
  // 顶层字段 + 步骤区），而不是 #workflowModalSteps（只覆盖步骤）。
  // 若只监听 steps，name/group_name/failure_policy 的变更不会触发 dirty，
  // E2E #5（改名称 → 点 ✕ 弹 confirm）会失败。
  document.getElementById('workflowModalForm').addEventListener('change', (event) => {
    state.workflowModal.dirty = true;
    const accordion = event.target.closest('.step-accordion');
    if (!accordion) return;
    const index = Number(accordion.dataset.stepIndex);
    if (event.target.matches('[data-step-type-select]')) {
      const newType = event.target.value;
      const dyn = accordion.querySelector('[data-step-dynamic]');
      const scriptId = state.scripts[0]?.script_id || '';
      dyn.innerHTML = renderModalStepBody(index, newType, scriptId, {}, {});
      updateStepAccordionHeader(index);
      return;
    }
    if (event.target.matches('[data-step-script-select]')) {
      const newScriptId = event.target.value;
      const dyn = accordion.querySelector('[data-step-dynamic]');
      dyn.innerHTML = renderModalStepBody(index, 'run_script', newScriptId, {}, {});
      updateStepAccordionHeader(index);
      return;
    }
  });

  // Modal 内 input：所有输入（包括步骤内字段）都标记 dirty
  document.getElementById('workflowModalForm').addEventListener('input', () => {
    state.workflowModal.dirty = true;
  });

  // Modal 内 click：手风琴切换 / 移除步骤
  document.getElementById('workflowModalForm').addEventListener('click', (event) => {
    const removeBtn = event.target.closest('[data-remove-step]');
    if (removeBtn) {
      event.stopPropagation();
      const accordion = removeBtn.closest('.step-accordion');
      if (accordion) removeModalWorkflowStep(Number(accordion.dataset.stepIndex));
      return;
    }
    const toggleBtn = event.target.closest('[data-accordion-toggle]');
    if (toggleBtn) {
      const accordion = toggleBtn.closest('.step-accordion');
      if (!accordion) return;
      const index = Number(accordion.dataset.stepIndex);
      const wasExpanded = accordion.classList.contains('expanded');
      // 收起所有
      document.querySelectorAll('.step-accordion').forEach((el) => el.classList.remove('expanded'));
      if (!wasExpanded) {
        accordion.classList.add('expanded');
        state.workflowModal.expandedIndex = index;
      }
    }
  });

  // ESC 键关闭尝试
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && state.workflowModal.open) {
      event.preventDefault();
      closeWorkflowModal();
    }
  });

  // 点击遮罩关闭尝试（点 panel 内不触发）
  document.getElementById('workflowModal').addEventListener('click', (event) => {
    if (event.target === event.currentTarget) {
      closeWorkflowModal();
    }
  });
```

- [ ] **Step 3: 验证 JS 语法**

```bash
cd "F:/Users/56440/PythonProjects/yys-pc-script" && node --check gui/renderer.js
```

预期：退出码 0。

- [ ] **Step 4: 验证后端测试不被破坏**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend -v 2>&1 | tail -20
```

预期：测试通过数 ≥ 既有基线（参考 `e3d7d84` 时的 38 passed）。如果后端测试本来就没动，**本步预期就是 38 passed**。

- [ ] **Step 5: Commit**

```bash
cd "F:/Users/56440/PythonProjects/yys-pc-script" && \
  git add gui/renderer.js && \
  git commit -m "feat(gui): 编排 Modal 完整接线：open/close/添加/移除/手风琴/ESC/遮罩

- 新增 openWorkflowModal / closeWorkflowModal / addModalWorkflowStep
  / removeModalWorkflowStep 4 个 Modal 控制函数
- bindEvents 改造：
  * 新建按钮 → openWorkflowModal('create')
  * addWorkflowStep 绑定 → addModalStep → addModalWorkflowStep
  * workflowForm submit → workflowModalForm submit
  * cancelEditButton 绑定 → closeWorkflowModalButton + cancelWorkflowModalButton
  * 步骤区 change/input/click 三个事件委托
  * ESC 键全局监听
  * 遮罩点击监听
- saveWorkflow 调用方改为 Modal；保存成功后 force 关闭 + 刷新列表
- 错误时在 Modal 顶部插入 .modal-error 提示条

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: 手动 E2E 验证（按 spec 10 条清单）

**Files:** 无（仅人工 + 后端日志）

- [ ] **Step 1: 启动后端**

```bash
cd "F:/Users/56440/PythonProjects/yys-pc-script" && \
  D:/ProgramData/anaconda3/envs/win_macro/python.exe -m ui_backend.main
```

预期：日志显示 `Application startup complete` 或 `Uvicorn running on http://127.0.0.1:8000`，无 `ModuleNotFoundError` / `ImportError`。

- [ ] **Step 2: 启动 Electron**

另开一个 shell：

```bash
cd "F:/Users/56440/PythonProjects/yys-pc-script/gui" && npm start
```

预期：Electron 窗口出现，工作台加载，点左侧"编排"导航能进入 workflowsView。

- [ ] **Step 3: 逐条验证 spec 验收清单**

打开浏览器/Electron 开发者工具 console（方便观察日志），按顺序验证：

| # | 操作 | 预期 |
|---|------|------|
| 1 | 点 `[+ 新建编排]` | Modal 居中弹出，标题"新建编排"，默认 1 个空步骤且第一个展开 |
| 2 | 填名称"日常探索"、分组"日常"、失败策略"失败后停止"、保留 1 个运行脚本步骤（选御魂）→ 保存 | Modal 关闭，列表新增 1 张"日常探索"卡片，console 写 INFO |
| 3 | 点"日常探索"卡片的"编辑" | Modal 标题"编辑日常探索"，所有字段和步骤回填，步骤摘要正确 |
| 4 | 点步骤 2 的 header | 步骤 2 展开、步骤 1 自动收起 |
| 5 | 改名称 → 点 ✕ | confirm 弹窗 → 取消 → Modal 保持 |
| 6 | 再次打开 Modal → 不改任何字段 → 点 ✕ | 直接关闭，无 confirm |
| 7 | 点 `[+ 添加步骤]` | 末尾追加空步骤并展开 |
| 8 | 点新步骤的"移除" | 步骤移除，剩余步骤重新编号 |
| 9 | 点"删除"卡片 | confirm → 卡片消失 |
| 10 | 切步骤类型（运行脚本→等待→运行到指定时间）各 2 次 | 每次切换后摘要 + 字段正确更新（不出现 step_type 选择器被销毁） |
| 11 | 视觉检查 Modal | 颜色全部使用现有 token（`--panel` 背景、`--line` 边框、`--green` 主按钮、`--muted` 文字），无硬编码颜色；与列表页卡片视觉协调 |
| 12 | 点"立即运行"卡片 | 切到执行页 + console 写 INFO |

- [ ] **Step 4: 后端最终回归**

确认后端进程仍在跑（Task 6 Step 1 启动的），运行：

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend -v 2>&1 | tail -5
```

预期：测试通过数与既有基线一致（38+ passed）。

- [ ] **Step 5: 关闭后端与 Electron**

手动 Ctrl+C 关闭两个进程。

- [ ] **Step 6: 提交验证记录**

将本任务验证结果追加到 spec 末尾（在 spec 第 401 行后追加"## 2026-06-02 验证记录"小节），模板：

```markdown
## 2026-06-02 验证记录

- `node --check gui/renderer.js`：通过
- `D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend -v`：N passed
- `D:/ProgramData/anaconda3/envs/win_macro/python.exe -m ui_backend.main` + `cd gui && npm start`：Modal 新建/编辑/删除/立即运行 10 条 E2E 全部通过
```

实际 N 与 E2E 结果按本任务执行情况填写。

```bash
cd "F:/Users/56440/PythonProjects/yys-pc-script" && \
  git add docs/specs/2026-06-02-workflow-list-modal-design.md && \
  git commit -m "docs(spec): 追加 2026-06-02 验证记录

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## 验收总览

- 所有 6 个 Task 的 checkbox 全部勾选完毕
- 6 次 commit 全部存在（`git log --oneline -7` 可见 6 个新 commit）
- `node --check gui/renderer.js` 通过
- `pytest tests/ui_backend` 维持基线（38+ passed）
- 10 条手动 E2E 全部通过
- `config/ui_workbench.db` 不再被追踪

## 风险与回滚

| 风险 | 回滚命令 |
|------|---------|
| Modal 渲染异常 | `git revert <task 5 commit>` |
| 步骤手风琴交互异常 | `git revert <task 3 commit>` |
| 整体回滚 | `git reset --hard 4a5f785`（回到 spec 已 commit 但未改 GUI 的状态） |
