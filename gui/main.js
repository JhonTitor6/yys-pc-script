const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, screen, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
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

const DEFAULT_BOUNDS = { width: 900, height: 650 };
const MIN_WIDTH = 800;
const MIN_HEIGHT = 600;

// 把窗口大小持久化到 userData/window-state.json；启动时恢复
function getWindowStatePath() {
  return path.join(app.getPath('userData'), 'window-state.json');
}

function loadWindowBounds() {
  try {
    const raw = fs.readFileSync(getWindowStatePath(), 'utf8');
    const parsed = JSON.parse(raw);
    const width = Number(parsed.width);
    const height = Number(parsed.height);
    if (!Number.isFinite(width) || !Number.isFinite(height)) return null;
    if (width < MIN_WIDTH || height < MIN_HEIGHT) return null;
    // 仅当记录的屏幕位置仍可见时，才使用上次的 x/y
    let x = Number(parsed.x);
    let y = Number(parsed.y);
    if (Number.isFinite(x) && Number.isFinite(y)) {
      const displays = screen.getAllDisplays();
      const visible = displays.some((d) => {
        const b = d.bounds;
        return x >= b.x && y >= b.y && x < b.x + b.width && y < b.y + b.height;
      });
      if (!visible) {
        x = undefined;
        y = undefined;
      }
    } else {
      x = undefined;
      y = undefined;
    }
    return { width, height, x, y };
  } catch (err) {
    return null;
  }
}

function saveWindowBounds(win) {
  if (!win || win.isDestroyed()) return;
  if (win.isMinimized() || win.isMaximized() || win.isFullScreen()) return;
  const bounds = win.getNormalBounds();
  try {
    fs.mkdirSync(path.dirname(getWindowStatePath()), { recursive: true });
    fs.writeFileSync(
      getWindowStatePath(),
      JSON.stringify({
        width: bounds.width,
        height: bounds.height,
        x: bounds.x,
        y: bounds.y
      }, null, 2),
      'utf8'
    );
  } catch (err) {
    console.error('保存窗口尺寸失败:', err);
  }
}

function resolvePythonExecutable() {
  // 打包模式：使用随产品分发的 yys-backend.exe（PyInstaller --onedir 产物）。
  // Windows 上固定名称，路径由 electron-builder 的 extraResources 注入。
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend', 'yys-backend.exe');
  }
  // 开发模式：YYS_PYTHON 环境变量优先，否则用项目默认 conda 环境。
  if (process.env.YYS_PYTHON) return process.env.YYS_PYTHON;
  return 'D:/ProgramData/anaconda3/envs/win_macro/python.exe';
}

function resolveBackendCwd(backendExe) {
  // dev 模式：cwd = 项目根（__dirname 上一级），保证 Path("config")/.. 落点不变。
  // pack 模式：cwd = exe 同目录，使相对路径 Path("config")、Path("yys/logs")
  //            自然落到用户安装目录的同级，而不是 _internal 内。
  if (app.isPackaged) {
    return path.dirname(backendExe);
  }
  return path.join(__dirname, '..');
}

function resolveBackendEnvironment() {
  return {
    ...process.env,
    YYS_UI_TOKEN: UI_TOKEN,
    YYS_USER_DATA_DIR: app.getPath('userData'),
    PYTHONIOENCODING: 'utf-8'
  };
}

function resolveImageOverridePath(resourceId) {
  if (typeof resourceId !== 'string' || resourceId.includes('\\') || resourceId.includes('\0')) return null;
  const parts = resourceId.split('/');
  if (
    parts.length < 2
    || parts[0] !== 'yys'
    || parts.some((part) => !part || part === '.' || part === '..' || part.includes(':'))
    || !/\.(bmp|png)$/i.test(parts[parts.length - 1])
  ) return null;

  const root = path.resolve(app.getPath('userData'), 'image-overrides');
  const target = path.resolve(root, ...parts);
  const relative = path.relative(root, target);
  if (relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) return null;
  return target;
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
    const isPackaged = app.isPackaged;
    // dev: 走 `python -m ui_backend.main`；pack: yys-backend.exe 是 PyInstaller 引导器，直接执行。
    const pythonArgs = isPackaged ? [] : ['-m', 'ui_backend.main'];
    const backendExe = resolvePythonExecutable();
    pythonProcess = spawn(backendExe, pythonArgs, {
      cwd: resolveBackendCwd(backendExe),
      env: resolveBackendEnvironment(),
      stdio: ['pipe', 'pipe', 'pipe']
    });
    pythonProcess.stdout.setEncoding('utf8');
    pythonProcess.stderr.setEncoding('utf8');

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
  const saved = loadWindowBounds();
  const opts = {
    width: saved?.width ?? DEFAULT_BOUNDS.width,
    height: saved?.height ?? DEFAULT_BOUNDS.height,
    minWidth: MIN_WIDTH,
    minHeight: MIN_HEIGHT,
    frame: false,
    backgroundColor: '#f2f4f4',
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  };
  if (saved?.x !== undefined && saved?.y !== undefined) {
    opts.x = saved.x;
    opts.y = saved.y;
  }
  mainWindow = new BrowserWindow(opts);

  mainWindow.loadFile(path.join(__dirname, 'index.html'), {
    query: { token: UI_TOKEN }
  });

  // 监听尺寸/位置变化：debounce 后写盘，避免拖动时频繁 IO
  let saveTimer = null;
  const scheduleSave = () => {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => saveWindowBounds(mainWindow), 400);
  };
  mainWindow.on('resize', scheduleSave);
  mainWindow.on('move', scheduleSave);
  const sendWindowState = () => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    mainWindow.webContents.send('window-state', { maximized: mainWindow.isMaximized() });
  };
  mainWindow.on('maximize', () => { scheduleSave(); sendWindowState(); });
  mainWindow.on('unmaximize', () => { scheduleSave(); sendWindowState(); });
  mainWindow.on('ready-to-show', sendWindowState);
  mainWindow.on('close', () => {
    if (saveTimer) clearTimeout(saveTimer);
    saveWindowBounds(mainWindow);
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

if (typeof ipcMain.handle === 'function') {
  ipcMain.handle('window-action', (event, action) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    if (!win || win.isDestroyed()) return { maximized: false };
    if (action === 'minimize') win.minimize();
    if (action === 'toggle-maximize') {
      if (win.isMaximized()) win.unmaximize();
      else win.maximize();
    }
    if (action === 'close') win.close();
    return { maximized: win.isMaximized() };
  });

  ipcMain.handle('is-maximized', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    return Boolean(win && !win.isDestroyed() && win.isMaximized());
  });

  ipcMain.handle('restore-gui-focus', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    if (!win || win.isDestroyed()) return false;
    if (win.isMinimized()) win.restore();
    win.show();
    win.focus();
    return true;
  });

  ipcMain.handle('open-image-resource-directory', (_event, resourceId) => {
    const target = resolveImageOverridePath(resourceId);
    if (!target) return { opened: false, reason: 'invalid-resource' };
    try {
      if (!fs.statSync(target).isFile()) return { opened: false, reason: 'not-found' };
      shell.showItemInFolder(target);
      return { opened: true };
    } catch (error) {
      return { opened: false, reason: 'not-found' };
    }
  });
}

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
  isPortOpen,
  resolveBackendEnvironment,
  resolveImageOverridePath
};
