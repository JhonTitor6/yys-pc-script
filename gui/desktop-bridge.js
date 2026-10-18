(() => {
  if (window.desktopBridge || !window.__TAURI__) return;
  const { invoke } = window.__TAURI__.core;
  const { listen } = window.__TAURI__.event;
  // 保留同步返回清理函数的契约，处理订阅尚未完成就被清理的竞态。
  const subscribe = (event, callback) => {
    let disposed = false;
    let unlisten;
    listen(event, ({ payload }) => { if (!disposed) callback(payload); }, { target: { kind: 'WebviewWindow', label: 'main' } })
      .then((cleanup) => { if (disposed) cleanup(); else unlisten = cleanup; })
      .catch((error) => { if (!disposed) console.error('桌面事件订阅失败', error); });
    return () => { if (!disposed) { disposed = true; unlisten?.(); } };
  };
  const windowAction = (action) => invoke('window_action', { action });
  window.desktopBridge = Object.freeze({
    bootstrap: () => invoke('desktop_bootstrap'),
    windowAction,
    minimizeWindow: () => windowAction('minimize'),
    maximizeWindow: () => windowAction('toggle-maximize'),
    closeWindow: () => windowAction('close'),
    isMaximized: () => invoke('is_maximized'),
    restoreGuiFocus: () => invoke('restore_gui_focus'),
    openScreenshotDirectory: () => invoke('open_screenshot_directory'),
    openImageResourceDirectory: (resourceId) => invoke('open_image_resource_directory', { resourceId }),
    onTrayCommand: (callback) => subscribe('tray-command', callback),
    onWindowState: (callback) => subscribe('window-state', callback)
  });
  document.addEventListener('mousedown', (event) => {
    if (event.button === 0 && event.target.closest('[data-drag-region]')) {
      windowAction(event.detail === 2 ? 'toggle-maximize' : 'drag').catch(console.error);
    }
  });
})();
