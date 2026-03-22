const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const net = require('net');

const PYTHON_PORT = 8000;
let mainWindow = null;
let pythonProcess = null;

function waitForPort(port, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    let timer;
    const check = () => {
      const client = new net.Socket();
      client.connect(port, '127.0.0.1', () => {
        clearTimeout(timer);
        client.destroy();
        resolve();
      });
      client.on('error', () => {
        clearTimeout(timer);
        client.destroy();
        if (Date.now() - start > timeout) {
          reject(new Error('Port timeout'));
        } else {
          timer = setTimeout(check, 500);
        }
      });
    };
    timer = setTimeout(check, 500);
  });
}

function startPythonBackend() {
  return new Promise((resolve, reject) => {
    const pythonScript = path.join(__dirname, '..', 'web_server.py');
    pythonProcess = spawn('python', [pythonScript], {
      cwd: path.join(__dirname, '..'),
      stdio: ['pipe', 'pipe', 'pipe']
    });

    pythonProcess.stdout.on('data', (data) => {
      console.log(`[Python] ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`[Python Error] ${data}`);
    });

    pythonProcess.on('close', (code) => {
      console.log(`Python process exited with code ${code}`);
      pythonProcess = null;
    });

    pythonProcess.on('error', (err) => {
      reject(err);
    });

    // 等待端口就绪
    waitForPort(PYTHON_PORT)
      .then(resolve)
      .catch(reject);
  });
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

  mainWindow.loadFile(path.join(__dirname, 'index.html'));

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
  } catch (err) {
    console.error('Failed to start Python backend:', err);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (pythonProcess) {
    pythonProcess.kill('SIGTERM');
    setTimeout(() => {
      if (pythonProcess) {
        pythonProcess.kill('SIGKILL');
      }
    }, 5000);
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
