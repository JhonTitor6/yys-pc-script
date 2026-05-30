const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const net = require('net');
const crypto = require('crypto');

const PYTHON_PORT = 8000;
const PYTHON_HOST = '127.0.0.1';
const UI_TOKEN = crypto.randomBytes(32).toString('hex');
let mainWindow = null;
let pythonProcess = null;
let tray = null;
let isQuitting = false;

function resolvePythonExecutable() {
  if (process.env.YYS_PYTHON) return process.env.YYS_PYTHON;
  return 'D:/ProgramData/anaconda3/envs/win_macro/python.exe';
}

function isPortOpen({ port = PYTHON_PORT, host = PYTHON_HOST, timeout = 1000 } = {}) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port });
    let settled = false;

    const finish = (open) => {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve(open);
    };

    socket.setTimeout(timeout);
    socket.once('connect', () => finish(true));
    socket.once('timeout', () => finish(false));
    socket.once('error', () => finish(false));
  });
}

function checkBackendHealth({ token = UI_TOKEN, port = PYTHON_PORT, host = PYTHON_HOST, timeout = 3000 } = {}) {
  return new Promise((resolve) => {
    const req = http.get(
      `http://${host}:${port}/api/scripts`,
      { headers: { 'X-YYS-UI-Token': token } },
      (res) => {
        let body = '';

        res.setEncoding('utf8');
        res.on('data', (chunk) => {
          body += chunk;
        });
        res.on('end', () => {
          if (res.statusCode === 403) {
            resolve({ healthy: false, protected: true });
            return;
          }

          if (res.statusCode !== 200) {
            resolve({ healthy: false, protected: false });
            return;
          }

          try {
            const scripts = JSON.parse(body);
            const healthy = Array.isArray(scripts) && scripts.some((script) => {
              if (script === 'soul_raid') return true;
              return script && (script.script_id === 'soul_raid' || script.id === 'soul_raid');
            });
            resolve({ healthy, protected: false });
          } catch (err) {
            resolve({ healthy: false, protected: false });
          }
        });
      }
    );

    req.setTimeout(timeout, () => {
      req.destroy();
      resolve({ healthy: false, protected: false });
    });
    req.on('error', () => {
      resolve({ healthy: false, protected: false });
    });
  });
}

async function detectBackendState({ token = UI_TOKEN, port = PYTHON_PORT, host = PYTHON_HOST, timeout = 3000 } = {}) {
  const portOpen = await isPortOpen({ port, host, timeout: Math.min(timeout, 1000) });
  if (!portOpen) {
    return { portOpen: false, healthy: false, protected: false };
  }

  const health = await checkBackendHealth({ token, port, host, timeout });
  return { portOpen: true, healthy: health.healthy, protected: health.protected };
}

async function assertBackendPortAvailable(options = {}) {
  const port = options.port || PYTHON_PORT;
  const state = await detectBackendState(options);
  if (!state.portOpen) {
    return;
  }
  if (state.protected) {
    throw new Error(`端口 ${port} 已有受保护的桌面后端在运行，请先退出旧进程`);
  }
  throw new Error(`端口 ${port} 已被占用，无法启动新的桌面后端`);
}

function waitForBackendReady(timeout = 30000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();

    const check = () => {
      detectBackendState({ token: UI_TOKEN }).then((state) => {
        if (state.healthy) {
          resolve();
          return;
        }

        if (state.portOpen && state.protected) {
          reject(new Error(`端口 ${PYTHON_PORT} 已有受保护的桌面后端在运行，请先退出旧进程`));
          return;
        }

        if (Date.now() - start > timeout) {
          reject(new Error('Backend ready timeout'));
          return;
        }

        setTimeout(check, 500);
      });
    };

    check();
  });
}

async function startPythonBackend() {
  await assertBackendPortAvailable({ token: UI_TOKEN });

  return new Promise((resolve, reject) => {
    let settled = false;
    const pythonArgs = ['-m', 'ui_backend.main'];
    pythonProcess = spawn(resolvePythonExecutable(), pythonArgs, {
      cwd: path.join(__dirname, '..'),
      env: { ...process.env, YYS_UI_TOKEN: UI_TOKEN },
      stdio: ['pipe', 'pipe', 'pipe']
    });

    const failStartup = (err) => {
      if (settled) return;
      settled = true;
      reject(err);
    };

    const resolveStartup = () => {
      if (settled) return;
      settled = true;
      resolve();
    };

    pythonProcess.stdout.on('data', (data) => {
      console.log(`[Python] ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`[Python Error] ${data}`);
    });

    pythonProcess.on('close', (code) => {
      if (!settled) {
        failStartup(new Error(`Python process exited before backend ready with code ${code}`));
      }
      console.log(`Python process exited with code ${code}`);
      pythonProcess = null;
    });

    pythonProcess.once('error', failStartup);

    // 等待真实后端接口就绪，避免误判占用同端口的其他进程。
    waitForBackendReady()
      .then(resolveStartup)
      .catch(failStartup);
  });
}

function createTrayIcon() {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">
      <rect width="32" height="32" rx="7" fill="#111820"/>
      <text x="16" y="22" text-anchor="middle" font-size="18" fill="#35c28d" font-family="Arial">阴</text>
    </svg>`;
  return nativeImage.createFromDataURL(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`);
}

function createTray() {
  if (tray) return;

  tray = new Tray(createTrayIcon());
  const menu = Menu.buildFromTemplate([
    { label: '显示工作台', click: () => mainWindow && mainWindow.show() },
    { label: '暂停当前脚本', click: () => mainWindow && mainWindow.webContents.send('tray-command', 'pause') },
    { label: '停止当前脚本', click: () => mainWindow && mainWindow.webContents.send('tray-command', 'stop') },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        isQuitting = true;
        app.quit();
      }
    }
  ]);
  tray.setToolTip('阴阳师脚本工作台');
  tray.setContextMenu(menu);
  tray.on('double-click', () => mainWindow && mainWindow.show());
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 650,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'), {
    query: { token: UI_TOKEN }
  });

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC 处理器 - 窗口控制
ipcMain.on('minimize-window', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.on('maximize-window', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  }
});

ipcMain.on('close-window', () => {
  if (mainWindow) mainWindow.close();
});

app.whenReady().then(async () => {
  try {
    console.log('Starting Python backend...');
    await startPythonBackend();
    console.log('Python backend ready');
    createWindow();
    createTray();
  } catch (err) {
    console.error('Failed to start Python backend:', err);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  isQuitting = true;
  if (pythonProcess) {
    pythonProcess.kill('SIGTERM');
    setTimeout(() => {
      if (pythonProcess) {
        pythonProcess.kill('SIGKILL');
      }
    }, 5000);
  }
});

module.exports = {
  assertBackendPortAvailable,
  checkBackendHealth,
  detectBackendState,
  isPortOpen
};
