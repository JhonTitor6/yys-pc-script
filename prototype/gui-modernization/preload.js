const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('prototypeWindow', {
  resize: (size) => ipcRenderer.invoke('prototype:resize', size),
  action: (action) => ipcRenderer.invoke('prototype:window-action', action),
  isMaximized: () => ipcRenderer.invoke('prototype:is-maximized'),
  onStateChange: (listener) => {
    const handler = (_event, state) => listener(state);
    ipcRenderer.on('prototype:window-state', handler);
    return () => ipcRenderer.removeListener('prototype:window-state', handler);
  }
});
