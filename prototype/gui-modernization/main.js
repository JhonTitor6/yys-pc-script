const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

const PREVIEW_SIZES = new Set(['800x600', '900x650', '1280x720']);

function createWindow() {
  const window = new BrowserWindow({
    width: 900,
    height: 650,
    minWidth: 800,
    minHeight: 600,
    frame: false,
    backgroundColor: '#f4f5f6',
    title: '阴阳师 PC Script · Prototype',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  const sendWindowState = () => {
    if (!window.isDestroyed()) {
      window.webContents.send('prototype:window-state', { maximized: window.isMaximized() });
    }
  };

  window.on('maximize', sendWindowState);
  window.on('unmaximize', sendWindowState);
  window.on('restore', sendWindowState);
  window.loadFile(path.join(__dirname, 'index.html'));
}

ipcMain.handle('prototype:resize', (event, size) => {
  if (typeof size !== 'string' || !PREVIEW_SIZES.has(size)) return false;
  const [width, height] = size.split('x').map(Number);
  const window = BrowserWindow.fromWebContents(event.sender);
  if (!window || window.isDestroyed()) return false;
  window.setSize(width, height);
  return true;
});

ipcMain.handle('prototype:window-action', (event, action) => {
  const window = BrowserWindow.fromWebContents(event.sender);
  if (!window || window.isDestroyed()) return { maximized: false };

  if (action === 'minimize') window.minimize();
  if (action === 'toggle-maximize') {
    if (window.isMaximized()) window.unmaximize();
    else window.maximize();
  }
  if (action === 'close') window.close();

  return { maximized: window.isMaximized() };
});

ipcMain.handle('prototype:is-maximized', (event) => {
  const window = BrowserWindow.fromWebContents(event.sender);
  return Boolean(window && !window.isDestroyed() && window.isMaximized());
});

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
