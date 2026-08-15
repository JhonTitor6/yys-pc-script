const assert = require('assert');
const fs = require('fs');
const http = require('http');
const path = require('path');
const vm = require('vm');

function loadMainModule() {
  const filename = path.resolve(__dirname, '../../gui/main.js');
  const source = fs.readFileSync(filename, 'utf8');
  const module = { exports: {} };
  const sandbox = {
    __dirname: path.dirname(filename),
    console,
    module,
    exports: module.exports,
    process,
    require: (name) => {
      if (name === 'electron') {
        return {
          app: {
            getPath: (name) => {
              assert.strictEqual(name, 'userData');
              return 'C:\\Users\\tester\\AppData\\Roaming\\yys-script-manager';
            },
            whenReady: () => new Promise(() => {}),
            on: () => {},
            quit: () => {},
            requestSingleInstanceLock: () => true
          },
          BrowserWindow: function BrowserWindow() {},
          ipcMain: { on: () => {}, handle: () => {} },
          Tray: function Tray() {},
          Menu: { buildFromTemplate: () => ({}) },
          nativeImage: { createFromDataURL: () => ({}) },
          shell: { showItemInFolder: () => {} }
        };
      }
      if (name === 'child_process') {
        return { spawn: () => { throw new Error('测试不应启动 Python'); } };
      }
      return require(name);
    }
  };

  vm.runInNewContext(source, sandbox, { filename });
  return module.exports;
}

function listen(server) {
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      resolve(server.address().port);
    });
  });
}

function close(server) {
  return new Promise((resolve, reject) => {
    server.close((err) => (err ? reject(err) : resolve()));
  });
}

async function testDetectsProtectedBackend() {
  const server = http.createServer((req, res) => {
    assert.strictEqual(req.url, '/api/scripts');
    res.writeHead(403, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ detail: 'UI token 无效' }));
  });
  const port = await listen(server);

  try {
    const main = loadMainModule();
    assert.strictEqual(typeof main.detectBackendState, 'function');

    const state = await main.detectBackendState({ port, token: 'new-token', timeout: 1000 });

    assert.strictEqual(state.portOpen, true);
    assert.strictEqual(state.healthy, false);
    assert.strictEqual(state.protected, true);
  } finally {
    await close(server);
  }
}

async function testProtectedBackendBlocksStartup() {
  const server = http.createServer((_req, res) => {
    res.writeHead(403, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ detail: 'UI token 无效' }));
  });
  const port = await listen(server);

  try {
    const main = loadMainModule();
    assert.strictEqual(typeof main.assertBackendPortAvailable, 'function');

    await assert.rejects(
      () => main.assertBackendPortAvailable({ port, token: 'new-token', timeout: 1000 }),
      /受保护/
    );
  } finally {
    await close(server);
  }
}

function testBackendReceivesPersistentUserDataRoot() {
  const main = loadMainModule();
  const env = main.resolveBackendEnvironment();
  assert.strictEqual(
    env.YYS_USER_DATA_DIR,
    'C:\\Users\\tester\\AppData\\Roaming\\yys-script-manager'
  );
  assert.ok(env.YYS_UI_TOKEN);
}

function testImageOverridePathValidation() {
  const main = loadMainModule();
  assert.strictEqual(
    main.resolveImageOverridePath('yys/common/example.bmp'),
    path.join('C:\\Users\\tester\\AppData\\Roaming\\yys-script-manager', 'image-overrides', 'yys', 'common', 'example.bmp')
  );
  assert.strictEqual(main.resolveImageOverridePath('../secret.bmp'), null);
  assert.strictEqual(main.resolveImageOverridePath('yys\\common\\example.bmp'), null);
}

async function main() {
  testBackendReceivesPersistentUserDataRoot();
  testImageOverridePathValidation();
  await testDetectsProtectedBackend();
  await testProtectedBackendBlocksStartup();
  console.log('backend detection tests passed');
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
