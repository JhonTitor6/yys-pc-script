const navItems = [
  ['run', '运行', 'play'],
  ['workflow', '工作流', 'workflow'],
  ['history', '历史', 'history'],
  ['settings', '设置', 'settings']
];

const scriptOptions = [
  ['soul_raid', '御魂·日常'],
  ['abyss_shadows', '狭间暗域'],
  ['exploration', '探索·第 28 章']
];

const actionMeta = {
  pause: { label: '暂停', icon: 'pause', className: 'primary' },
  resume: { label: '恢复', icon: 'play', className: 'primary' },
  continue_waiting: { label: '继续等待', icon: 'refresh', className: 'primary' },
  retry: { label: '重试', icon: 'refresh', className: 'primary' },
  skip: { label: '跳过', icon: 'arrow-right', className: 'quiet' },
  manual_takeover: { label: '人工接管', icon: 'flag', className: 'quiet' },
  stop: { label: '停止', icon: 'stop', className: 'danger' }
};

const statusLabels = {
  idle: '未启动',
  configured: '已保存',
  queued: '排队中',
  running: '运行中',
  paused: '已暂停',
  error: '执行失败',
  manual: '人工接管',
  success: '已完成',
  stopped: '已停止',
  skipped: '已跳过'
};

const stageLabels = {
  idle: '请在左侧选择脚本并保存配置',
  configured: '配置已保存，可从左侧启动',
  queued: '等待执行',
  preparing: '准备运行环境',
  waiting_safe_entry: '等待安全进入',
  waiting_safe_entry_timeout: '安全进入等待已超时',
  navigating: '进入任务界面',
  verifying_entry: '确认任务入口',
  script_running: '正在执行脚本',
  paused: '已暂停，等待恢复',
  script_failed: '脚本执行失败',
  manual_takeover: '等待人工处理',
  completed: '任务已完成',
  stopped: '已停止，等待下一次启动',
  skipped: '已跳过当前运行'
};

const historyRows = [
  ['御魂·日常', '已完成', '10 / 10', '今天 21:24', 'success'],
  ['探索·第 28 章', '人工接管', '—', '今天 20:48', 'manual'],
  ['御魂·日常', '已停止', '3 / 10', '昨天 23:16', 'stopped'],
  ['狭间暗域', '已完成', '6 / 6', '昨天 22:03', 'success']
];

const statePreviewOptions = [
  ['idle', '空状态'],
  ['configured', '已保存'],
  ['queued', '排队中'],
  ['running-prep', '准备中'],
  ['running', '运行中'],
  ['waiting-timeout', '等待超时'],
  ['paused', '已暂停'],
  ['error', '失败'],
  ['manual', '人工接管'],
  ['success', '已完成'],
  ['stopped', '已停止']
];

function createScriptConfig(script = 'soul_raid') {
  return {
    script,
    battleCount: 10,
    failurePolicy: 'stop_workflow',
    manualTakeover: true,
    evidenceCapture: true,
    teamSlot: '队伍 1',
    soulLevel: '御魂·悲鸣',
    chapter: '第 28 章',
    autoAdvance: true,
    targetArea: '孔雀',
    bossCount: 2,
    bossDamageLimit: 120000,
    commanderCount: 4,
    eliteCount: 6,
    damageMode: '达到上限后停止',
    leaderMode: true
  };
}

function getScriptTitle(script = 'soul_raid') {
  if (script === 'abyss_shadows') return '狭间暗域';
  if (script === 'exploration') return '探索·第 28 章';
  return '御魂·日常';
}

function createRun(script = 'soul_raid') {
  return {
    title: getScriptTitle(script),
    count: 0,
    total: createScriptConfig(script).battleCount,
    progress: 0,
    status: 'idle',
    stage: 'idle',
    elapsed: '—',
    source: '—',
    available_actions: [],
    error_code: '',
    error_message: '',
    events: []
  };
}

const state = {
  view: 'run',
  theme: document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light',
  navMode: 'expanded',
  detailOpen: false,
  modalReturnFocus: '#mainContent',
  configBaseline: createScriptConfig(),
  configDraft: createScriptConfig(),
  configCommitted: false,
  saveState: 'idle',
  saveMessage: '',
  fieldErrors: {},
  simulateSaveFailure: false,
  viewportPreset: '900x650',
  currentRun: createRun(),
  focusAfterRender: ''
};

const app = document.getElementById('app');

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function icon(name, label = '') {
  return `<svg class="icon" aria-hidden="true" focusable="false"><use href="#icon-${name}"></use></svg>${label}`;
}

function renderIconSprite() {
  return `
    <svg class="icon-sprite" aria-hidden="true">
      <symbol id="icon-play" viewBox="0 0 24 24"><path d="M8 5.8v12.4a1.5 1.5 0 0 0 2.27 1.29l9.7-6.2a1.5 1.5 0 0 0 0-2.54l-9.7-6.2A1.5 1.5 0 0 0 8 5.8Z" fill="currentColor"/></symbol>
      <symbol id="icon-pause" viewBox="0 0 24 24"><path d="M8 5.5v13M16 5.5v13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></symbol>
      <symbol id="icon-workflow" viewBox="0 0 24 24"><path d="M5 5h5v5H5zM14 14h5v5h-5zM10 7.5h4a2 2 0 0 1 2 2V14M7.5 10v4a2 2 0 0 0 2 2H14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></symbol>
      <symbol id="icon-history" viewBox="0 0 24 24"><path d="M4.2 10a8 8 0 1 1 1.9 6.2M4 5v5h5M12 7v5l3.4 2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></symbol>
      <symbol id="icon-settings" viewBox="0 0 24 24"><path d="m9.7 4.1.5-1.1h3.6l.5 1.1 1.4.8 1.2-.2 1.8 3.1-.8.9v1.7l.8.9-1.8 3.1-1.2-.2-1.4.8-.5 1.1h-3.6l-.5-1.1-1.4-.8-1.2.2-1.8-3.1.8-.9V8.7l-.8-.9 1.8-3.1 1.2.2 1.4-.8Z" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linejoin="round"/><circle cx="12" cy="9.6" r="2.5" fill="none" stroke="currentColor" stroke-width="1.55"/></symbol>
      <symbol id="icon-panel" viewBox="0 0 24 24"><path d="M4 5.5h16v13H4zM9 5.5v13M6.5 8.5h.01M6.5 11.5h.01M6.5 14.5h.01" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></symbol>
      <symbol id="icon-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3.4" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M12 2.8v2M12 19.2v2M21.2 12h-2M4.8 12h-2M18.5 5.5l-1.4 1.4M6.9 17.1l-1.4 1.4M18.5 18.5l-1.4-1.4M6.9 6.9 5.5 5.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></symbol>
      <symbol id="icon-moon" viewBox="0 0 24 24"><path d="M18.7 15.9A7.5 7.5 0 0 1 8.1 5.3 7.5 7.5 0 1 0 18.7 15.9Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></symbol>
      <symbol id="icon-stop" viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"/></symbol>
      <symbol id="icon-external" viewBox="0 0 24 24"><path d="M14 5h5v5M19 5l-8 8M18 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
      <symbol id="icon-arrow-right" viewBox="0 0 24 24"><path d="m9.5 5 7 7-7 7M16 12H7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></symbol>
      <symbol id="icon-chevron" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></symbol>
      <symbol id="icon-check" viewBox="0 0 24 24"><path d="m5 12.5 4.3 4.3L19 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></symbol>
      <symbol id="icon-plus" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></symbol>
      <symbol id="icon-close" viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></symbol>
      <symbol id="icon-minimize" viewBox="0 0 24 24"><path d="M5 17.5h14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></symbol>
      <symbol id="icon-maximize" viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1.7"/></symbol>
      <symbol id="icon-restore" viewBox="0 0 24 24"><path d="M8 8h10v10M6 16V6h10" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></symbol>
      <symbol id="icon-refresh" viewBox="0 0 24 24"><path d="M19 8.5A7 7 0 0 0 6.4 6.7L4.5 8.5M4.5 5v3.5H8M5 15.5a7 7 0 0 0 12.6 1.8l1.9-1.8M19.5 19v-3.5H16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
      <symbol id="icon-flag" viewBox="0 0 24 24"><path d="M6 20V4m0 1c3-2 5 2 8 0 1.2-.8 2.5-.9 4-.2V14c-1.5-.7-2.8-.6-4 .2-3 2-5-2-8 0" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
    </svg>`;
}

function isCompactNavigation() {
  return state.navMode === 'compact' || window.innerWidth <= 840;
}

function isRunActive() {
  return ['queued', 'running', 'paused'].includes(state.currentRun.status);
}

function isConfigLocked() {
  return isRunActive();
}

function isConfigDirty() {
  return JSON.stringify(state.configDraft) !== JSON.stringify(state.configBaseline);
}

function statusLabel(status) {
  return statusLabels[status] || status;
}

function stageLabel(stage) {
  return stageLabels[stage] || stage;
}

function cloneConfig(config) {
  return { ...config };
}

function render() {
  document.documentElement.dataset.theme = state.theme;
  app.innerHTML = `${renderIconSprite()}${renderShell()}${renderDetailModal()}`;
  const focusTarget = state.focusAfterRender;
  state.focusAfterRender = '';
  if (focusTarget) {
    window.requestAnimationFrame(() => document.querySelector(focusTarget)?.focus());
  }
}

function renderShell() {
  const compact = isCompactNavigation();
  return `
    <div class="app-frame">
      ${renderWindowChrome()}
      <div class="app-shell ${compact ? 'is-compact' : ''}" data-view="${state.view}">
        <aside class="app-nav" aria-label="主导航">
          <div class="nav-brand">
            <span class="brand-seal" aria-hidden="true">陰</span>
            <div class="brand-copy"><strong>阴阳师</strong><span>PC Script</span></div>
          </div>
          <button class="nav-toggle" type="button" data-action="toggle-nav" data-tooltip="${compact ? '展开导航' : '折叠导航'}" aria-label="${compact ? '展开导航' : '折叠导航'}" aria-expanded="${!compact}">
            ${icon('panel')}<span>${compact ? '展开' : '导航'}</span>
          </button>
          <nav class="nav-list" aria-label="一级导航">
            ${navItems.map(([id, label, iconName]) => `
              <button class="nav-item ${state.view === id ? 'active' : ''}" type="button" data-action="nav" data-view="${id}" data-tooltip="${label}" aria-label="${label}" aria-current="${state.view === id ? 'page' : 'false'}">
                ${icon(iconName)}<span>${label}</span>
              </button>`).join('')}
          </nav>
        </aside>
        <div class="app-column">
          <main class="app-main" id="mainContent" tabindex="-1" aria-labelledby="pageTitle"><h1 id="pageTitle" class="sr-only" tabindex="-1">${escapeHtml({ run: '运行', workflow: '工作流', history: '历史', settings: '设置' }[state.view])}</h1>${renderPage()}</main>
        </div>
      </div>
    </div>`;
}

function renderWindowChrome() {
  return `
    <header class="window-chrome" aria-label="窗口标题栏">
      <div class="window-drag-region" title="阴阳师 PC Script">
        <span class="window-seal" aria-hidden="true">陰</span>
        <span class="window-title">阴阳师 PC Script</span>
        <span class="window-prototype">Prototype · 不代表最终实现</span>
      </div>
      <div class="window-controls" aria-label="窗口控制">
        <button class="window-control" type="button" data-action="window-control" data-window-action="minimize" aria-label="最小化" title="最小化">${icon('minimize')}</button>
        <button class="window-control" type="button" data-action="window-control" data-window-action="toggle-maximize" aria-label="最大化" title="最大化">${icon('maximize')}</button>
        <button class="window-control window-close" type="button" data-action="window-control" data-window-action="close" aria-label="关闭窗口" title="关闭窗口">${icon('close')}</button>
      </div>
    </header>`;
}

function renderPage() {
  if (state.view === 'workflow') return renderWorkflowPage();
  if (state.view === 'history') return renderHistoryPage();
  if (state.view === 'settings') return renderSettingsPage();
  return renderRunPage();
}

function renderRunPage() {
  return `
    <div class="page page-run">
      <div class="run-workspace">
        ${renderRunConfigPanel()}
        <section class="run-execution-panel surface-block" aria-label="执行面板">
          <div class="run-execution-scroll">${renderExecutionPanel()}</div>
        </section>
      </div>
    </div>`;
}

function renderRunConfigPanel() {
  const readOnly = isConfigLocked();
  const dirty = isConfigDirty();
  const hasFieldErrors = Object.keys(state.fieldErrors).length > 0;
  const canSave = !readOnly && state.saveState !== 'saving' && (!state.configCommitted || dirty);
  const canStart = !readOnly && !hasFieldErrors && state.saveState !== 'saving';
  const statusClass = readOnly ? 'locked' : dirty ? 'dirty' : state.configCommitted ? 'saved' : '';
  const statusText = readOnly ? '运行中 · 已锁定' : dirty ? '未保存更改' : state.configCommitted ? '已保存' : '未保存';
  const feedback = state.saveMessage || (readOnly ? '运行中配置已锁定；停止后可修改下一次运行。' : dirty ? '参数会随本次启动使用；保存仅用于保留设置。' : state.configCommitted ? '配置已保存，可直接启动。' : '配置完成后可直接启动，保存是可选的。');
  return `
    <aside class="run-config-panel surface-block" aria-label="脚本配置">
      <div class="run-pane-header">
        <h2>脚本配置</h2>
        <span class="config-summary-state ${statusClass}" role="status">${statusText}</span>
      </div>
      <div class="run-config-scroll">${renderConfigFields(readOnly)}</div>
      <div class="run-pane-actions">
        <span class="run-pane-hint ${state.saveState === 'error' ? 'is-error' : ''}" role="status" aria-live="polite">${escapeHtml(feedback)}</span>
        <div class="action-row">
          <button class="button quiet" type="button" data-action="${dirty ? 'config-cancel' : 'config-reset'}"${readOnly ? ' disabled' : ''}>${dirty ? '取消修改' : '恢复默认'}</button>
          <button class="button quiet ${canSave ? '' : 'is-disabled'}" type="button" data-action="config-save"${canSave ? '' : ' disabled'}>${state.saveState === 'saving' ? '保存中…' : '保存配置'}</button>
          <button class="button primary ${canStart ? '' : 'is-disabled'}" type="button" data-action="execute"${canStart ? '' : ' disabled'}>${icon('play')}启动</button>
        </div>
      </div>
    </aside>`;
}

function renderExecutionPanel() {
  const run = state.currentRun;
  if (run.status === 'idle') return `${renderEmptyState()}${renderLegacySlot()}`;
  if (run.status === 'configured') return `${renderConfiguredState()}${renderLegacySlot()}`;
  return `<section class="execution-content" aria-live="polite" aria-atomic="false">
    ${renderExecutionHeading(run)}
    ${renderProgressBlock(run)}
    ${run.status === 'error' ? renderRunError(run) : ''}
    ${renderMetricStrip(run)}
    ${renderRunActionGroup(run)}
    ${renderDetailTrigger(run)}
    ${renderTimeline(run)}
    ${renderLegacySlot()}
  </section>`;
}

function renderEmptyState() {
  return `<section class="execution-empty" aria-live="polite"><span class="empty-mark" aria-hidden="true">陰</span><h2>还没有运行</h2><p>从左侧选择脚本，配置完成后即可启动。</p></section>`;
}

function renderConfiguredState() {
  return `<section class="execution-configured" aria-live="polite"><span class="configured-mark" aria-hidden="true">✓</span><div><h2>配置已保存</h2><p>${escapeHtml(state.currentRun.title)} 已准备好，启动操作位于左侧。</p></div><span class="state-label state-configured"><i aria-hidden="true"></i>已保存</span></section>`;
}

function renderExecutionHeading(run) {
  return `<div class="detail-heading"><div><h2>${escapeHtml(run.title)}</h2><p>${escapeHtml(stageLabel(run.stage))}</p></div><span class="state-label state-${escapeHtml(run.status)}"><i aria-hidden="true"></i>${escapeHtml(statusLabel(run.status))}</span></div>`;
}

function renderProgressBlock(run) {
  const total = Math.max(1, Number(run.total) || 1);
  const count = Math.max(0, Math.min(total, Number(run.count) || 0));
  const progress = Math.max(0, Math.min(100, Number(run.progress) || 0));
  return `<div class="run-progress-large">
    <div class="progress-meta"><span>整体进度</span><strong>${progress}%</strong></div>
    <div class="progress-track" role="progressbar" aria-label="运行进度" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${count}" aria-valuetext="${count} / ${total} 场，${progress}%"><span style="width:${progress}%"></span></div>
    <div class="progress-foot"><span>第 ${count} / ${total} 场</span><span>${escapeHtml(stageLabel(run.stage))}</span></div>
  </div>`;
}

function renderMetricStrip(run) {
  return `<div class="metric-strip"><div><span>已运行</span><b>${escapeHtml(run.elapsed)}</b></div><div><span>运行来源</span><b>${escapeHtml(run.source)}</b></div><div><span>当前脚本</span><b>${escapeHtml(run.title)}</b></div></div>`;
}

function renderRunActionGroup(run) {
  const actions = Array.isArray(run.available_actions) ? run.available_actions : [];
  if (!actions.length) return '';
  return `<div class="run-action-group"><span class="action-group-title">运行操作</span><div class="action-row">${actions.map(renderActionButton).join('')}</div></div>`;
}

function renderActionButton(action) {
  const meta = actionMeta[action];
  if (!meta) return '';
  return `<button class="button ${meta.className}" type="button" data-action="run-action" data-run-action="${action}">${icon(meta.icon)}<span>${meta.label}</span></button>`;
}

function renderRunError(run) {
  return `<div class="run-error" role="alert"><div><strong>运行未完成</strong><span>${escapeHtml(run.error_code || 'SCRIPT_FAILED')}</span></div><p>${escapeHtml(run.error_message || '脚本在执行过程中返回失败，请选择恢复操作。')}</p></div>`;
}

function renderDetailTrigger(run) {
  if (run.status === 'idle' || run.status === 'configured') return '';
  return `<div class="execution-secondary-actions"><button class="button quiet run-detail-trigger" type="button" data-action="progress">查看详细进度</button></div>`;
}

function renderTimeline(run) {
  if (!run.events?.length) return '';
  return `<div class="timeline" aria-label="运行记录">${run.events.map((event) => `<div class="timeline-item"><span class="timeline-time">${escapeHtml(event.time)}</span><span class="timeline-marker ${escapeHtml(event.kind || 'neutral')}" aria-hidden="true"></span><div><b>${escapeHtml(event.title)}</b><p>${escapeHtml(event.text)}</p></div></div>`).join('')}</div>`;
}

function renderLegacySlot() {
  return `<section class="legacy-slot" aria-label="旧版业务内容占位区"><div class="legacy-heading"><span class="stamp-small" aria-hidden="true">旧</span><div><h3>原有业务内容</h3><span>任务卡与实时日志</span></div></div><div class="legacy-content"><p>${escapeHtml(state.currentRun.title)} · ${escapeHtml(stageLabel(state.currentRun.stage))}</p><button class="link-button" type="button" data-action="legacy">打开详情 ${icon('arrow-right')}</button></div></section>`;
}

function renderWorkflowPage() {
  const names = ['御魂·日常', '探索·第 28 章', '狭间暗域'];
  const rows = names.map((name, index) => `<button type="button" class="workflow-a-row ${index === 0 ? 'selected' : ''}" data-action="legacy"><span class="workflow-dot ${index === 0 ? 'on' : ''}" aria-hidden="true"></span><b>${name}</b><small>${index === 0 ? '已启用 · 3 步' : '草稿 · 2 步'}</small></button>`).join('');
  return `<div class="page generic-page workflow-page"><section class="page-command"><div><h2>工作流</h2><p>把重复任务整理成可复用的本地步骤。</p></div><button class="button primary" type="button" data-action="workflow-add">${icon('plus')}新建工作流</button></section><div class="workflow-a-layout"><div class="workflow-a-list"><h3>工作流列表</h3>${rows}</div><div class="workflow-a-detail"><span class="stamp-small" aria-hidden="true">流</span><h3>御魂·日常</h3><p>按顺序执行队伍准备、御魂战斗和结算检查。</p><div class="step-row"><span>01</span><b>队伍准备</b><span>已配置</span></div><div class="step-row"><span>02</span><b>御魂战斗</b><span>已配置</span></div><div class="step-row"><span>03</span><b>结算检查</b><span>已配置</span></div></div></div></div>`;
}

function renderHistoryPage() {
  const rows = historyRows.map(([name, status, count, time, kind]) => `<button class="history-row" type="button" data-action="legacy"><span><b>${escapeHtml(name)}</b><small>${escapeHtml(time)}</small></span><span class="history-status ${kind}"><i aria-hidden="true"></i>${escapeHtml(status)}</span><span>${escapeHtml(count)}</span>${icon('chevron')}</button>`).join('');
  return `<div class="page generic-page history-page"><section class="page-command"><div><h2>历史</h2><p>回看过去的运行结果和接管节点。</p></div><span class="record-count">共 18 条记录</span></section><div class="history-a-panel"><div class="history-a-toolbar"><h3>最近运行</h3><button class="button quiet" type="button" data-action="legacy">${icon('refresh')}刷新</button></div>${rows}</div></div>`;
}

function renderSettingsPage() {
  return `<div class="page generic-page settings-page"><section class="page-command"><div><h2>设置</h2><p>主题、导航和窗口尺寸可即时预览。</p></div></section><div class="settings-grid"><section class="settings-section"><div class="settings-section-head"><h3>外观</h3><p>默认浅色，选择会保存在本地。</p></div><div class="setting-row"><span><b>主题</b><small>${state.theme === 'dark' ? '当前为深色' : '当前为浅色'}</small></span><button class="button quiet" type="button" data-action="theme">${state.theme === 'dark' ? '切换浅色' : '切换深色'}</button></div><div class="setting-row"><span><b>导航状态</b><small>800×600 自动图标化，宽屏可手动折叠。</small></span><button class="button quiet" type="button" data-action="toggle-nav">${isCompactNavigation() ? '当前折叠' : '当前展开'}</button></div></section><section class="settings-section"><div class="settings-section-head"><h3>窗口预览</h3><p>检查三个桌面端验收尺寸。</p></div>${renderSizeControls()}</section><section class="settings-section state-preview-section"><div class="settings-section-head"><h3>运行状态演示</h3><p>用于评审不同运行权限和空、错、终态。</p></div><div class="state-preview-grid">${statePreviewOptions.map(([key, label]) => `<button class="state-preview-button ${state.currentRun.status === (key === 'running-prep' || key === 'running' || key === 'waiting-timeout' ? 'running' : key) ? 'active' : ''}" type="button" data-action="simulate-status" data-status-key="${key}" aria-pressed="${state.currentRun.status === key}">${label}</button>`).join('')}</div><button class="button quiet simulate-error-button" type="button" data-action="simulate-save-error">${state.simulateSaveFailure ? '下次保存将模拟失败' : '模拟下一次保存失败'}</button></section></div></div>`;
}

function renderSizeControls() {
  return `<div class="size-controls">${['800x600', '900x650', '1280x720'].map((size) => `<button class="size-button ${state.viewportPreset === size ? 'active' : ''}" type="button" data-action="viewport" data-size="${size}" aria-pressed="${state.viewportPreset === size}"><b>${size.replace('x', ' × ')}</b><small>${size === '800x600' ? '图标导航 · 单列' : size === '900x650' ? '默认窗口 · 双列' : '宽工作区'}</small></button>`).join('')}</div>`;
}

function renderDetailModal() {
  if (!state.detailOpen) return '';
  const run = state.currentRun;
  return `<div class="modal-backdrop"><section class="detail-modal" role="dialog" aria-modal="true" aria-labelledby="detailModalTitle" aria-describedby="detailModalDescription"><div class="modal-head"><div><h2 id="detailModalTitle">详细进度</h2><p id="detailModalDescription">${escapeHtml(run.title)} · ${escapeHtml(statusLabel(run.status))}</p></div><button class="icon-button" type="button" data-action="close-detail" aria-label="关闭详细进度">${icon('close')}</button></div><div class="modal-run-summary"><span class="stamp-small" aria-hidden="true">御</span><div><b>${escapeHtml(run.title)}</b><span>${escapeHtml(stageLabel(run.stage))} · ${run.progress}%</span></div><span class="state-label state-${escapeHtml(run.status)}"><i aria-hidden="true"></i>${escapeHtml(statusLabel(run.status))}</span></div>${renderTimeline(run) || '<p class="modal-empty">暂无可展示的详细记录。</p>'}<div class="modal-footer"><button class="button quiet" type="button" data-action="close-detail">返回运行页</button></div></section></div>`;
}

function fieldAttrs(key, readOnly) {
  const disabled = readOnly || state.saveState === 'saving';
  const error = state.fieldErrors[key];
  return `${disabled ? ' disabled' : ''}${error ? ' aria-invalid="true" aria-describedby="help-' + key + ' error-' + key + '"' : ' aria-describedby="help-' + key + '"'}`;
}

function fieldNote(key, text) {
  const error = state.fieldErrors[key];
  return `<small id="help-${key}" class="field-note">${escapeHtml(text)}</small>${error ? `<small id="error-${key}" class="field-error" role="alert">${escapeHtml(error)}</small>` : ''}`;
}

function renderNumberField(key, label, value, description, min, max, step, readOnly) {
  return `<label class="config-field ${state.fieldErrors[key] ? 'has-error' : ''}"><span>${label}</span><input data-config-field="${key}" type="number" min="${min}" max="${max}" step="${step}" value="${escapeHtml(value)}"${fieldAttrs(key, readOnly)}>${fieldNote(key, description)}</label>`;
}

function renderSelectField(key, label, value, options, description, readOnly) {
  return `<label class="config-field ${state.fieldErrors[key] ? 'has-error' : ''}"><span>${label}</span><select data-config-field="${key}"${fieldAttrs(key, readOnly)}>${options.map(([optionValue, optionLabel]) => `<option value="${escapeHtml(optionValue)}" ${String(value) === String(optionValue) ? 'selected' : ''}>${escapeHtml(optionLabel)}</option>`).join('')}</select>${fieldNote(key, description)}</label>`;
}

function renderToggleField(key, label, checked, description, readOnly) {
  return `<label class="toggle-field ${state.fieldErrors[key] ? 'has-error' : ''}"><input data-config-field="${key}" type="checkbox" ${checked ? 'checked' : ''}${fieldAttrs(key, readOnly)}><span><b>${label}</b>${fieldNote(key, description)}</span></label>`;
}

function renderConfigFields(readOnly = false) {
  const config = state.configDraft;
  const isAbyss = config.script === 'abyss_shadows';
  const isExploration = config.script === 'exploration';
  return `
    <div class="config-selected-script"><span class="stamp-small" aria-hidden="true">配</span><div><b>${escapeHtml(getScriptTitle(config.script))}</b><span>${readOnly ? '运行中只读，停止后可修改。' : '可直接启动，运行中会自动锁定。'}</span></div></div>
    ${renderSelectField('script', '运行脚本', config.script, scriptOptions, '选择要运行的脚本。', readOnly)}
    <section class="config-section"><div class="config-section-head"><h3>通用参数</h3><p>运行次数和失败处理方式。</p></div><div class="config-grid">${renderNumberField('battleCount', '战斗次数', config.battleCount, '1–100 场', 1, 100, 1, readOnly)}${renderSelectField('failurePolicy', '失败策略', config.failurePolicy, [['stop_workflow', '失败后停止'], ['continue_next', '失败后继续下一步'], ['retry_then_stop', '重试后停止']], '失败时的流程处理方式。', readOnly)}</div><div class="config-toggles">${renderToggleField('manualTakeover', '允许人工接管', config.manualTakeover, '保留人工处理入口。', readOnly)}${renderToggleField('evidenceCapture', '保留截图证据', config.evidenceCapture, '失败节点保留证据快照。', readOnly)}</div></section>
    ${isAbyss ? `<section class="config-section config-section-accent"><div class="config-section-head"><h3>狭间暗域</h3><p>首领、副将和精英目标的次数与伤害限制。</p></div><div class="config-grid">${renderNumberField('bossCount', '首领次数', config.bossCount, '0–99 次', 0, 99, 1, readOnly)}${renderNumberField('bossDamageLimit', '首领伤害限制', config.bossDamageLimit, '达到阈值后停止当前目标。', 0, 999999999, 1000, readOnly)}${renderNumberField('commanderCount', '副将次数', config.commanderCount, '0–99 次', 0, 99, 1, readOnly)}${renderNumberField('eliteCount', '精英次数', config.eliteCount, '0–99 次', 0, 99, 1, readOnly)}${renderSelectField('damageMode', '伤害策略', config.damageMode, [['达到上限后停止', '达到上限后停止'], ['仅记录不停止', '仅记录不停止']], '达到限制时的处理方式。', readOnly)}${renderSelectField('targetArea', '目标暗域', config.targetArea, [['孔雀', '孔雀'], ['豹', '豹'], ['狐', '狐'], ['龙', '龙']], '选择目标暗域。', readOnly)}</div>${renderToggleField('leaderMode', '队长模式', config.leaderMode, '以当前账号作为队长。', readOnly)}</section>` : isExploration ? `<section class="config-section"><div class="config-section-head"><h3>探索</h3><p>章节和推进方式。</p></div><div class="config-grid">${renderSelectField('chapter', '章节', config.chapter, [['第 28 章', '第 28 章'], ['第 27 章', '第 27 章']], '选择探索章节。', readOnly)}</div>${renderToggleField('autoAdvance', '自动推进章节', config.autoAdvance, '完成当前章节后继续探索。', readOnly)}</section>` : `<section class="config-section"><div class="config-section-head"><h3>御魂</h3><p>难度和队伍选择。</p></div><div class="config-grid">${renderSelectField('soulLevel', '御魂难度', config.soulLevel, [['御魂·悲鸣', '御魂·悲鸣'], ['御魂·神罚', '御魂·神罚']], '选择御魂难度。', readOnly)}${renderSelectField('teamSlot', '队伍', config.teamSlot, [['队伍 1', '队伍 1'], ['队伍 2', '队伍 2']], '选择执行队伍。', readOnly)}</div></section>`}
  `;
}

function setTheme(theme) {
  state.theme = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.dataset.theme = state.theme;
  window.localStorage.setItem('yys-prototype-theme', state.theme);
  render();
  showToast(state.theme === 'dark' ? '已切换深色主题' : '已切换浅色主题');
}

function setConfiguredRun() {
  const total = Math.max(1, Math.min(100, Number(state.configDraft.battleCount) || 10));
  state.currentRun = {
    ...createRun(state.configDraft.script),
    title: getScriptTitle(state.configDraft.script),
    total,
    status: 'configured',
    stage: 'configured',
    source: '手动启动'
  };
}

function appendRunEvent(title, text, kind = 'neutral') {
  state.currentRun.events = [{ time: '刚刚', title, text, kind }, ...(state.currentRun.events || [])];
}

function startSimulation() {
  if (isConfigLocked()) return;
  const errors = validateConfig();
  state.fieldErrors = errors;
  if (Object.keys(errors).length) {
    state.saveState = 'error';
    state.saveMessage = '请修正标红字段后再启动。';
    state.focusAfterRender = `[data-config-field="${Object.keys(errors)[0]}"]`;
    render();
    showToast('配置校验失败，请检查标红字段', 'error');
    return;
  }
  const total = Math.max(1, Math.min(100, Number(state.configDraft.battleCount) || 10));
  const count = Math.min(1, total);
  state.currentRun = {
    ...createRun(state.configDraft.script),
    title: getScriptTitle(state.configDraft.script),
    count,
    total,
    progress: Math.round((count / total) * 100),
    status: 'running',
    stage: 'script_running',
    elapsed: '00:00:08',
    source: '手动启动',
    available_actions: ['pause', 'stop'],
    events: [
      { time: '刚刚', title: '进入脚本运行', text: '任务已经启动，配置保持锁定。', kind: 'ok' },
      { time: '刚刚', title: '启动任务', text: `${getScriptTitle(state.configDraft.script)} · 手动启动`, kind: 'neutral' }
    ]
  };
  state.detailOpen = false;
  state.view = 'run';
  state.focusAfterRender = '#pageTitle';
  render();
  showToast(`已启动${getScriptTitle(state.configDraft.script)}，运行中配置已锁定`);
}

function validateConfig() {
  const config = state.configDraft;
  const errors = {};
  const numberRules = [
    ['battleCount', '战斗次数', 1, 100],
    ['bossCount', '首领次数', 0, 99],
    ['bossDamageLimit', '首领伤害限制', 0, 999999999],
    ['commanderCount', '副将次数', 0, 99],
    ['eliteCount', '精英次数', 0, 99]
  ];
  numberRules.forEach(([key, label, min, max]) => {
    if (config[key] === undefined) return;
    const value = Number(config[key]);
    if (!Number.isInteger(value) || value < min || value > max) errors[key] = `${label}需为 ${min}–${max} 的整数。`;
  });
  if (!['stop_workflow', 'continue_next', 'retry_then_stop'].includes(config.failurePolicy)) errors.failurePolicy = '请选择有效的失败策略。';
  return errors;
}

function saveConfig() {
  if (isConfigLocked() || state.saveState === 'saving') return;
  const errors = validateConfig();
  state.fieldErrors = errors;
  if (Object.keys(errors).length) {
    state.saveState = 'error';
    state.saveMessage = '请修正标红字段后再保存。';
    state.focusAfterRender = `[data-config-field="${Object.keys(errors)[0]}"]`;
    render();
    showToast('配置校验失败，请检查标红字段', 'error');
    return;
  }
  state.saveState = 'saving';
  state.saveMessage = '正在保存到本地…';
  render();
  window.setTimeout(() => {
    if (state.simulateSaveFailure) {
      state.simulateSaveFailure = false;
      state.saveState = 'error';
      state.saveMessage = '保存失败，请重试。';
      render();
      showToast('模拟保存失败，请重试', 'error');
      return;
    }
    state.configBaseline = cloneConfig(state.configDraft);
    state.configCommitted = true;
    state.saveState = 'success';
    state.saveMessage = '配置已保存，可直接启动。';
    setConfiguredRun();
    render();
    showToast(`已保存${getScriptTitle()}配置`);
  }, 320);
}

function cancelConfig() {
  if (isConfigLocked()) return;
  state.configDraft = cloneConfig(state.configBaseline);
  state.fieldErrors = {};
  state.saveState = 'idle';
  state.saveMessage = '';
  if (state.configCommitted) setConfiguredRun();
  else state.currentRun = createRun(state.configDraft.script);
  render();
  showToast('已取消未保存修改');
}

function resetConfig() {
  if (isConfigLocked()) return;
  state.configDraft = createScriptConfig(state.configDraft.script);
  state.configCommitted = false;
  state.fieldErrors = {};
  state.saveState = 'idle';
  state.saveMessage = '默认值已恢复，可直接启动；保存是可选的。';
  state.currentRun = createRun(state.configDraft.script);
  render();
  showToast('已恢复默认配置');
}

function applyRunAction(action) {
  if (!state.currentRun.available_actions.includes(action)) return;
  const title = getScriptTitle(state.configDraft.script);
  if (action === 'stop') {
    state.currentRun.status = 'stopped';
    state.currentRun.stage = 'stopped';
    state.currentRun.available_actions = [];
    appendRunEvent('运行已停止', '用户请求停止当前任务。');
    showToast('运行已停止');
  } else if (action === 'pause') {
    state.currentRun.status = 'paused';
    state.currentRun.stage = 'paused';
    state.currentRun.available_actions = ['resume', 'stop'];
    appendRunEvent('运行已暂停', '当前任务等待恢复。');
    showToast('运行已暂停');
  } else if (action === 'resume') {
    state.currentRun.status = 'running';
    state.currentRun.stage = 'script_running';
    state.currentRun.available_actions = ['pause', 'stop'];
    appendRunEvent('运行已恢复', '任务继续执行。', 'ok');
    showToast('运行已恢复');
  } else if (action === 'continue_waiting') {
    state.currentRun.status = 'running';
    state.currentRun.stage = 'waiting_safe_entry';
    state.currentRun.available_actions = ['stop'];
    appendRunEvent('继续等待', '继续等待安全进入窗口。');
    showToast('已继续等待');
  } else if (action === 'retry') {
    state.currentRun = {
      ...createRun(state.configDraft.script),
      title,
      count: 1,
      total: Math.max(1, Number(state.configDraft.battleCount) || 10),
      progress: 10,
      status: 'running',
      stage: 'script_running',
      elapsed: '00:00:03',
      source: '关联重试',
      available_actions: ['pause', 'stop'],
      events: [{ time: '刚刚', title: '关联重试已启动', text: `${title} · 重新执行`, kind: 'ok' }]
    };
    showToast('已启动关联重试');
  } else if (action === 'skip') {
    state.currentRun.status = 'skipped';
    state.currentRun.stage = 'skipped';
    state.currentRun.available_actions = [];
    appendRunEvent('已跳过', '当前失败运行已跳过。');
    showToast('已跳过当前运行');
  } else if (action === 'manual_takeover') {
    state.currentRun.status = 'manual';
    state.currentRun.stage = 'manual_takeover';
    state.currentRun.available_actions = ['retry'];
    appendRunEvent('进入人工接管', '等待人工处理当前任务。');
    showToast('已进入人工接管');
  }
  render();
}

function createDemoRun(key) {
  const script = state.configDraft.script;
  const total = Math.max(1, Number(state.configDraft.battleCount) || 10);
  const base = { ...createRun(script), title: getScriptTitle(script), total, source: '状态演示' };
  if (key === 'configured') return { ...base, status: 'configured', stage: 'configured', source: '手动启动' };
  if (key === 'queued') return { ...base, status: 'queued', stage: 'queued', available_actions: ['stop'], events: [{ time: '刚刚', title: '进入队列', text: '任务等待执行。', kind: 'neutral' }] };
  if (key === 'running-prep') return { ...base, status: 'running', stage: 'preparing', count: 0, progress: 0, elapsed: '00:00:02', available_actions: ['stop'], events: [{ time: '刚刚', title: '准备运行环境', text: '正在确认任务入口。', kind: 'neutral' }] };
  if (key === 'running') return { ...base, status: 'running', stage: 'script_running', count: Math.min(3, total), progress: Math.round((Math.min(3, total) / total) * 100), elapsed: '00:02:18', available_actions: ['pause', 'stop'], events: [{ time: '刚刚', title: '脚本运行中', text: '已识别当前战斗并进入自动操作。', kind: 'ok' }] };
  if (key === 'waiting-timeout') return { ...base, status: 'running', stage: 'waiting_safe_entry_timeout', count: 0, progress: 0, elapsed: '00:00:42', available_actions: ['continue_waiting', 'manual_takeover', 'stop'], events: [{ time: '刚刚', title: '安全进入等待超时', text: '可以继续等待、人工接管或停止。', kind: 'neutral' }] };
  if (key === 'paused') return { ...base, status: 'paused', stage: 'paused', count: Math.min(3, total), progress: Math.round((Math.min(3, total) / total) * 100), elapsed: '00:02:18', available_actions: ['resume', 'stop'], events: [{ time: '刚刚', title: '运行已暂停', text: '任务等待恢复。', kind: 'neutral' }] };
  if (key === 'error') return { ...base, status: 'error', stage: 'script_failed', count: Math.min(3, total), progress: Math.round((Math.min(3, total) / total) * 100), elapsed: '00:01:36', error_code: 'SCRIPT_FAILED', error_message: '模拟脚本在识别结算页面时失败。请选择重试、跳过、停止或人工接管。', available_actions: ['retry', 'skip', 'stop', 'manual_takeover'], events: [{ time: '刚刚', title: '执行失败', text: '识别结算页面失败。', kind: 'error' }] };
  if (key === 'manual') return { ...base, status: 'manual', stage: 'manual_takeover', count: Math.min(3, total), progress: Math.round((Math.min(3, total) / total) * 100), elapsed: '00:01:36', available_actions: ['retry'], events: [{ time: '刚刚', title: '人工接管', text: '等待人工处理后重试。', kind: 'neutral' }] };
  if (key === 'success') return { ...base, status: 'success', stage: 'completed', count: total, progress: 100, elapsed: '00:08:42', events: [{ time: '刚刚', title: '运行完成', text: `已完成 ${total} 场任务。`, kind: 'ok' }] };
  if (key === 'stopped') return { ...base, status: 'stopped', stage: 'stopped', count: Math.min(3, total), progress: Math.round((Math.min(3, total) / total) * 100), elapsed: '00:02:18', events: [{ time: '刚刚', title: '运行已停止', text: '任务等待下一次启动。', kind: 'neutral' }] };
  return createRun(script);
}

function showToast(message, kind = 'status') {
  const region = document.getElementById('toastRegion');
  if (!region) return;
  region.replaceChildren();
  const toast = document.createElement('div');
  toast.className = `toast ${kind === 'error' ? 'is-error' : ''}`;
  toast.setAttribute('role', kind === 'error' ? 'alert' : 'status');
  toast.textContent = message;
  region.appendChild(toast);
  window.setTimeout(() => toast.remove(), 2600);
}

function updateMaximizeControl(maximized) {
  const control = document.querySelector('[data-window-action="toggle-maximize"]');
  if (!control) return;
  control.setAttribute('aria-label', maximized ? '还原窗口' : '最大化');
  control.setAttribute('title', maximized ? '还原窗口' : '最大化');
  control.innerHTML = icon(maximized ? 'restore' : 'maximize');
}

async function handleWindowControl(action) {
  if (!window.prototypeWindow?.action) return;
  const result = await window.prototypeWindow.action(action);
  if (result && typeof result.maximized === 'boolean') updateMaximizeControl(result.maximized);
  if (action === 'toggle-maximize') {
    window.setTimeout(() => window.prototypeWindow.isMaximized().then(updateMaximizeControl), 120);
  }
}

function setViewport(size) {
  state.viewportPreset = size;
  render();
  if (window.prototypeWindow?.resize) window.prototypeWindow.resize(size);
  showToast(`已切换预览尺寸 ${size.replace('x', ' × ')}`);
}

function closeDetailModal() {
  const returnFocus = state.modalReturnFocus || '#mainContent';
  state.detailOpen = false;
  state.modalReturnFocus = '#mainContent';
  state.focusAfterRender = returnFocus;
  render();
}

function openDetailModal() {
  state.modalReturnFocus = document.activeElement?.closest('.run-detail-trigger') ? '.run-detail-trigger' : '#mainContent';
  state.detailOpen = true;
  render();
  window.requestAnimationFrame(() => document.querySelector('.detail-modal [data-action="close-detail"]')?.focus());
}

function handleClick(event) {
  const control = event.target.closest('[data-action]');
  if (!control) return;
  const action = control.dataset.action;
  if (action === 'nav') {
    state.view = control.dataset.view;
    state.detailOpen = false;
    state.focusAfterRender = '#pageTitle';
    render();
    return;
  }
  if (action === 'toggle-nav') {
    if (window.innerWidth <= 840) {
      state.navMode = 'compact';
      render();
      showToast('800×600 下导航保持图标模式');
    } else {
      state.navMode = state.navMode === 'compact' ? 'expanded' : 'compact';
      render();
      showToast(state.navMode === 'compact' ? '导航已折叠' : '导航已展开');
    }
    return;
  }
  if (action === 'theme') return setTheme(state.theme === 'dark' ? 'light' : 'dark');
  if (action === 'window-control') return handleWindowControl(control.dataset.windowAction);
  if (action === 'config-save') return saveConfig();
  if (action === 'config-cancel') return cancelConfig();
  if (action === 'config-reset') return resetConfig();
  if (action === 'execute') return startSimulation();
  if (action === 'run-action') return applyRunAction(control.dataset.runAction);
  if (action === 'progress') return openDetailModal();
  if (action === 'close-detail') {
    if (control.classList.contains('modal-backdrop') && event.target !== control) return;
    return closeDetailModal();
  }
  if (action === 'simulate-status') {
    state.currentRun = createDemoRun(control.dataset.statusKey);
    state.view = 'run';
    state.detailOpen = false;
    state.focusAfterRender = '#pageTitle';
    render();
    showToast(`已切换到“${control.textContent.trim()}”状态`);
    return;
  }
  if (action === 'simulate-save-error') {
    state.simulateSaveFailure = true;
    showToast('下一次保存将展示失败反馈');
    render();
    return;
  }
  if (action === 'legacy') {
    showToast('已打开原有业务内容');
    return;
  }
  if (action === 'workflow-add') {
    showToast('新建工作流入口已打开');
    return;
  }
  if (action === 'viewport') return setViewport(control.dataset.size);
}

function handleConfigField(event) {
  if (isConfigLocked() || state.saveState === 'saving') return;
  const field = event.target.closest('[data-config-field]');
  if (!field) return;
  const key = field.dataset.configField;
  const value = field.type === 'checkbox' ? field.checked : field.type === 'number' ? Number(field.value) : field.value;
  if (key === 'script') {
    const previous = state.configDraft;
    state.configDraft = createScriptConfig(value);
    state.configDraft.battleCount = previous.battleCount;
    state.configDraft.failurePolicy = previous.failurePolicy;
    state.configDraft.manualTakeover = previous.manualTakeover;
    state.configDraft.evidenceCapture = previous.evidenceCapture;
  } else {
    state.configDraft[key] = value;
  }
  delete state.fieldErrors[key];
  state.configCommitted = false;
  state.saveState = 'idle';
  state.saveMessage = '';
  state.currentRun = createRun(state.configDraft.script);
  render();
}

function handleKeydown(event) {
  if (!state.detailOpen) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    closeDetailModal();
    return;
  }
  if (event.key !== 'Tab') return;
  const modal = document.querySelector('.detail-modal');
  if (!modal) return;
  const focusables = [...modal.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])')];
  if (!focusables.length) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

document.addEventListener('click', handleClick);
document.addEventListener('input', handleConfigField);
document.addEventListener('change', handleConfigField);
document.addEventListener('keydown', handleKeydown);
document.addEventListener('dblclick', (event) => {
  if (event.target.closest('.window-drag-region')) handleWindowControl('toggle-maximize');
});

let resizeTimer;
window.addEventListener('resize', () => {
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(render, 100);
});

render();
if (window.prototypeWindow?.isMaximized) window.prototypeWindow.isMaximized().then(updateMaximizeControl);
window.prototypeWindow?.onStateChange?.((windowState) => updateMaximizeControl(Boolean(windowState?.maximized)));
