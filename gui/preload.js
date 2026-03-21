// 预加载脚本，用于暴露API到渲染进程
const { contextBridge, ipcRenderer } = require('electron');

// 安全地暴露API到渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 发送任务控制命令
  startTask: (taskName) => ipcRenderer.invoke('start-task', taskName),
  pauseTask: () => ipcRenderer.invoke('pause-task'),
  resumeTask: () => ipcRenderer.invoke('resume-task'),
  stopTask: () => ipcRenderer.invoke('stop-task'),
  sendInput: (value) => ipcRenderer.invoke('send-input', value),
  
  // 监听事件
  onTaskStatus: (callback) => ipcRenderer.on('task-status', callback),
  onLogMessage: (callback) => ipcRenderer.on('log-message', callback),
  onTaskList: (callback) => ipcRenderer.on('task-list', callback),
  onInputRequest: (callback) => ipcRenderer.on('input-request', callback),
  
  // WebSocket通信相关
  sendToBackend: (message) => ipcRenderer.send('send-to-backend', message),
  onWsMessage: (callback) => ipcRenderer.on('ws-message', callback)
});