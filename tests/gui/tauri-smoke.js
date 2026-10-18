// 产品契约：AC10/12/13/14，在真实 WebView2 中验证官方 IPC 和资源。
(async () => {
  const checks = [];
  const check = (condition, label) => { if (!condition) throw new Error(label); checks.push(label); };
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const post = (path, body) => fetch(smokeEndpoint + path, { method: 'POST', headers: { 'X-YYS-UI-Token': smokeToken }, body: JSON.stringify(body) });
  try {
    check(location.origin === 'http://tauri.localhost', '生产页面来源');
    check(Boolean(window.Cropper), '裁剪器资源加载');
    const bridge = window.desktopBridge;
    const bootstrap = await bridge.bootstrap();
    check(bootstrap.ready && bootstrap.apiBase === smokeEndpoint && bootstrap.token === smokeToken, '受限握手');
    const messages = new Set();
    for (let i = 0; i < 100 && !document.getElementById('historyList').textContent.includes('暂无'); i++) {
      messages.add(document.getElementById('toastRegion').textContent);
      await wait(100);
    }
    check(document.getElementById('historyList').textContent.includes('暂无'), 'renderer 完成假后端初始化：' + [...messages].join(' '));
    for (const [command, args] of [['unknown_command', {}], ['window_action', {action: 'execute'}], ['window_action', {action: 12}], ['plugin:shell|execute', {program: 'cmd.exe'}]]) {
      let denied = false;
      try { await window.__TAURI__.core.invoke(command, args); } catch { denied = true; }
      check(denied, `拒绝 ${command}/${args.action || ''}`);
    }
    check(!(await bridge.openImageResourceDirectory('../escape.png')).opened, '拒绝路径穿越');
    check(!(await bridge.openImageResourceDirectory('yys/unknown.png')).opened, '拒绝未知资源');
    const resourceId = await (await fetch(smokeEndpoint + '/smoke/resource', {headers: {'X-YYS-UI-Token': smokeToken}})).json();
    check((await bridge.openImageResourceDirectory(resourceId)).opened, '已知图片覆盖目录');
    check((await bridge.openScreenshotDirectory()).opened, '受限截图库目录');
    let changes = 0;
    const cleanup = bridge.onWindowState(() => changes++);
    await wait(100);
    await bridge.windowAction('toggle-maximize');
    await wait(150);
    check(await bridge.isMaximized(), '最大化');
    await bridge.windowAction('toggle-maximize');
    await wait(150);
    check(!(await bridge.isMaximized()) && changes > 0, '恢复窗口和定向状态事件');
    cleanup();
    const previous = changes;
    await bridge.windowAction('close');
    await bridge.restoreGuiFocus();
    await wait(100);
    check(changes === previous, '监听清理后不再回调');
    await bridge.windowAction('minimize');
    check(await bridge.restoreGuiFocus(), '最小化与焦点恢复');
    const tray = [];
    const stop = bridge.onTrayCommand((command) => tray.push(command));
    await wait(100);
    await post('/smoke/tray', {});
    for (let i = 0; i < 30 && tray.length < 2; i++) await wait(100);
    stop();
    check(tray.join(',') === 'pause,stop', '托盘暂停停止定向事件');
    // 产品契约：AC13，页面只能停留在受控首页，外部导航和新窗口都必须被拒绝。
    const pageUrl = location.href;
    try { location.assign(smokeEndpoint + '/evil'); } catch { /* 同步拒绝也算通过 */ }
    await wait(300);
    check(location.href === pageUrl && Boolean(document.getElementById('historyList')), '拒绝外部导航');
    check(!window.open(smokeEndpoint + '/evil', '_blank'), '拒绝新窗口');
    check(!location.search.includes('token'), 'URL 不携带 token');
    await post('/smoke/report', {ok: true, checks});
  } catch (error) {
    await post('/smoke/report', {ok: false, checks, error: String(error)});
  }
})();
