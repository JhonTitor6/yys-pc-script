const API_BASE = 'http://127.0.0.1:8000';
const LOG_LIMIT = 500;
const UI_TOKEN = new URLSearchParams(window.location.search).get('token') || '';

const state = {
  scripts: [],
  selectedScriptId: null,
  currentRun: null,
  logs: [],
  workflows: [],
  editingWorkflowId: null,
  workflowModal: {
    open: false,
    mode: null,          // 'create' | 'edit'
    workflowId: null,    // edit 模式才有
    dirty: false,
    expandedIndex: 0
  },
  logLevelMin: 'INFO'
};

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: authHeaders()
  });
  if (!response.ok) {
    throw new Error(`请求失败: ${path} (${response.status})`);
  }
  return response.json();
}

async function apiPost(path, body = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`请求失败: ${path} (${response.status}) ${text}`);
  }
  return response.json();
}

async function apiPatch(path, body = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`请求失败: ${path} (${response.status}) ${text}`);
  }
  return response.json();
}

async function apiPut(path, body = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'PUT',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`请求失败: ${path} (${response.status}) ${text}`);
  }
  return response.json();
}

async function apiDelete(path) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: authHeaders()
  });
  if (!response.ok) {
    const text = await response.text();
    const error = new Error(`请求失败: ${path} (${response.status}) ${text}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function authHeaders(headers = {}) {
  if (!UI_TOKEN) return headers;
  return { ...headers, 'X-YYS-UI-Token': UI_TOKEN };
}

function eventsWebSocketUrl() {
  const query = UI_TOKEN ? `?token=${encodeURIComponent(UI_TOKEN)}` : '';
  return `ws://127.0.0.1:8000/ws/events${query}`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function findScript(scriptId) {
  return state.scripts.find((script) => script.script_id === scriptId) || null;
}

// 判断脚本是否处于正在运行/排队/暂停等活跃状态
function isScriptActive(scriptId) {
  const run = state.currentRun;
  if (!run || run.script_id !== scriptId) return false;
  return ['queued', 'running', 'paused'].includes(run.status);
}

// 运行中状态文案
function activeStatusText(status) {
  if (status === 'running') return '运行中';
  if (status === 'paused') return '已暂停';
  if (status === 'queued') return '排队中';
  return status;
}

function renderScripts() {
  const container = document.getElementById('scriptList');
  container.innerHTML = '';

  if (state.scripts.length === 0) {
    container.innerHTML = '<p class="empty-text">暂无可用脚本</p>';
    return;
  }

  // 活跃脚本（运行/暂停/排队）置顶，保持其它脚本原顺序
  const sorted = [...state.scripts].sort((a, b) => {
    const aActive = isScriptActive(a.script_id) ? 1 : 0;
    const bActive = isScriptActive(b.script_id) ? 1 : 0;
    return bActive - aActive;
  });

  for (const script of sorted) {
    const selected = state.selectedScriptId === script.script_id;
    const active = isScriptActive(script.script_id);
    const row = document.createElement('article');
    row.className = `script-row${selected ? ' selected' : ''}${active ? ' active' : ''}`;
    const activeBadge = active
      ? `<span class="active-badge" data-script-active="${escapeHtml(script.script_id)}">${escapeHtml(activeStatusText(state.currentRun?.status))}</span>`
      : '';
    // 运行中卡片：把启动按钮替换为控制按钮组
    const controlButtons = active ? renderActiveControls(state.currentRun?.status) : '';
    const startButton = active
      ? ''
      : `<button type="submit" class="primary-button">启动</button>`;
    row.innerHTML = `
      <button class="script-head" data-script-id="${escapeHtml(script.script_id)}" type="button">
        <span>
          <strong>${escapeHtml(script.display_name || script.script_id)}</strong>
          <small>${script.category === 'experimental' ? '实验脚本' : '稳定脚本'}</small>
        </span>
        <span class="script-head-right">${activeBadge}<span class="caret">${selected ? '⌄' : '›'}</span></span>
      </button>
      ${script.description ? `<p class="script-description">${escapeHtml(script.description)}</p>` : ''}
      <form class="script-params${selected ? ' active' : ''}" data-script-form="${escapeHtml(script.script_id)}">
        ${active ? '' : (script.config_schema || []).map((field) => renderField(field, script.default_config || {})).join('')}
        <div class="script-actions">${controlButtons}${startButton}</div>
      </form>
    `;
    container.appendChild(row);
  }
}

// 渲染运行中卡片的控制按钮组（暂停/恢复/停止）
function renderActiveControls(status) {
  const canPause = status === 'running';
  const canResume = status === 'paused';
  const canStop = ['running', 'paused', 'queued'].includes(status);
  return `
    <button type="button" class="ghost-button" data-run-control="pause"${canPause ? '' : ' disabled'}>暂停</button>
    <button type="button" class="ghost-button" data-run-control="resume"${canResume ? '' : ' disabled'}>恢复</button>
    <button type="button" class="danger-button" data-run-control="stop"${canStop ? '' : ' disabled'}>停止</button>
  `;
}

function renderField(field, defaults = {}) {
  const key = field.key;
  const value = defaults[key] ?? field.default ?? '';
  const label = escapeHtml(field.label || key);
  const name = escapeHtml(key);

  if (field.field_type === 'select') {
    const options = (field.options || []).map((item) => {
      const optionValue = item.value ?? item.label ?? '';
      const selected = String(optionValue) === String(value) ? ' selected' : '';
      return `<option value="${escapeHtml(optionValue)}"${selected}>${escapeHtml(item.label ?? optionValue)}</option>`;
    }).join('');
    return `<label class="field"><span>${label}</span><select name="${name}">${options}</select></label>`;
  }

  if (field.field_type === 'boolean') {
    const checked = value === true || value === 'true' ? ' checked' : '';
    return `<label class="field boolean-field"><input name="${name}" type="checkbox" value="true"${checked}><span>${label}</span></label>`;
  }

  const type = field.field_type === 'number' ? 'number' : 'text';
  const min = field.min_value !== null && field.min_value !== undefined ? ` min="${escapeHtml(field.min_value)}"` : '';
  const max = field.max_value !== null && field.max_value !== undefined ? ` max="${escapeHtml(field.max_value)}"` : '';
  return `<label class="field"><span>${label}</span><input name="${name}" type="${type}" value="${escapeHtml(value)}"${min}${max}></label>`;
}

function normalizeConfigValue(value, field) {
  if (field?.field_type === 'number') {
    return value === '' ? null : Number(value);
  }
  if (field?.field_type === 'boolean') {
    return value === true || value === 'true';
  }
  return value;
}

async function startScript(scriptId, form) {
  const formData = new FormData(form);
  const script = findScript(scriptId);
  const fields = script?.config_schema || [];
  const config = {};
  for (const [key, value] of formData.entries()) {
    const field = fields.find((item) => item.key === key);
    config[key] = normalizeConfigValue(value, field);
  }
  for (const field of fields) {
    if (field.field_type === 'boolean' && !(field.key in config)) {
      config[field.key] = false;
    }
  }
  try {
    const patchResp = await apiPatch(`/api/scripts/${encodeURIComponent(scriptId)}/config`, config);
    // Step 4: 热重载结果文案（B2 决策：默默落盘 + 当前 run 忽略）
    if (patchResp?.note) {
      appendLog({ level: 'INFO', message: patchResp.note });
    } else if (patchResp?.status === 'ok') {
      appendLog({ level: 'INFO', message: '配置已保存' });
    }
  } catch (error) {
    appendLog({ level: 'WARNING', message: `保存配置失败: ${error.message}` });
  }
  await apiPost('/api/runs/start', { script_id: scriptId, config });
  appendLog({ level: 'INFO', message: `已提交启动请求: ${scriptId}` });
  await refreshCurrentRun();
}

// 失败策略文案映射
const FAILURE_POLICY_LABELS = {
  stop_workflow: '失败后停止',
  continue_next: '失败后继续',
  retry_then_stop: '重试后停止'
};

// 保存或更新编排
async function saveWorkflow(form) {
  const data = new FormData(form);
  const fieldsets = [...document.querySelectorAll('.step-accordion')];
  const steps = fieldsets.map((fieldset, index) => {
    const inputs = fieldset.querySelectorAll('input, select');
    // 收集 fieldset 内所有控件的当前值
    const fields = {};
    for (const input of inputs) {
      if (input.type === 'checkbox') {
        fields[input.name] = input.checked;
      } else {
        fields[input.name] = input.value;
      }
    }
    const stepType = fields.step_type;
    const step = {
      sort_order: index + 1,
      step_type: stepType,
      retry_count: 0,
      script_id: null,
      config: {},
      condition: {}
    };
    if (stepType === 'run_script') {
      step.script_id = fields.script_id;
      // 提取 step_{index}_ 前缀的字段作为配置参数
      const prefix = `step_${index}_`;
      const script = findScript(step.script_id);
      const schemaFields = script?.config_schema || [];
      for (const key in fields) {
        if (key.startsWith(prefix)) {
          const realKey = key.slice(prefix.length);
          const fieldDef = schemaFields.find((f) => f.key === realKey);
          step.config[realKey] = normalizeConfigValue(fields[key], fieldDef);
        }
      }
      // 未勾选的 boolean 字段不会出现在 inputs，需要补 false
      for (const field of schemaFields) {
        if (field.field_type === 'boolean' && !(field.key in step.config)) {
          step.config[field.key] = false;
        }
      }
    } else if (stepType === 'wait_duration') {
      step.condition.seconds = Number(fields.seconds || 0);
    } else if (stepType === 'run_until_time') {
      step.condition.until = fields.until || '';
    }
    return step;
  });

  const payload = {
    name: data.get('name'),
    group_name: data.get('group_name'),
    enabled: true,
    trigger_type: 'manual',
    trigger_config: {},
    failure_policy: data.get('failure_policy'),
    steps
  };

  const editingId = data.get('workflow_id');
  if (editingId) {
    await apiPut(`/api/workflows/${editingId}`, payload);
    appendLog({ level: 'INFO', message: `已更新编排: ${payload.name || '未命名'}` });
  } else {
    await apiPost('/api/workflows', payload);
    appendLog({ level: 'INFO', message: `已保存编排: ${payload.name || '未命名'}` });
  }
}

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
    el.querySelectorAll('[data-step-type-select], [data-step-script-select], [data-accordion-toggle], [data-remove-step], [data-step-summary], [data-step-dynamic]').forEach((node) => {
      for (const attr of node.attributes) {
        if (attr.name.startsWith('data-') && /\d+/.test(attr.value)) {
          attr.value = attr.value.replace(/\d+/, String(i));
        }
      }
    });
    el.querySelectorAll('[name^="step_"]').forEach((node) => {
      node.name = node.name.replace(/^step_\d+_/, `step_${i}_`);
    });
    el.classList.toggle('expanded', i === state.workflowModal.expandedIndex);
  });
  state.workflowModal.dirty = true;
}

function resetWorkflowModalState() {
  state.workflowModal = {
    open: false,
    mode: null,
    workflowId: null,
    dirty: false,
    expandedIndex: 0
  };
}

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

function updateStepAccordionHeader(index) {
  const accordion = document.querySelector(`.step-accordion[data-step-index="${index}"]`);
  if (!accordion) return;
  const step = collectStepFromDom(index);
  const summaryEl = accordion.querySelector(`[data-step-summary="${index}"]`);
  if (summaryEl) summaryEl.textContent = buildStepSummary(step);
}

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

async function renderWorkflows() {
  const workflows = await apiGet('/api/workflows');
  state.workflows = workflows;
  const container = document.getElementById('workflowList');

  if (!workflows.length) {
    container.innerHTML = '<p class="empty-text">暂无编排任务</p>';
    return;
  }

  container.innerHTML = workflows.map((item) => {
    const isEditing = state.editingWorkflowId === item.id;
    const stepCount = (item.steps || []).length;
    const policyLabel = FAILURE_POLICY_LABELS[item.failure_policy] || item.failure_policy || '';
    return `
      <article class="workflow-card${isEditing ? ' editing' : ''}">
        <strong>${escapeHtml(item.name || '未命名编排')}</strong>
        <small>${escapeHtml(item.group_name || '未分组')} · ${stepCount} 个步骤 · ${escapeHtml(policyLabel)}</small>
        <div class="workflow-actions">
          <button data-run-workflow="${escapeHtml(item.id)}" class="ghost-button" type="button">立即运行</button>
          <button data-edit-workflow="${escapeHtml(item.id)}" class="ghost-button" type="button">编辑</button>
          <button data-delete-workflow="${escapeHtml(item.id)}" class="danger-button" type="button">删除</button>
        </div>
      </article>
    `;
  }).join('');
}

// 删除编排：409 表示存在关联运行任务
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

// 编辑编排：从缓存中找到对应数据后打开编辑弹窗
function editWorkflow(workflowId) {
  const workflow = state.workflows.find((w) => w.id === Number(workflowId));
  if (!workflow) return;
  openWorkflowModal('edit', workflow);
}

async function runWorkflowNow(workflowId) {
  await apiPost(`/api/workflows/${workflowId}/run-now`);
  appendLog({ level: 'INFO', message: `已提交编排运行请求: ${workflowId}` });
  switchView('execute');
  await refreshCurrentRun();
}

async function refreshCurrentRun() {
  state.currentRun = await apiGet('/api/runs/current');
  renderCurrentRun();
  renderScripts();
}

function statusText(status) {
  const labels = {
    queued: '排队',
    running: '运行中',
    paused: '已暂停',
    success: '已完成',
    error: '错误',
    stopped: '已停止'
  };
  return labels[status] || status || '空闲';
}

function sourceText(sourceType) {
  if (sourceType === 'workflow') return '编排';
  if (sourceType === 'manual') return '手动';
  return sourceType || '-';
}

// 将单个 config 字段值转成可读字符串，遵循 config_schema 渲染规则
function formatConfigValue(value, field) {
  if (value === true || value === 'true') return '是';
  if (value === false || value === 'false') return '否';
  if (field?.field_type === 'select' && Array.isArray(field.options)) {
    const match = field.options.find(
      (opt) => String(opt.value ?? opt.label ?? '') === String(value)
    );
    if (match) return match.label ?? String(match.value ?? '');
  }
  if (value === null || value === undefined || value === '') return '—';
  return String(value);
}

// 根据脚本的 config_schema 把 config 渲染为「标签：值」列表 HTML
function renderConfigSummary(config, script) {
  if (!config || Object.keys(config).length === 0) return '未配置';
  const schema = script?.config_schema || [];
  const schemaByKey = new Map(schema.map((f) => [f.key, f]));
  // 先按 schema 顺序输出 schema 中存在的字段，再追加自定义 key
  const orderedKeys = [
    ...schema.map((f) => f.key).filter((k) => k in config),
    ...Object.keys(config).filter((k) => !schemaByKey.has(k))
  ];
  if (orderedKeys.length === 0) return '未配置';
  return orderedKeys
    .map((key) => {
      const field = schemaByKey.get(key);
      const label = field?.label || key;
      const value = formatConfigValue(config[key], field);
      return `<span class="config-pair"><span class="config-key">${escapeHtml(label)}</span><span class="config-value">${escapeHtml(value)}</span></span>`;
    })
    .join('');
}

function renderCurrentRun() {
  const run = state.currentRun;
  const script = run ? findScript(run.script_id) : null;
  const status = run ? run.status : 'idle';
  const runStatus = document.getElementById('runStatus');

  document.getElementById('currentRunTitle').textContent = run
    ? (script?.display_name || run.script_id)
    : '暂无运行脚本';
  runStatus.textContent = run ? statusText(run.status) : '空闲';
  runStatus.className = `status-pill ${status}`;
  document.getElementById('runSource').textContent = run ? sourceText(run.source_type) : '-';
  const runConfigEl = document.getElementById('runConfigText');
  if (run) {
    runConfigEl.classList.add('config-summary');
    runConfigEl.innerHTML = renderConfigSummary(run.config || {}, script);
  } else {
    runConfigEl.classList.remove('config-summary');
    runConfigEl.textContent = '未启动';
  }

  if (!run) {
    renderSnapshot({});
  }
}

// 日志级别优先级映射，值越大表示严重程度越高
const LOG_LEVEL_ORDER = { DEBUG: 0, INFO: 1, WARNING: 2, ERROR: 3 };

// 判断某条日志在当前过滤等级下是否应展示
function shouldShowLog(level) {
  const min = LOG_LEVEL_ORDER[state.logLevelMin] ?? 1;
  const cur = LOG_LEVEL_ORDER[String(level || 'INFO').toUpperCase()] ?? 1;
  return cur >= min;
}

// 格式化当前时间为 HH:MM:SS 字符串
function formatLogTime(date = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

// 将单条日志写入指定容器
function appendLogLine(body, event) {
  const level = String(event.level || 'INFO').toUpperCase();
  const line = document.createElement('div');
  line.className = `log-line ${level}`;
  line.textContent = `[${formatLogTime()}] [${level}] ${event.message || event.data || JSON.stringify(event)}`;
  body.appendChild(line);
}

// 按当前级别过滤重渲染整个日志面板
function rerenderLogBody() {
  const body = document.getElementById('logBody');
  body.innerHTML = '';
  for (const event of state.logs) {
    if (shouldShowLog(event.level)) {
      appendLogLine(body, event);
    }
  }
  body.scrollTop = body.scrollHeight;
}

function appendLog(event) {
  state.logs.push(event);
  while (state.logs.length > LOG_LIMIT) {
    state.logs.shift();
  }
  const body = document.getElementById('logBody');
  if (shouldShowLog(event.level)) {
    appendLogLine(body, event);
    while (body.children.length > LOG_LIMIT) {
      body.removeChild(body.firstElementChild);
    }
    body.scrollTop = body.scrollHeight;
  }
  const level = String(event.level || 'INFO').toUpperCase();
  if (level === 'WARNING' || level === 'ERROR') {
    document.getElementById('keyLogPreview').textContent = `[${level}] ${event.message || ''}`;
  }
}

function connectEvents() {
  const ws = new WebSocket(eventsWebSocketUrl());
  ws.onopen = () => {
    refreshCurrentRun().catch((error) => {
      appendLog({ level: 'ERROR', message: `刷新运行状态失败: ${error.message}` });
    });
  };
  ws.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === 'log') appendLog(payload);
    if (payload.type === 'run_status_changed') refreshCurrentRun().catch((error) => {
      appendLog({ level: 'ERROR', message: error.message });
    });
    if (payload.type === 'state_snapshot') renderSnapshot(payload.state || {});
    if (payload.type === 'workflow_error') {
      const workflowId = payload.workflow_id ? `编排 ${payload.workflow_id}` : '编排';
      const detail = payload.message || payload.error || payload.data || '后台执行失败';
      const detailText = typeof detail === 'string' ? detail : JSON.stringify(detail);
      appendLog({ level: 'ERROR', message: `${workflowId}: ${detailText}` });
    }
  };
  ws.onerror = () => ws.close();
  ws.onclose = () => setTimeout(connectEvents, 2000);
}

function renderSnapshot(stateSnapshot) {
  const battleCount = stateSnapshot.battle_count ?? stateSnapshot.current_battle_count ?? 0;
  const maxBattleCount = stateSnapshot.max_battle_count ?? state.currentRun?.config?.max_battle_count ?? 0;
  const victoryCount = stateSnapshot.victory_count ?? stateSnapshot.win_count ?? 0;
  const progress = maxBattleCount > 0 ? Math.min(100, Math.round((battleCount / maxBattleCount) * 100)) : 0;

  document.getElementById('snapshotPreview').textContent = Object.keys(stateSnapshot).length
    ? JSON.stringify(stateSnapshot)
    : '暂无快照';
  document.getElementById('battleCount').textContent = `${battleCount} / ${maxBattleCount}`;
  document.getElementById('victoryCount').textContent = String(victoryCount);
  document.getElementById('progressBar').style.width = `${progress}%`;
}

async function controlCurrentRun(action) {
  if (!state.currentRun?.id) return;
  await apiPost(`/api/runs/${state.currentRun.id}/${action}`);
  await refreshCurrentRun();
}

function switchView(viewName) {
  const targetView = document.getElementById(`${viewName}View`);
  if (!targetView) return;

  document.querySelectorAll('.rail-button').forEach((button) => {
    button.classList.toggle('active', button.dataset.view === viewName);
  });
  document.querySelectorAll('.view').forEach((view) => {
    view.classList.toggle('active', view.id === `${viewName}View`);
  });
}

function bindEvents() {
  document.getElementById('scriptList').addEventListener('click', (event) => {
    // 运行中卡片的控制按钮（暂停/恢复/停止）优先处理
    const controlBtn = event.target.closest('[data-run-control]');
    if (controlBtn) {
      if (controlBtn.disabled) return;
      const action = controlBtn.dataset.runControl;
      controlCurrentRun(action).catch((error) => appendLog({ level: 'ERROR', message: error.message }));
      return;
    }
    const button = event.target.closest('[data-script-id]');
    if (!button) return;
    state.selectedScriptId = button.dataset.scriptId;
    renderScripts();
  });

  document.getElementById('scriptList').addEventListener('submit', (event) => {
    event.preventDefault();
    const form = event.target;
    // 运行中的卡片没有启动按钮（不渲染），此分支仅对其它卡片生效
    const controlBtn = event.submitter?.closest('[data-run-control]');
    if (controlBtn) return;
    startScript(form.dataset.scriptForm, form).catch((error) => {
      appendLog({ level: 'ERROR', message: error.message });
    });
  });

  document.getElementById('addModalStep').addEventListener('click', addModalWorkflowStep);

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

  document.getElementById('workflowList').addEventListener('click', (event) => {
    // 立即运行、编辑、删除三种操作通过 data-* 区分
    const run = event.target.closest('[data-run-workflow]');
    if (run) {
      runWorkflowNow(run.dataset.runWorkflow).catch((err) => appendLog({ level: 'ERROR', message: err.message }));
      return;
    }
    const edit = event.target.closest('[data-edit-workflow]');
    if (edit) {
      editWorkflow(edit.dataset.editWorkflow);
      return;
    }
    const del = event.target.closest('[data-delete-workflow]');
    if (del) {
      deleteWorkflow(del.dataset.deleteWorkflow);
      return;
    }
  });

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
      document.querySelectorAll('.step-accordion').forEach((el) => el.classList.remove('expanded'));
      if (!wasExpanded) {
        accordion.classList.add('expanded');
        state.workflowModal.expandedIndex = index;
      }
    }
  });

  document.getElementById('clearLogButton').addEventListener('click', () => {
    document.getElementById('logBody').innerHTML = '';
    document.getElementById('keyLogPreview').textContent = '暂无警告或错误';
    state.logs = [];
  });

  // 日志级别过滤切换时仅重渲染视图，不影响 state.logs
  document.getElementById('logLevelFilter').addEventListener('change', (event) => {
    state.logLevelMin = event.target.value;
    rerenderLogBody();
  });

  document.getElementById('closeWorkflowModalButton').addEventListener('click', () => closeWorkflowModal());
  document.getElementById('cancelWorkflowModalButton').addEventListener('click', () => closeWorkflowModal());

  document.querySelectorAll('.rail-button').forEach((button) => {
    button.addEventListener('click', () => switchView(button.dataset.view));
  });

  if (window.desktopBridge?.onTrayCommand) {
    window.desktopBridge.onTrayCommand((command) => {
      if (command === 'pause') {
        controlCurrentRun('pause').catch((error) => appendLog({ level: 'ERROR', message: error.message }));
      }
      if (command === 'stop') {
        controlCurrentRun('stop').catch((error) => appendLog({ level: 'ERROR', message: error.message }));
      }
    });
  }

  // 新建编排按钮
  document.getElementById('newWorkflowButton').addEventListener('click', () => {
    openWorkflowModal('create');
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
}

async function init() {
  state.scripts = await apiGet('/api/scripts');
  state.selectedScriptId = state.scripts[0]?.script_id || null;
  renderScripts();
  bindEvents();
  await renderWorkflows();
  await refreshCurrentRun();
  connectEvents();
}

init().catch((error) => appendLog({ level: 'ERROR', message: error.message }));
