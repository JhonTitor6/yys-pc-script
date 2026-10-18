const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../gui/desktop-bridge.js'), 'utf8');

async function main() {
  // 产品契约：阶段1/AC14，旧 renderer 清理函数同步返回，重复挂载不能遗留监听。
  const listeners = new Set();
  const pending = [];
  const calls = [];
  const handlers = {};
  const context = {
    window: { __TAURI__: {
      core: { invoke: (...args) => { calls.push(args); return Promise.resolve(true); } },
      event: { listen: (name, callback, options) => new Promise((resolve) => {
        const listener = { name, callback, options };
        listeners.add(listener);
        pending.push(() => resolve(() => listeners.delete(listener)));
      }) }
    } },
    document: { addEventListener: (name, callback) => { handlers[name] = callback; } }, console
  };
  vm.runInNewContext(source, context);
  const bridge = context.window.desktopBridge;
  let count = 0;
  for (let i = 0; i < 5; i++) {
    const cleanup = bridge.onTrayCommand(() => count++);
    assert.equal(typeof cleanup, 'function');
    cleanup();
    cleanup();
  }
  for (const listener of listeners) listener.callback({payload: 'pause'});
  assert.equal(count, 0);
  pending.splice(0).forEach((finish) => finish());
  await Promise.resolve();
  assert.equal(listeners.size, 0);
  const cleanup = bridge.onWindowState(() => count++);
  pending.pop()();
  await Promise.resolve();
  for (const listener of listeners) listener.callback({payload: {maximized: true}});
  assert.equal(count, 1);
  cleanup();
  assert.equal(listeners.size, 0);
  await bridge.openImageResourceDirectory('yys/common/test.png');
  assert.equal(calls[0][0], 'open_image_resource_directory');
  assert.equal(calls[0][1].resourceId, 'yys/common/test.png');
  // 产品契约：AC10，标题区域左键拖动，双击切换最大化。
  handlers.mousedown({button: 0, detail: 1, target: {closest: () => true}});
  assert.equal(calls[1][1].action, 'drag');
  handlers.mousedown({button: 0, detail: 2, target: {closest: () => true}});
  assert.equal(calls[2][1].action, 'toggle-maximize');
  // 产品契约：Electron 回退入口保留，其 preload 桥接不能被覆盖。
  vm.runInNewContext(source, context);
  assert.equal(context.window.desktopBridge, bridge);

  const capability = JSON.parse(fs.readFileSync(path.join(__dirname, '../../gui/src-tauri/capabilities/main.json')));
  assert.deepEqual(capability.windows, ['main']);
  assert.equal(capability.remote, undefined);
  assert.deepEqual(capability.permissions, [
    'allow-desktop-bootstrap', 'allow-window-action', 'allow-is-maximized',
    'allow-restore-gui-focus', 'allow-open-screenshot-directory', 'allow-open-image-resource-directory',
    'core:event:allow-listen', 'core:event:allow-unlisten'
  ]);
  const renderer = fs.readFileSync(path.join(__dirname, '../../gui/renderer.js'), 'utf8');
  const guardStart = renderer.indexOf('async function requestJson');
  const guardEnd = renderer.indexOf('\nasync function apiGet', guardStart);
  let fetched = false;
  const notReady = { desktopReady: false, fetch: () => { fetched = true; }, Error };
  vm.runInNewContext(renderer.slice(guardStart, guardEnd) + '\nthis.request = requestJson;', notReady);
  await assert.rejects(notReady.request('/api/scripts'), /尚未就绪/);
  assert.equal(fetched, false);
  console.log('Tauri 桥接契约检查通过');
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
