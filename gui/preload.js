const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('desktopBridge', {
  onTrayCommand: (callback) => {
    const listener = (_event, command) => callback(command);
    ipcRenderer.on('tray-command', listener);
    return () => ipcRenderer.removeListener('tray-command', listener);
  },
  minimizeWindow: () => ipcRenderer.send('minimize-window'),
  maximizeWindow: () => ipcRenderer.send('maximize-window'),
  closeWindow: () => ipcRenderer.send('close-window'),
  restoreGuiFocus: () => ipcRenderer.invoke('restore-gui-focus'),
  openScreenshotDirectory: () => ipcRenderer.invoke('open-screenshot-directory'),
  openImageResourceDirectory: (resourceId) => ipcRenderer.invoke('open-image-resource-directory', resourceId),
  windowAction: (action) => ipcRenderer.invoke('window-action', action),
  isMaximized: () => ipcRenderer.invoke('is-maximized'),
  onWindowState: (callback) => {
    const listener = (_event, windowState) => callback(windowState);
    ipcRenderer.on('window-state', listener);
    return () => ipcRenderer.removeListener('window-state', listener);
  }
});
