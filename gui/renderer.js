const API_BASE = 'http://127.0.0.1:8000';
const LOG_LIMIT = 500;
const UI_TOKEN = new URLSearchParams(window.location.search).get('token') || '';

const ACTION_META = {
  pause: { label: '暂停', icon: 'pause', className: 'primary' },
  resume: { label: '恢复', icon: 'play', className: 'primary' },
  continue_waiting: { label: '继续等待 3 分钟', icon: 'refresh', className: 'primary' },
  retry: { label: '重试', icon: 'refresh', className: 'primary' },
  skip: { label: '跳过', icon: 'arrow-right', className: 'quiet' },
  manual_takeover: { label: '人工接管', icon: 'flag', className: 'quiet' },
  stop: { label: '停止', icon: 'stop', className: 'danger' }
};

const STATUS_LABELS = {
  queued: '排队中',
  running: '运行中',
  paused: '已暂停',
  success: '已完成',
  error: '执行失败',
  stopped: '已停止',
  skipped: '已跳过',
  manual: '人工接管'
};

const STAGE_LABELS = {
  queued: '排队中',
  starting: '启动中',
  preparing: '准备入口中',
  waiting_safe_entry: '等待战斗安全结束',
  waiting_safe_entry_timeout: '等待超时，请选择操作',
  navigating: '正在导航到入口',
  verifying_entry: '验证入口稳定',
  entry_failed: '入口准备失败',
  script_running: '脚本运行中',
  paused: '已暂停',
  script_failed: '脚本失败',
  start_failed: '启动失败',
  stopping: '停止中',
  stop_timeout: '停止超时',
  stopped: '已停止',
  stopped_after_error: '失败后停止',
  backend_restarted: '后端重启终止',
  completed: '已完成',
  skipped: '已跳过',
  manual_takeover: '人工接管'
};

const SOURCE_LABELS = { manual: '手动', workflow: '工作流' };

const FAILURE_POLICY_LABELS = {
  stop_workflow: '失败后停止',
  continue_next: '失败后继续',
  retry_then_stop: '重试后停止',
  stop: '失败后停止',
  continue: '失败后继续',
  retry: '按次数重试',
  skip: '失败后跳过',
  manual: '转人工接管',
  inherit: '继承工作流'
};

const STEP_FAILURE_POLICY_OPTIONS = [
  ['inherit', '继承工作流'],
  ['stop', '停止工作流'],
  ['continue', '继续下一步'],
  ['retry', '按次数重试'],
  ['skip', '跳过当前步骤'],
  ['manual', '转人工接管']
];

const state = {
  scripts: [],
  selectedScriptId: null,
  configDrafts: {},
  configDirty: {},
  configSaved: {},
  configErrors: {},
  configFeedback: '',
  saveState: 'idle',
  startState: 'idle',
  currentRun: null,
  logs: [],
  lastEventSeq: 0,
  socket: null,
  reconnectTimer: null,
  connectionStatus: 'disconnected',
  view: 'run',
  navCollapsed: localStorage.getItem('yys-gui-nav-collapsed') === 'true',
  theme: document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light',
  runDetailTab: 'timeline',
  workflows: [],
  workflowView: 'list',
  workflowDraft: null,
  workflowDirty: false,
  workflowExpandedIndex: 0,
  history: {
    scriptId: '',
    status: '',
    offset: 0,
    limit: 20,
    hasNext: false,
    items: [],
    detail: null,
    listScrollTop: 0
  }
};

function icon(name, label = '') {
  return `<svg class="icon" aria-hidden="true" focusable="false"><use href="#icon-${name}"></use></svg>${label}`;
}

function authHeaders(headers = {}) {
  return UI_TOKEN ? { ...headers, 'X-YYS-UI-Token': UI_TOKEN } : headers;
}

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: authHeaders(options.headers || {})
  });
  if (!response.ok) {
    const text = await response.text();
    const error = new Error(`请求失败：${path}（${response.status}）${text}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

async function apiGet(path) {
  return requestJson(path);
}

async function apiPost(path, body = {}) {
  return requestJson(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

async function apiPatch(path, body = {}) {
  return requestJson(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

async function apiPut(path, body = {}) {
  return requestJson(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

async function apiDelete(path) {
  return requestJson(path, { method: 'DELETE' });
}

function eventsWebSocketUrl() {
  const token = UI_TOKEN ? `?token=${encodeURIComponent(UI_TOKEN)}` : '';
  return `ws://127.0.0.1:8000/ws/events${token}`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

function findScript(scriptId) {
  return state.scripts.find((script) => script.script_id === scriptId) || null;
}

function getFieldType(field) {
  return field?.field_type === 'checkbox' ? 'boolean' : field?.field_type;
}

function scriptSchema(script) {
  return Array.isArray(script?.config_schema) ? script.config_schema : [];
}

function scriptTitle(scriptId) {
  const script = findScript(scriptId);
  return script?.display_name || scriptId || '未选择脚本';
}

function getScriptDraft(scriptId) {
  const script = findScript(scriptId);
  if (!script) return {};
  if (!state.configDrafts[scriptId]) {
    const draft = {};
    for (const field of scriptSchema(script)) {
      draft[field.key] = script.default_config?.[field.key] ?? field.default ?? '';
    }
    state.configDrafts[scriptId] = draft;
  }
  return state.configDrafts[scriptId];
}

function activeRunStatus(status = state.currentRun?.status) {
  return ['queued', 'running', 'paused'].includes(status);
}

function isConfigLocked() {
  return activeRunStatus() || ['stopping', 'stop_timeout'].includes(state.currentRun?.stage);
}

function statusText(status) {
  return STATUS_LABELS[status] || status || '空闲';
}

function stageText(run) {
  return STAGE_LABELS[run?.stage] || run?.stage || statusText(run?.status);
}

function sourceText(sourceType) {
  return SOURCE_LABELS[sourceType] || sourceType || '—';
}

function setConnectionStatus(status) {
  state.connectionStatus = status;
  const element = document.getElementById('connectionStatus');
  if (!element) return;
  const labels = { connected: '已连接', connecting: '连接中', reconnecting: '重连中', disconnected: '未连接' };
  element.textContent = labels[status] || status;
  element.className = `status-pill connection ${status}`;
}

function showToast(message, type = 'info') {
  const region = document.getElementById('toastRegion');
  if (!region) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  if (type === 'error') toast.setAttribute('role', 'alert');
  region.replaceChildren(toast);
  window.setTimeout(() => toast.remove(), type === 'error' ? 6000 : 3500);
}

function updateConfigFieldErrors(scriptId) {
  const errors = state.configErrors[scriptId] || {};
  document.querySelectorAll('[data-config-error]').forEach((element) => {
    const key = element.dataset.configError;
    element.textContent = errors[key] || '';
    element.hidden = !errors[key];
    const field = element.closest('.config-field');
    if (field) field.classList.toggle('has-error', Boolean(errors[key]));
  });
}

function renderField(field, values = {}, { prefix = '', disabled = false, scriptId = '', stepIndex = null } = {}) {
  const type = getFieldType(field);
  const key = field.key;
  const name = `${prefix}${key}`;
  const value = values[key] ?? field.default ?? '';
  const id = `${prefix.replaceAll('_', '-')}${key}-${stepIndex ?? 'config'}`;
  const description = field.description ? `<small class="field-note">${escapeHtml(field.description)}${field.unit ? ` · ${escapeHtml(field.unit)}` : ''}</small>` : field.unit ? `<small class="field-note">${escapeHtml(field.unit)}</small>` : '';
  const error = scriptId && stepIndex === null ? `<small class="field-error" data-config-error="${escapeHtml(key)}" hidden></small>` : '';
  const disabledAttr = disabled ? ' disabled' : '';

  if (type === 'select') {
    const options = (field.options || []).map((option) => {
      const optionValue = option.value ?? option.label ?? '';
      const selected = String(optionValue) === String(value) ? ' selected' : '';
      return `<option value="${escapeHtml(optionValue)}"${selected}>${escapeHtml(option.label ?? optionValue)}</option>`;
    }).join('');
    return `<label class="config-field" for="${escapeHtml(id)}"><span>${escapeHtml(field.label || key)}</span><select id="${escapeHtml(id)}" name="${escapeHtml(name)}" data-config-field="${escapeHtml(key)}"${disabledAttr}>${options}</select>${description}${error}</label>`;
  }

  if (type === 'boolean') {
    const checked = value === true || value === 'true' ? ' checked' : '';
    return `<label class="toggle-field config-field" for="${escapeHtml(id)}"><input id="${escapeHtml(id)}" name="${escapeHtml(name)}" type="checkbox" data-config-field="${escapeHtml(key)}"${checked}${disabledAttr}><span><b>${escapeHtml(field.label || key)}</b>${description}${error}</span></label>`;
  }

  const inputType = field.sensitive ? 'password' : type === 'number' ? 'number' : 'text';
  const min = field.min_value !== null && field.min_value !== undefined ? ` min="${escapeHtml(field.min_value)}"` : '';
  const max = field.max_value !== null && field.max_value !== undefined ? ` max="${escapeHtml(field.max_value)}"` : '';
  return `<label class="config-field" for="${escapeHtml(id)}"><span>${escapeHtml(field.label || key)}</span><input id="${escapeHtml(id)}" name="${escapeHtml(name)}" type="${inputType}" value="${escapeHtml(value)}" data-config-field="${escapeHtml(key)}"${min}${max}${disabledAttr}>${description}${error}</label>`;
}

function normalizeConfigValue(value, field) {
  const type = field?.field_type === 'checkbox' ? 'boolean' : field?.field_type;
  if (type === 'number') {
    return value === '' ? null : Number(value);
  }
  if (type === 'boolean') {
    return value === true || value === 'true';
  }
  if (type === 'select') {
    const matchedOption = (field.options || []).find((item) => {
      const optionValue = item.value ?? item.label ?? '';
      return String(optionValue) === String(value);
    });
    return matchedOption ? (matchedOption.value ?? matchedOption.label ?? '') : value;
  }
  return value;
}

async function startScript(scriptId, form) {
  const script = findScript(scriptId);
  if (!script || isConfigLocked()) return false;
  const config = collectConfigFromForm(form || document.getElementById('configForm'), script);
  const errors = validateConfig(config, script);
  state.configErrors[scriptId] = errors;
  updateConfigFieldErrors(scriptId);
  if (Object.keys(errors).length > 0) {
    state.configFeedback = '请先修正标红字段。';
    updateConfigUi();
    const firstError = Object.keys(errors)[0];
    document.querySelector(`[data-config-field="${CSS.escape(firstError)}"]`)?.focus();
    return false;
  }
  state.configDrafts[scriptId] = config;
  state.startState = 'starting';
  state.configFeedback = '正在提交启动请求…';
  updateConfigUi();
  try {
    await apiPost('/api/runs/start', { script_id: scriptId, config });
    state.configDirty[scriptId] = false;
    state.startState = 'idle';
    state.configFeedback = '已提交启动请求，等待后端快照。';
    showToast(`已启动：${scriptTitle(scriptId)}`, 'success');
    await refreshCurrentRun();
    return true;
  } catch (error) {
    state.startState = 'error';
    state.configFeedback = `启动失败：${error.message}`;
    showToast(error.message, 'error');
    updateConfigUi();
    return false;
  }
}

function collectConfigFromForm(form, script) {
  const config = {};
  if (!form) return config;
  for (const field of scriptSchema(script)) {
    const input = form.elements.namedItem(field.key);
    if (!input) continue;
    config[field.key] = normalizeConfigValue(getFieldType(field) === 'boolean' ? input.checked : input.value, field);
  }
  return config;
}

function validateConfig(config, script) {
  const errors = {};
  for (const field of scriptSchema(script)) {
    const type = getFieldType(field);
    const value = config[field.key];
    if (type === 'number') {
      if (value === null || !Number.isFinite(value)) {
        errors[field.key] = '请输入有效数字。';
        continue;
      }
      if (field.min_value !== null && field.min_value !== undefined && value < Number(field.min_value)) {
        errors[field.key] = `不能小于 ${field.min_value}。`;
      } else if (field.max_value !== null && field.max_value !== undefined && value > Number(field.max_value)) {
        errors[field.key] = `不能大于 ${field.max_value}。`;
      }
    }
    if (type === 'select' && !(field.options || []).some((option) => String(option.value ?? option.label ?? '') === String(value))) {
      errors[field.key] = '请选择有效选项。';
    }
  }
  return errors;
}

function renderScripts() {
  const container = document.getElementById('scriptList');
  if (!container) return;
  if (!state.scripts.length) {
    container.innerHTML = '<p class="empty-text">暂无可用脚本</p>';
    document.getElementById('configFields').innerHTML = '';
    updateConfigUi();
    return;
  }
  const current = findScript(state.selectedScriptId) || state.scripts[0];
  state.selectedScriptId = current.script_id;
  const options = state.scripts.map((script) => `<option value="${escapeHtml(script.script_id)}"${script.script_id === state.selectedScriptId ? ' selected' : ''}>${escapeHtml(script.display_name || script.script_id)}</option>`).join('');
  container.innerHTML = `<label class="script-picker-field"><span>运行脚本</span><select id="scriptSelector" aria-label="选择运行脚本"${isConfigLocked() ? ' disabled' : ''}>${options}</select><small>${escapeHtml(current.description || '选择一个脚本后配置真实参数。')}</small></label>`;
  renderConfigFields();
}

function renderConfigFields() {
  const script = findScript(state.selectedScriptId);
  const container = document.getElementById('configFields');
  if (!container) return;
  if (!script) {
    container.innerHTML = '<p class="empty-text">请选择脚本。</p>';
    updateConfigUi();
    return;
  }
  const readOnly = isConfigLocked();
  const fields = scriptSchema(script).map((field) => renderField(field, getScriptDraft(script.script_id), { disabled: readOnly, scriptId: script.script_id })).join('');
  container.innerHTML = `
    <form id="configForm" class="config-form" data-script-form="${escapeHtml(script.script_id)}">
      <div class="config-section"><div class="section-heading"><h3>脚本参数</h3><p>字段来自后端 config_schema，保存只影响下一次启动。</p></div><div class="config-grid">${fields}</div></div>
    </form>`;
  updateConfigFieldErrors(script.script_id);
  updateConfigUi();
}

function updateConfigUi() {
  const script = findScript(state.selectedScriptId);
  const id = script?.script_id;
  const dirty = Boolean(id && state.configDirty[id]);
  const locked = isConfigLocked();
  const errors = id ? state.configErrors[id] || {} : {};
  const status = document.getElementById('configStatus');
  if (status) {
    status.textContent = locked ? '运行中 · 已锁定' : dirty ? '未保存更改' : state.configSaved[id] ? '已保存' : script ? '可直接启动' : '未选择';
    status.className = `config-summary-state ${locked ? 'locked' : dirty ? 'dirty' : state.configSaved[id] ? 'saved' : ''}`;
  }
  const feedback = document.getElementById('configFeedback');
  if (feedback) {
    feedback.textContent = state.configFeedback || (locked ? '当前运行配置只读，停止后可修改下一次运行。' : dirty ? '参数会随本次启动使用，保存是可选的。' : '配置完成后可直接启动，保存用于保留设置。');
    feedback.classList.toggle('is-error', state.saveState === 'error' || state.startState === 'error' || Object.keys(errors).length > 0);
  }
  const saveButton = document.getElementById('configSaveButton');
  const resetButton = document.getElementById('configResetButton');
  const startButton = document.getElementById('configStartButton');
  if (saveButton) saveButton.disabled = locked || !script || !dirty || state.saveState === 'saving';
  if (resetButton) resetButton.disabled = locked || !script;
  if (startButton) startButton.disabled = locked || !script || state.startState === 'starting';
  if (startButton) startButton.innerHTML = state.startState === 'starting' ? '启动中…' : `${icon('play')}启动任务`;
}

async function saveScriptConfig() {
  const script = findScript(state.selectedScriptId);
  const form = document.getElementById('configForm');
  if (!script || !form || isConfigLocked()) return;
  const config = collectConfigFromForm(form, script);
  const errors = validateConfig(config, script);
  state.configErrors[script.script_id] = errors;
  updateConfigFieldErrors(script.script_id);
  if (Object.keys(errors).length > 0) {
    state.configFeedback = '请先修正标红字段。';
    updateConfigUi();
    return;
  }
  state.configDrafts[script.script_id] = config;
  state.saveState = 'saving';
  state.configFeedback = '正在保存配置…';
  updateConfigUi();
  try {
    const response = await apiPatch(`/api/scripts/${encodeURIComponent(script.script_id)}/config`, config);
    state.saveState = 'success';
    state.configDirty[script.script_id] = false;
    state.configSaved[script.script_id] = true;
    state.configFeedback = response?.applied === false ? '已保存，下次启动生效。' : '配置已保存。';
    showToast(state.configFeedback, 'success');
  } catch (error) {
    state.saveState = 'error';
    state.configFeedback = `保存失败：${error.message}`;
    showToast(state.configFeedback, 'error');
  }
  updateConfigUi();
}

function resetScriptConfig() {
  const script = findScript(state.selectedScriptId);
  if (!script || isConfigLocked()) return;
  delete state.configDrafts[script.script_id];
  state.configDirty[script.script_id] = false;
  state.configErrors[script.script_id] = {};
  state.configFeedback = '已恢复后端提供的默认值。';
  renderConfigFields();
}

function progressForRun(run) {
  const progress = run?.progress && Object.keys(run.progress).length ? run.progress : run?.latest_snapshot?.state || {};
  const current = progress.current ?? progress.battle_count ?? progress.current_battle_count;
  const total = progress.total ?? progress.max_battle_count ?? run?.config?.max_battle_count;
  const rawPercent = progress.percent ?? progress.progress_percent;
  const calculated = rawPercent === undefined && Number.isFinite(Number(current)) && Number(total) > 0
    ? Number(current) / Number(total) * 100
    : rawPercent;
  const percent = Number.isFinite(Number(calculated)) ? Math.max(0, Math.min(100, Number(calculated))) : null;
  return { current, total, percent, victory: progress.victory_count ?? progress.win_count };
}

function renderActionButton(action) {
  const meta = ACTION_META[action];
  if (!meta) return '';
  return `<button type="button" class="button ${meta.className}" data-run-action="${escapeHtml(action)}">${icon(meta.icon)}${escapeHtml(meta.label)}</button>`;
}

function renderTimeline(run) {
  const entries = [];
  if (run.started_at) entries.push(`<div class="timeline-item"><span class="timeline-time">${escapeHtml(formatDateTime(run.started_at))}</span><span class="timeline-marker"></span><div><b>开始运行</b><p>${escapeHtml(sourceText(run.source_type))} · ${escapeHtml(scriptTitle(run.script_id))}</p></div></div>`);
  if (run.updated_at || run.stage) entries.push(`<div class="timeline-item"><span class="timeline-time">${escapeHtml(formatDateTime(run.updated_at))}</span><span class="timeline-marker ${run.status === 'error' ? 'error' : run.status === 'success' ? 'ok' : ''}"></span><div><b>${escapeHtml(stageText(run))}</b><p>当前快照来自后端规范化运行状态。</p></div></div>`);
  return entries.length ? `<div class="timeline">${entries.join('')}</div>` : '<p class="empty-text">暂无可用阶段记录。</p>';
}

function renderEvidenceList(run) {
  const evidence = Array.isArray(run?.evidence) ? run.evidence : run?.latest_evidence ? [run.latest_evidence] : [];
  if (!evidence.length) return '<p class="empty-text">暂无截图证据。</p>';
  return evidence.map((item, index) => {
    const error = item.capture_error;
    const image = !error && run?.id && index === evidence.length - 1
      ? `<img src="${API_BASE}/api/runs/${encodeURIComponent(run.id)}/evidence/latest${UI_TOKEN ? `?token=${encodeURIComponent(UI_TOKEN)}` : ''}" alt="运行最新截图">`
      : '';
    return `<article class="evidence-item"><div><b>${error ? '截图不可用' : '截图证据'}</b><small>${escapeHtml(error || item.created_at || '已记录')}</small></div>${image || `<p>${escapeHtml(error || '已记录证据，但当前没有可预览文件。')}</p>`}</article>`;
  }).join('');
}

function renderLogsList(logs = state.logs) {
  if (!logs.length) return '<p class="empty-text">暂无日志。</p>';
  return `<div class="log-list">${logs.slice(-LOG_LIMIT).map((log) => `<div class="log-line ${escapeHtml(String(log.level || 'INFO').toUpperCase())}"><span>${escapeHtml(formatDateTime(log.created_at || log.timestamp))}</span><b>${escapeHtml(String(log.level || 'INFO').toUpperCase())}</b><p>${escapeHtml(log.message || log.data || '')}</p></div>`).join('')}</div>`;
}

function renderRunDetail(run) {
  if (!run) return '';
  if (state.runDetailTab === 'evidence') return renderEvidenceList(run);
  if (state.runDetailTab === 'logs') return renderLogsList(run.logs || state.logs);
  return renderTimeline(run);
}

function renderExecutionPanel() {
  const run = state.currentRun;
  if (!run) {
    return `<section class="execution-empty" aria-live="polite"><span class="empty-mark" aria-hidden="true">陰</span><h2>还没有运行</h2><p>从左侧选择脚本，配置完成后即可启动。保存配置不是启动前置条件。</p></section>`;
  }
  const progress = progressForRun(run);
  const actions = new Set(Array.isArray(run.available_actions) ? run.available_actions : []);
  const progressValue = progress.percent === null ? 0 : Math.round(progress.percent);
  const count = progress.current ?? '—';
  const total = progress.total ?? '—';
  const error = run.error_code ? `${run.error_code}：${run.error_message || '请根据可用操作恢复。'}` : run.error_message || '';
  const actionButtons = [...actions].map(renderActionButton).join('');
  return `
    <div class="execution-content" aria-live="polite">
      <div class="execution-heading"><div><span class="eyebrow">当前运行</span><h2>${escapeHtml(scriptTitle(run.script_id))}</h2><p>${escapeHtml(stageText(run))} · ${escapeHtml(sourceText(run.source_type))}</p></div><span id="runStatus" class="status-label state-${escapeHtml(run.status)}"><i aria-hidden="true"></i>${escapeHtml(statusText(run.status))}</span></div>
      ${error ? `<div class="run-error" role="alert"><strong>${escapeHtml(error)}</strong><p>请使用下方后端声明的恢复操作，操作完成后页面会重新读取运行快照。</p></div>` : ''}
      <div class="run-progress-large" tabindex="-1"><div class="progress-meta"><span>执行进度</span><strong id="progressText">${progress.percent === null ? '—' : `${progressValue}%`}</strong></div><div class="progress-track" role="progressbar" aria-label="当前运行进度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progressValue}"><span id="progressBar" style="width:${progressValue}%"></span></div><div class="progress-foot"><span>阶段：${escapeHtml(stageText(run))}</span><span>${escapeHtml(formatDateTime(run.updated_at || run.started_at))}</span></div></div>
      <div class="metric-strip"><div><span>已执行</span><b id="battleCount">${escapeHtml(count)} / ${escapeHtml(total)}</b></div><div><span>胜利</span><b id="victoryCount">${escapeHtml(progress.victory ?? '—')}</b></div><div><span>来源</span><b id="runSource">${escapeHtml(sourceText(run.source_type))}</b></div></div>
      <div class="run-action-group"><span class="action-group-title">可用操作</span><div class="action-row">${actionButtons || '<span class="muted-text">当前没有可用操作。</span>'}</div></div>
      <div class="execution-secondary-actions"><button type="button" class="link-button" data-view-run-detail>查看详细进度 ${icon('arrow-right')}</button></div>
      <div class="run-detail-tabs" role="tablist" aria-label="运行详情"><button type="button" role="tab" data-run-tab="timeline" aria-selected="${state.runDetailTab === 'timeline'}">时间线</button><button type="button" role="tab" data-run-tab="evidence" aria-selected="${state.runDetailTab === 'evidence'}">证据</button><button type="button" role="tab" data-run-tab="logs" aria-selected="${state.runDetailTab === 'logs'}">日志</button></div>
      <div id="runDetailContent" class="run-detail-content">${renderRunDetail(run)}</div>
    </div>`;
}

function renderTopbar() {
  const run = state.currentRun;
  const actions = new Set(run?.available_actions || []);
  const title = document.getElementById('currentRunTitle');
  const progressElement = document.getElementById('currentRunProgress');
  const status = document.getElementById('globalRunStatus');
  const stop = document.getElementById('mainStopButton');
  if (title) title.textContent = run ? scriptTitle(run.script_id) : '无';
  if (progressElement) {
    const progress = run ? progressForRun(run) : null;
    progressElement.textContent = progress ? `${progress.current ?? '—'} / ${progress.total ?? '—'}` : '—';
    progressElement.hidden = !run;
  }
  if (status) {
    status.textContent = run ? statusText(run.status) : '空闲';
    status.className = `status-pill ${run?.status || 'idle'}`;
  }
  if (stop) {
    stop.hidden = !actions.has('stop');
    stop.disabled = !actions.has('stop');
  }
}

function renderCurrentRun() {
  renderTopbar();
  renderConfigFields();
  const panel = document.getElementById('executionPanel');
  if (panel) panel.innerHTML = renderExecutionPanel();
}

function renderSnapshot(snapshot = {}) {
  const current = snapshot.current ?? snapshot.battle_count ?? snapshot.current_battle_count;
  const total = snapshot.total ?? snapshot.max_battle_count ?? state.currentRun?.config?.max_battle_count;
  const victory = snapshot.victory_count ?? snapshot.win_count;
  const percent = snapshot.percent ?? snapshot.progress_percent;
  const battle = document.getElementById('battleCount');
  const wins = document.getElementById('victoryCount');
  const bar = document.getElementById('progressBar');
  const text = document.getElementById('progressText');
  if (battle) battle.textContent = `${current ?? '—'} / ${total ?? '—'}`;
  if (wins) wins.textContent = String(victory ?? '—');
  if (bar && Number.isFinite(Number(percent))) bar.style.width = `${Math.max(0, Math.min(100, Number(percent)))}%`;
  if (text) text.textContent = Number.isFinite(Number(percent)) ? `${Math.round(Number(percent))}%` : '—';
}

async function refreshCurrentRun() {
  state.currentRun = await apiGet('/api/runs/current');
  renderCurrentRun();
}

async function controlCurrentRun(action, run = state.currentRun) {
  if (!run?.id || !(run.available_actions || []).includes(action)) return;
  const endpoint = { manual_takeover: 'manual-takeover', continue_waiting: 'continue-waiting' }[action] || action;
  try {
    await apiPost(`/api/runs/${encodeURIComponent(run.id)}/${endpoint}`);
    showToast(`${ACTION_META[action]?.label || '操作'}请求已提交。`, 'success');
  } catch (error) {
    showToast(error.message, 'error');
  }
  await refreshCurrentRun().catch((error) => showToast(`刷新运行状态失败：${error.message}`, 'error'));
}

function connectEvents() {
  if (state.socket) state.socket.close();
  setConnectionStatus('connecting');
  const suffix = state.lastEventSeq > 0 ? `${UI_TOKEN ? '&' : '?'}after_seq=${encodeURIComponent(state.lastEventSeq)}` : '';
  const socket = new WebSocket(`${eventsWebSocketUrl()}${suffix}`);
  state.socket = socket;
  socket.onopen = () => {
    setConnectionStatus('connected');
    refreshCurrentRun().catch((error) => showToast(`刷新运行状态失败：${error.message}`, 'error'));
  };
  socket.onmessage = (event) => {
    let payload;
    try { payload = JSON.parse(event.data); } catch { return; }
    if (Number.isFinite(Number(payload.seq))) {
      if (Number(payload.seq) <= state.lastEventSeq) return;
      state.lastEventSeq = Number(payload.seq);
    }
    if (payload.type === 'run_snapshot') {
      state.currentRun = payload.snapshot || null;
      renderCurrentRun();
      return;
    }
    if (payload.type === 'log') {
      appendLog(payload);
      return;
    }
    if (payload.type === 'state_snapshot' && state.currentRun) {
      state.currentRun.progress = payload.progress || state.currentRun.progress;
      renderCurrentRun();
      return;
    }
    if (payload.type === 'run_status_changed') {
      refreshCurrentRun().catch((error) => showToast(`刷新运行状态失败：${error.message}`, 'error'));
    }
    if (payload.type === 'workflow_error') {
      appendLog({ level: 'ERROR', message: `${payload.workflow_id ? `工作流 ${payload.workflow_id}` : '工作流'}：${payload.message || payload.error || '后台执行失败'}` });
    }
  };
  socket.onerror = () => socket.close();
  socket.onclose = () => {
    if (state.socket !== socket) return;
    setConnectionStatus('reconnecting');
    if (!state.reconnectTimer) {
      state.reconnectTimer = window.setTimeout(() => {
        state.reconnectTimer = null;
        connectEvents();
      }, 2000);
    }
  };
}

function appendLog(event) {
  state.logs.push(event);
  while (state.logs.length > LOG_LIMIT) state.logs.shift();
  if (state.currentRun && state.runDetailTab === 'logs') {
    const content = document.getElementById('runDetailContent');
    if (content) content.innerHTML = renderLogsList();
  }
}

function formatDateTime(value) {
  if (!value) return '—';
  return String(value).replace('T', ' ').slice(0, 19);
}

function formatDuration(start, end) {
  if (!start || !end) return '—';
  const begin = Date.parse(start);
  const finish = Date.parse(end);
  if (!Number.isFinite(begin) || !Number.isFinite(finish) || finish < begin) return '—';
  const seconds = Math.floor((finish - begin) / 1000);
  return `${Math.floor(seconds / 60)}分${String(seconds % 60).padStart(2, '0')}秒`;
}

function formatConfigValue(value, field) {
  if (value === true || value === 'true') return '是';
  if (value === false || value === 'false') return '否';
  if (getFieldType(field) === 'select') {
    const option = (field.options || []).find((item) => String(item.value ?? item.label ?? '') === String(value));
    if (option) return option.label ?? String(option.value ?? '');
  }
  return value === null || value === undefined || value === '' ? '—' : String(value);
}

function redactConfigForDisplay(config, script) {
  const result = {};
  for (const field of scriptSchema(script)) {
    if (!(field.key in (config || {}))) continue;
    result[field.label || field.key] = field.sensitive ? '••••••' : formatConfigValue(config[field.key], field);
  }
  return result;
}

function renderConfigSummary(config, script) {
  const data = redactConfigForDisplay(config, script);
  const entries = Object.entries(data);
  return entries.length ? entries.map(([key, value]) => `<span class="config-pair"><span class="config-key">${escapeHtml(key)}</span><span class="config-value">${escapeHtml(value)}</span></span>`).join('') : '未配置';
}

function defaultWorkflow() {
  return {
    id: null,
    name: '',
    group_name: '',
    enabled: true,
    trigger_type: 'manual',
    trigger_config: {},
    priority: 0,
    success_interval_seconds: 0,
    failure_interval_seconds: 0,
    failure_policy: 'stop_workflow',
    steps: [{ step_type: 'run_script', script_id: state.scripts[0]?.script_id || '', config: {}, condition: {}, retry_count: 0, failure_policy: 'inherit' }]
  };
}

function workflowDraftClone(workflow) {
  return clone(workflow || defaultWorkflow());
}

function renderWorkflowBasic() {
  const draft = state.workflowDraft;
  const trigger = draft.trigger_type || 'manual';
  document.getElementById('workflowEditorBasic').innerHTML = `
    <label class="config-field"><span>名称</span><input name="name" value="${escapeHtml(draft.name || '')}" required></label>
    <label class="config-field"><span>分组</span><input name="group_name" value="${escapeHtml(draft.group_name || '')}"></label>
    <div class="config-grid"><label class="toggle-field config-field"><input name="enabled" type="checkbox"${draft.enabled !== false ? ' checked' : ''}><span><b>启用自动调度</b><small class="field-note">只影响周期调度，不影响手动运行。</small></span></label><label class="config-field"><span>优先级</span><input name="priority" type="number" min="0" value="${escapeHtml(draft.priority ?? 0)}"></label></div>
    <div class="config-grid"><label class="config-field"><span>触发方式</span><select name="trigger_type"><option value="manual"${trigger === 'manual' ? ' selected' : ''}>手动</option><option value="interval"${trigger === 'interval' ? ' selected' : ''}>按间隔</option><option value="scheduled_time"${trigger === 'scheduled_time' ? ' selected' : ''}>每日定时</option></select></label><label class="config-field"><span>${trigger === 'scheduled_time' ? '每日时间' : '间隔秒数'}</span><input name="trigger_value" type="${trigger === 'scheduled_time' ? 'time' : 'number'}" min="0" value="${escapeHtml(trigger === 'scheduled_time' ? draft.trigger_config?.time || '09:00' : draft.trigger_config?.interval_seconds || 0)}"></label></div>
    <div class="config-grid"><label class="config-field"><span>成功间隔（秒）</span><input name="success_interval_seconds" type="number" min="0" value="${escapeHtml(draft.success_interval_seconds ?? 0)}"></label><label class="config-field"><span>失败间隔（秒）</span><input name="failure_interval_seconds" type="number" min="0" value="${escapeHtml(draft.failure_interval_seconds ?? 0)}"></label></div>
    <label class="config-field"><span>失败策略</span><select name="failure_policy">${Object.entries(FAILURE_POLICY_LABELS).filter(([key]) => key !== 'inherit').map(([key, label]) => `<option value="${key}"${draft.failure_policy === key ? ' selected' : ''}>${label}</option>`).join('')}</select></label>`;
}

function renderWorkflowStep(index, step) {
  const stepType = step.step_type || 'run_script';
  const scriptId = step.script_id || state.scripts[0]?.script_id || '';
  const script = findScript(scriptId);
  const scriptOptions = state.scripts.map((item) => `<option value="${escapeHtml(item.script_id)}"${item.script_id === scriptId ? ' selected' : ''}>${escapeHtml(item.display_name || item.script_id)}</option>`).join('');
  let dynamic = '';
  if (stepType === 'run_script') {
    dynamic = `<label class="config-field"><span>脚本</span><select data-step-script="${index}" name="step_${index}_script_id">${scriptOptions}</select></label><div class="config-grid">${scriptSchema(script).map((field) => renderField(field, step.config || {}, { prefix: `step_${index}_`, stepIndex: index })).join('')}</div>`;
  } else if (stepType === 'wait_duration') {
    dynamic = `<label class="config-field"><span>等待秒数</span><input name="step_${index}_seconds" type="number" min="0" value="${escapeHtml(step.condition?.seconds ?? 30)}"></label>`;
  } else if (stepType === 'run_until_time') {
    dynamic = `<label class="config-field"><span>目标时间</span><input name="step_${index}_until" type="time" value="${escapeHtml(step.condition?.until || '21:00')}"></label>`;
  }
  return `<article class="workflow-step" data-step-index="${index}"><div class="workflow-step-head"><button type="button" class="step-toggle" data-step-toggle="${index}" aria-expanded="${state.workflowExpandedIndex === index}"><span>步骤 ${index + 1}</span><strong>${escapeHtml(stepType === 'run_script' ? `运行脚本 · ${scriptTitle(scriptId)}` : stepType === 'wait_duration' ? '等待' : '运行到指定时间')}</strong></button><button type="button" class="link-button danger-link" data-remove-step="${index}">移除</button></div><div class="workflow-step-body"${state.workflowExpandedIndex === index ? '' : ' hidden'}><div class="config-grid"><label class="config-field"><span>步骤类型</span><select name="step_${index}_step_type" data-step-type="${index}"><option value="run_script"${stepType === 'run_script' ? ' selected' : ''}>运行脚本</option><option value="wait_duration"${stepType === 'wait_duration' ? ' selected' : ''}>等待</option><option value="run_until_time"${stepType === 'run_until_time' ? ' selected' : ''}>运行到指定时间</option></select></label><label class="config-field"><span>步骤失败策略</span><select name="step_${index}_failure_policy">${STEP_FAILURE_POLICY_OPTIONS.map(([value, label]) => `<option value="${value}"${(step.failure_policy || 'inherit') === value ? ' selected' : ''}>${label}</option>`).join('')}</select></label></div><div class="config-grid"><label class="config-field"><span>重试次数</span><input name="step_${index}_retry_count" type="number" min="0" value="${escapeHtml(step.retry_count ?? 0)}"></label>${dynamic}</div></div></article>`;
}

function renderWorkflowEditor() {
  const draft = state.workflowDraft;
  if (!draft) return;
  document.getElementById('workflowEditorTitle').textContent = draft.id ? '编辑工作流' : '新建工作流';
  document.getElementById('workflowEditorState').textContent = state.workflowDirty ? '有未保存修改' : '未保存';
  renderWorkflowBasic();
  document.getElementById('workflowEditorSteps').innerHTML = (draft.steps || []).map((step, index) => renderWorkflowStep(index, step)).join('') || '<p class="empty-text">暂无步骤，请添加。</p>';
}

function renderWorkflowList() {
  const container = document.getElementById('workflowList');
  if (!container) return;
  if (!state.workflows.length) {
    container.innerHTML = '<p class="empty-text">暂无工作流。</p>';
    return;
  }
  container.innerHTML = state.workflows.map((workflow) => {
    const trigger = workflow.trigger_type === 'interval' ? `间隔 ${workflow.trigger_config?.interval_seconds || 0} 秒` : workflow.trigger_type === 'scheduled_time' ? `每日 ${workflow.trigger_config?.time || '未设置'}` : '手动';
    return `<article class="workflow-row"><div><strong>${escapeHtml(workflow.name || '未命名工作流')}</strong><small>${escapeHtml(workflow.group_name || '未分组')} · ${(workflow.steps || []).length} 个步骤 · ${escapeHtml(trigger)}</small></div><span class="state-label ${workflow.enabled ? 'state-success' : 'state-idle'}"><i aria-hidden="true"></i>${workflow.enabled ? '已启用' : '已停用'}</span><div class="workflow-actions"><button class="button quiet" type="button" data-run-workflow="${escapeHtml(workflow.id)}">立即运行</button><button class="button quiet" type="button" data-toggle-workflow="${escapeHtml(workflow.id)}" data-enabled="${workflow.enabled ? 'true' : 'false'}">${workflow.enabled ? '停用' : '启用'}</button><button class="button quiet" type="button" data-edit-workflow="${escapeHtml(workflow.id)}">编辑</button><button class="button danger" type="button" data-delete-workflow="${escapeHtml(workflow.id)}">删除</button></div></article>`;
  }).join('');
}

async function renderWorkflows() {
  state.workflows = await apiGet('/api/workflows');
  renderWorkflowList();
  if (state.workflowView === 'editor') renderWorkflowEditor();
}

function openWorkflowEditor(workflow = null) {
  state.workflowDraft = workflowDraftClone(workflow);
  state.workflowView = 'editor';
  state.workflowDirty = false;
  state.workflowExpandedIndex = 0;
  renderWorkflowPage();
  document.getElementById('workflowEditorTitle')?.focus();
}

function closeWorkflowEditor(force = false) {
  if (!force && state.workflowDirty && !window.confirm('有未保存的修改，确定离开编辑器？')) return false;
  state.workflowDraft = null;
  state.workflowDirty = false;
  state.workflowView = 'list';
  renderWorkflowPage();
  return true;
}

function collectWorkflowDraftFromDom() {
  if (!state.workflowDraft) return null;
  const form = document.getElementById('workflowEditorForm');
  const draft = workflowDraftClone(state.workflowDraft);
  draft.name = form.elements.name.value;
  draft.group_name = form.elements.group_name.value;
  draft.enabled = form.elements.enabled.checked;
  draft.priority = Number(form.elements.priority.value || 0);
  draft.trigger_type = form.elements.trigger_type.value;
  draft.success_interval_seconds = Number(form.elements.success_interval_seconds.value || 0);
  draft.failure_interval_seconds = Number(form.elements.failure_interval_seconds.value || 0);
  draft.failure_policy = form.elements.failure_policy.value;
  const triggerValue = form.elements.trigger_value.value;
  draft.trigger_config = draft.trigger_type === 'interval' ? { interval_seconds: Number(triggerValue || 0) } : draft.trigger_type === 'scheduled_time' ? { time: triggerValue || '' } : {};
  draft.steps = [...form.querySelectorAll('.workflow-step')].map((element, index) => {
    const type = element.querySelector(`[name="step_${index}_step_type"]`)?.value || 'run_script';
    const step = { sort_order: index + 1, step_type: type, script_id: null, config: {}, condition: {}, retry_count: Number(element.querySelector(`[name="step_${index}_retry_count"]`)?.value || 0), failure_policy: element.querySelector(`[name="step_${index}_failure_policy"]`)?.value || 'inherit' };
    if (type === 'run_script') {
      step.script_id = element.querySelector(`[name="step_${index}_script_id"]`)?.value || '';
      const script = findScript(step.script_id);
      for (const field of scriptSchema(script)) {
        const input = element.querySelector(`[name="step_${index}_${CSS.escape(field.key)}"]`);
        if (!input) continue;
        step.config[field.key] = normalizeConfigValue(getFieldType(field) === 'boolean' ? input.checked : input.value, field);
      }
    } else if (type === 'wait_duration') {
      step.condition.seconds = Number(element.querySelector(`[name="step_${index}_seconds"]`)?.value || 0);
    } else {
      step.condition.until = element.querySelector(`[name="step_${index}_until"]`)?.value || '';
    }
    return step;
  });
  return draft;
}

async function saveWorkflow(form) {
  const draft = collectWorkflowDraftFromDom();
  if (!draft) return;
  const payload = {
    name: draft.name,
    group_name: draft.group_name,
    enabled: draft.enabled,
    trigger_type: draft.trigger_type,
    trigger_config: draft.trigger_config,
    priority: draft.priority,
    success_interval_seconds: draft.success_interval_seconds,
    failure_interval_seconds: draft.failure_interval_seconds,
    failure_policy: draft.failure_policy,
    steps: draft.steps
  };
  const feedback = document.getElementById('workflowEditorFeedback');
  try {
    if (draft.id) await apiPut(`/api/workflows/${encodeURIComponent(draft.id)}`, payload);
    else await apiPost('/api/workflows', payload);
    state.workflowDirty = false;
    await renderWorkflows();
    closeWorkflowEditor(true);
    showToast('工作流已保存。', 'success');
  } catch (error) {
    if (feedback) feedback.textContent = `保存失败：${error.message}`;
    showToast(error.message, 'error');
  }
}

async function toggleWorkflow(workflowId, enabled) {
  try {
    await apiPost(`/api/workflows/${encodeURIComponent(workflowId)}/${enabled ? 'enable' : 'disable'}`);
    await renderWorkflows();
    showToast(enabled ? '工作流已启用。' : '工作流已停用。', 'success');
  } catch (error) { showToast(error.message, 'error'); }
}

async function deleteWorkflow(workflowId) {
  if (!window.confirm('确认删除该工作流？')) return;
  try {
    await apiDelete(`/api/workflows/${encodeURIComponent(workflowId)}`);
    await renderWorkflows();
    showToast('工作流已删除。', 'success');
  } catch (error) {
    showToast(error.status === 409 ? '存在运行中的关联任务，无法删除。' : error.message, 'error');
  }
}

async function runWorkflowNow(workflowId) {
  try {
    await apiPost(`/api/workflows/${encodeURIComponent(workflowId)}/run-now`);
    switchView('run');
    await refreshCurrentRun();
    showToast('已提交工作流运行请求。', 'success');
  } catch (error) { showToast(error.message, 'error'); }
}

function renderWorkflowPage() {
  const list = document.getElementById('workflowListView');
  const editor = document.getElementById('workflowEditorView');
  const editing = state.workflowView === 'editor';
  if (list) list.hidden = editing;
  if (editor) editor.hidden = !editing;
  if (editing) renderWorkflowEditor();
  else renderWorkflowList();
}

const HISTORY_STATUS_LABELS = { queued: '排队中', running: '运行中', paused: '已暂停', success: '已完成', error: '错误', stopped: '已停止', skipped: '已跳过', manual: '人工接管' };

function populateHistoryScriptFilter() {
  const select = document.getElementById('historyScriptFilter');
  if (!select) return;
  const current = state.history.scriptId;
  select.innerHTML = `<option value="">全部脚本</option>${state.scripts.map((script) => `<option value="${escapeHtml(script.script_id)}"${script.script_id === current ? ' selected' : ''}>${escapeHtml(script.display_name || script.script_id)}</option>`).join('')}`;
}

async function loadHistory() {
  const params = new URLSearchParams({ limit: String(state.history.limit), offset: String(state.history.offset) });
  if (state.history.scriptId) params.set('script_id', state.history.scriptId);
  if (state.history.status) params.set('status', state.history.status);
  state.history.items = await apiGet(`/api/runs?${params.toString()}`);
  state.history.hasNext = state.history.items.length >= state.history.limit;
  renderHistory();
}

function renderHistory() {
  const container = document.getElementById('historyList');
  if (!container) return;
  const items = state.history.items;
  if (!items.length) {
    container.innerHTML = '<p class="empty-text">暂无符合条件的历史运行。</p>';
  } else {
    container.innerHTML = `<table class="history-table"><thead><tr><th>任务</th><th>状态</th><th>开始时间</th><th>耗时</th><th>来源</th><th>错误码</th><th><span class="sr-only">操作</span></th></tr></thead><tbody>${items.map((item) => `<tr><td><strong>${escapeHtml(scriptTitle(item.script_id))}</strong><small>#${escapeHtml(item.id)}</small></td><td><span class="status-label state-${escapeHtml(item.status)}"><i aria-hidden="true"></i>${escapeHtml(HISTORY_STATUS_LABELS[item.status] || item.status || '未知')}</span></td><td>${escapeHtml(formatDateTime(item.started_at || item.updated_at))}</td><td>${escapeHtml(formatDuration(item.started_at, item.ended_at))}</td><td>${escapeHtml(sourceText(item.source_type))}</td><td>${escapeHtml(item.error_code || '—')}</td><td><button class="link-button" type="button" data-history-detail="${escapeHtml(item.id)}">查看详情 ${icon('arrow-right')}</button></td></tr>`).join('')}</tbody></table>`;
  }
  const page = Math.floor(state.history.offset / state.history.limit) + 1;
  document.getElementById('historyPageText').textContent = `第 ${page} 页`;
  document.getElementById('historyPreviousButton').disabled = state.history.offset === 0;
  document.getElementById('historyNextButton').disabled = !state.history.hasNext;
}

function renderHistoryDetail(detail) {
  const script = findScript(detail.script_id);
  const logs = detail.logs || [];
  const snapshots = detail.snapshots || [];
  const evidence = detail.evidence || [];
  const config = redactConfigForDisplay(detail.config, script);
  const actions = new Set(detail.available_actions || []);
  const actionButtons = [...actions].map(renderActionButton).join('');
  const evidenceText = evidence.length ? renderEvidenceList({ ...detail, evidence }) : '<p class="empty-text">暂无证据。</p>';
  return `<header class="page-command history-detail-heading"><div><button class="link-button back-link" type="button" data-history-back>← 返回历史</button><h2 tabindex="-1">${escapeHtml(scriptTitle(detail.script_id))} · #${escapeHtml(detail.id)}</h2><p>${escapeHtml(HISTORY_STATUS_LABELS[detail.status] || detail.status || '未知')} · ${escapeHtml(stageText(detail))}</p></div><div class="action-row">${actionButtons}</div></header><div class="detail-summary-grid"><div><span>开始</span><b>${escapeHtml(formatDateTime(detail.started_at))}</b></div><div><span>结束</span><b>${escapeHtml(formatDateTime(detail.ended_at))}</b></div><div><span>耗时</span><b>${escapeHtml(formatDuration(detail.started_at, detail.ended_at))}</b></div><div><span>来源</span><b>${escapeHtml(sourceText(detail.source_type))}</b></div></div>${detail.error_code || detail.error_message ? `<div class="run-error" role="alert"><strong>${escapeHtml(detail.error_code || '运行失败')}</strong><p>${escapeHtml(detail.error_message || '请查看日志与证据。')}</p></div>` : ''}<div class="history-detail-grid"><section class="settings-section"><div class="section-heading"><h3>配置</h3></div><div class="config-summary-list">${Object.entries(config).map(([key, value]) => `<div><span>${escapeHtml(key)}</span><b>${escapeHtml(value)}</b></div>`).join('') || '<p class="empty-text">未配置</p>'}</div></section><section class="settings-section"><div class="section-heading"><h3>记录</h3></div><p>快照 ${snapshots.length} 条 · 证据 ${evidence.length} 条 · 日志 ${logs.length} 条</p></section></div><div class="detail-tabs"><section><h3>时间线</h3>${renderTimeline(detail)}</section><section><h3>证据</h3>${evidenceText}</section><section><h3>日志</h3>${renderLogsList(logs)}</section></div>`;
}

async function showHistoryDetail(runId) {
  state.history.listScrollTop = document.getElementById('historyListView')?.scrollTop || 0;
  try {
    state.history.detail = await apiGet(`/api/runs/${encodeURIComponent(runId)}`);
    document.getElementById('historyListView').hidden = true;
    const detail = document.getElementById('historyDetailView');
    detail.hidden = false;
    detail.innerHTML = renderHistoryDetail(state.history.detail);
    detail.querySelector('h2')?.focus();
  } catch (error) { showToast(error.message, 'error'); }
}

function closeHistoryDetail() {
  state.history.detail = null;
  document.getElementById('historyDetailView').hidden = true;
  document.getElementById('historyListView').hidden = false;
  renderHistory();
}

function setTheme(theme) {
  state.theme = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.dataset.theme = state.theme;
  localStorage.setItem('yys-gui-theme', state.theme);
  const button = document.getElementById('themeToggle');
  if (button) {
    button.setAttribute('aria-label', state.theme === 'dark' ? '切换浅色主题' : '切换深色主题');
    button.innerHTML = icon(state.theme === 'dark' ? 'sun' : 'moon');
  }
  document.querySelectorAll('[data-theme-option]').forEach((option) => option.classList.toggle('active', option.dataset.themeOption === state.theme));
}

function renderSettings() {
  setTheme(state.theme);
}

function setNavCollapsed(collapsed) {
  state.navCollapsed = collapsed;
  const compactByViewport = window.matchMedia?.('(max-width: 840px)').matches || false;
  const effectiveCollapsed = collapsed || compactByViewport;
  document.querySelector('.app-shell')?.classList.toggle('nav-collapsed', effectiveCollapsed);
  const toggle = document.getElementById('navToggle');
  if (toggle) {
    toggle.setAttribute('aria-expanded', String(!effectiveCollapsed));
    toggle.setAttribute('aria-label', effectiveCollapsed ? '展开导航' : '折叠导航');
    toggle.dataset.tooltip = effectiveCollapsed ? '展开导航' : '折叠导航';
  }
  localStorage.setItem('yys-gui-nav-collapsed', String(collapsed));
}

function switchView(viewName) {
  const view = viewName === 'progress' ? 'run' : viewName === 'logs' ? 'history' : viewName;
  if (state.view === 'workflows' && state.workflowView === 'editor' && state.workflowDirty && view !== 'workflows') {
    if (!window.confirm('工作流有未保存的修改，确定离开？')) return;
    closeWorkflowEditor(true);
  }
  state.view = view;
  const titles = { run: '运行', workflows: '工作流', history: '历史', settings: '设置' };
  document.getElementById('pageTitle').textContent = titles[view] || '工作台';
  document.querySelectorAll('.nav-item').forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  document.querySelectorAll('.page.view').forEach((element) => { element.hidden = element.id !== `${view}View`; element.classList.toggle('active', element.id === `${view}View`); });
  if (view === 'workflows') renderWorkflowPage();
  if (view === 'history') { populateHistoryScriptFilter(); loadHistory().catch((error) => showToast(error.message, 'error')); }
  if (view === 'settings') renderSettings();
  window.setTimeout(() => document.querySelector(`#${view}View h2, #${view}View h1, #${view}View button`)?.focus(), 0);
}

function bindEvents() {
  document.querySelectorAll('.nav-item').forEach((button) => button.addEventListener('click', () => switchView(button.dataset.view)));
  document.getElementById('navToggle').addEventListener('click', () => setNavCollapsed(!state.navCollapsed));
  document.getElementById('themeToggle').addEventListener('click', () => setTheme(state.theme === 'dark' ? 'light' : 'dark'));
  document.querySelectorAll('[data-window-action]').forEach((button) => button.addEventListener('click', () => window.desktopBridge?.windowAction?.(button.dataset.windowAction)));
  document.getElementById('viewRunButton').addEventListener('click', () => switchView('run'));

  document.getElementById('scriptList').addEventListener('change', (event) => {
    if (event.target.id !== 'scriptSelector' || isConfigLocked()) return;
    state.selectedScriptId = event.target.value;
    state.configFeedback = '';
    state.saveState = 'idle';
    renderScripts();
  });
  document.getElementById('configFields').addEventListener('input', (event) => {
    const script = findScript(state.selectedScriptId);
    const field = scriptSchema(script).find((item) => item.key === event.target.dataset.configField);
    if (!script || !field) return;
    const draft = getScriptDraft(script.script_id);
    draft[field.key] = normalizeConfigValue(getFieldType(field) === 'boolean' ? event.target.checked : event.target.value, field);
    state.configDirty[script.script_id] = true;
    state.configSaved[script.script_id] = false;
    delete (state.configErrors[script.script_id] || {})[field.key];
    updateConfigFieldErrors(script.script_id);
    state.configFeedback = '';
    updateConfigUi();
  });
  document.querySelectorAll('[data-config-action]').forEach((button) => button.addEventListener('click', () => {
    if (button.dataset.configAction === 'save') saveScriptConfig();
    if (button.dataset.configAction === 'reset') resetScriptConfig();
    if (button.dataset.configAction === 'start') startScript(state.selectedScriptId, document.getElementById('configForm'));
  }));
  document.getElementById('executionPanel').addEventListener('click', (event) => {
    const action = event.target.closest('[data-run-action]');
    if (action) { controlCurrentRun(action.dataset.runAction); return; }
    if (event.target.closest('[data-view-run-detail]')) {
      const target = document.querySelector('.run-progress-large');
      target?.scrollIntoView({ behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
      target?.focus?.();
      return;
    }
    const tab = event.target.closest('[data-run-tab]');
    if (tab) { state.runDetailTab = tab.dataset.runTab; renderCurrentRun(); }
  });
  document.getElementById('mainStopButton').addEventListener('click', () => controlCurrentRun('stop'));

  document.getElementById('newWorkflowButton').addEventListener('click', () => openWorkflowEditor());
  document.getElementById('workflowBackButton').addEventListener('click', () => closeWorkflowEditor());
  document.getElementById('addWorkflowStepButton').addEventListener('click', () => { state.workflowDraft.steps.push({ step_type: 'run_script', script_id: state.scripts[0]?.script_id || '', config: {}, condition: {}, retry_count: 0, failure_policy: 'inherit' }); state.workflowExpandedIndex = state.workflowDraft.steps.length - 1; state.workflowDirty = true; renderWorkflowEditor(); });
  document.getElementById('workflowEditorForm').addEventListener('submit', (event) => { event.preventDefault(); saveWorkflow(event.target); });
  document.getElementById('workflowEditorForm').addEventListener('input', () => { state.workflowDirty = true; document.getElementById('workflowEditorState').textContent = '有未保存修改'; });
  document.getElementById('workflowEditorForm').addEventListener('change', (event) => {
    state.workflowDirty = true;
    const step = event.target.closest('.workflow-step');
    if (step && (event.target.dataset.stepType !== undefined || event.target.dataset.stepScript !== undefined)) {
      const index = Number(step.dataset.stepIndex);
      state.workflowDraft = collectWorkflowDraftFromDom();
      if (event.target.dataset.stepType !== undefined) state.workflowDraft.steps[index].step_type = event.target.value;
      if (event.target.dataset.stepScript !== undefined) state.workflowDraft.steps[index].script_id = event.target.value;
      renderWorkflowEditor();
    }
  });
  document.getElementById('workflowEditorSteps').addEventListener('click', (event) => {
    const toggle = event.target.closest('[data-step-toggle]');
    if (toggle) { state.workflowExpandedIndex = Number(toggle.dataset.stepToggle); renderWorkflowEditor(); return; }
    const remove = event.target.closest('[data-remove-step]');
    if (remove) { const index = Number(remove.dataset.removeStep); state.workflowDraft.steps.splice(index, 1); state.workflowExpandedIndex = Math.max(0, Math.min(state.workflowExpandedIndex, state.workflowDraft.steps.length - 1)); state.workflowDirty = true; renderWorkflowEditor(); }
  });
  document.getElementById('workflowList').addEventListener('click', (event) => {
    const run = event.target.closest('[data-run-workflow]');
    if (run) return runWorkflowNow(run.dataset.runWorkflow);
    const toggle = event.target.closest('[data-toggle-workflow]');
    if (toggle) return toggleWorkflow(toggle.dataset.toggleWorkflow, toggle.dataset.enabled !== 'true');
    const edit = event.target.closest('[data-edit-workflow]');
    if (edit) return openWorkflowEditor(state.workflows.find((item) => String(item.id) === String(edit.dataset.editWorkflow)));
    const remove = event.target.closest('[data-delete-workflow]');
    if (remove) return deleteWorkflow(remove.dataset.deleteWorkflow);
  });

  document.getElementById('historyScriptFilter').addEventListener('change', (event) => { state.history.scriptId = event.target.value; state.history.offset = 0; loadHistory().catch((error) => showToast(error.message, 'error')); });
  document.getElementById('historyStatusFilter').addEventListener('change', (event) => { state.history.status = event.target.value; state.history.offset = 0; loadHistory().catch((error) => showToast(error.message, 'error')); });
  document.getElementById('refreshHistoryButton').addEventListener('click', () => loadHistory().catch((error) => showToast(error.message, 'error')));
  document.getElementById('historyPreviousButton').addEventListener('click', () => { state.history.offset = Math.max(0, state.history.offset - state.history.limit); loadHistory().catch((error) => showToast(error.message, 'error')); });
  document.getElementById('historyNextButton').addEventListener('click', () => { if (!state.history.hasNext) return; state.history.offset += state.history.limit; loadHistory().catch((error) => showToast(error.message, 'error')); });
  document.getElementById('historyList').addEventListener('click', (event) => { const detail = event.target.closest('[data-history-detail]'); if (detail) showHistoryDetail(detail.dataset.historyDetail); });
  document.getElementById('historyDetailView').addEventListener('click', (event) => {
    if (event.target.closest('[data-history-back]')) { closeHistoryDetail(); return; }
    const action = event.target.closest('[data-run-action]');
    if (action && state.history.detail) controlCurrentRun(action.dataset.runAction, state.history.detail).then(() => { if (action.dataset.runAction === 'retry') switchView('run'); });
  });
  document.querySelectorAll('[data-theme-option]').forEach((button) => button.addEventListener('click', () => setTheme(button.dataset.themeOption)));

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && state.workflowView === 'editor') { event.preventDefault(); closeWorkflowEditor(); }
  });
  if (window.desktopBridge?.onTrayCommand) window.desktopBridge.onTrayCommand((command) => { if (command === 'pause' || command === 'stop') controlCurrentRun(command); });
  if (window.desktopBridge?.onWindowState) window.desktopBridge.onWindowState((windowState) => { const button = document.querySelector('[data-window-action="toggle-maximize"]'); if (button) button.innerHTML = icon(windowState.maximized ? 'restore' : 'maximize'); });
  window.matchMedia?.('(max-width: 840px)').addEventListener?.('change', () => setNavCollapsed(state.navCollapsed));
}

async function init() {
  setNavCollapsed(state.navCollapsed);
  setTheme(state.theme);
  bindEvents();
  try {
    state.scripts = await apiGet('/api/scripts');
    state.selectedScriptId = state.scripts[0]?.script_id || null;
    populateHistoryScriptFilter();
    renderScripts();
    await renderWorkflows();
    await refreshCurrentRun();
    await loadHistory();
    switchView('run');
    connectEvents();
  } catch (error) {
    setConnectionStatus('disconnected');
    showToast(`工作台初始化失败：${error.message}`, 'error');
    renderScripts();
  }
}

init();
