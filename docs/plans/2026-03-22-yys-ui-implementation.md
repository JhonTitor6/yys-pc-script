# 阴阳师 UI 界面实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完善现有 `gui/` 目录，实现 Electron 桌面外壳 + FastAPI 后端 + 深色主题 UI

**Architecture:** 基于现有 `gui/` 结构，修复 main.js 启动 Python 后端，改造 UI 为深色主题

**Tech Stack:** Electron ^28.0.0, FastAPI, WebSocket, HTML/CSS/JS (现有 Vue + Element Plus)

---

## 文件结构（修改现有文件）

```
yys-pc-script/
├── gui/
│   ├── main.js              # 修改：添加 Python 后端启动 + ipcMain 处理器
│   ├── preload.js           # 保留：已有正确的 IPC 模式
│   ├── index.html           # 修改：深色主题 UI
│   └── package.json         # 保留：依赖已满足
├── web_server.py            # 修改：支持配置传递
├── config/
│   └── ui_config.json       # 新增：UI 配置文件
└── docs/superpowers/plans/
```

---

## 任务列表

### Task 1: 修复 gui/main.js（添加 Python 后端启动 + IPC 处理）

**Files:**
- Modify: `gui/main.js`
- Modify: `gui/preload.js` (简化，移除未使用的 IPC)

> **Note:** 新 UI 直接通过 WebSocket 与后端通信，不使用 preload.js 的 IPC 通道。preload.js 中的 `ipcRenderer.invoke('start-task')` 等调用将不起作用（因为 main.js 没有对应的 `ipcMain.handle`）。但这不影响功能，因 renderer.js 直接连接 `ws://localhost:8000/ws`。

- [ ] **Step 1: 替换 gui/main.js 完整内容**

```javascript
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
    const check = () => {
      const client = new net.Socket();
      client.connect(port, '127.0.0.1', () => {
        client.destroy();
        resolve();
      });
      client.on('error', () => {
        client.destroy();
        if (Date.now() - start > timeout) {
          reject(new Error('Port timeout'));
        } else {
          setTimeout(check, 500);
        }
      });
    };
    check();
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
```

- [ ] **Step 2: Commit**

```bash
git add gui/main.js
git commit -m "fix(gui): add Python backend spawn and IPC handlers to main.js"
```

---

### Task 2: 修改 web_server.py 支持配置传递

**Files:**
- Modify: `web_server.py:86` (TaskExecutor.__init__)
- Modify: `web_server.py:250` (start_task 处理)

- [ ] **Step 1: 修改 TaskExecutor 接收配置参数**

定位到约第 86 行，`TaskExecutor.__init__` 方法，添加 `config` 参数：

```python
def __init__(self, task_name, task_class: Type[YYSBaseScript], log_queue,
             input_queue, response_queue, config: Optional[Dict] = None):
    # ... 现有代码 ...
    self.config = config or {}
    self.task_instance = self._instance_class()
```

- [ ] **Step 2: 修改 _instance_class 方法应用配置**

定位到约第 97 行，修改 `_instance_class` 方法：

```python
def _instance_class(self):
    # 保存当前工作目录并在任务开始前切换到项目根目录
    logger.debug(f"当前工作目录: {self.original_cwd}")
    # 获取任务类所在的目录并切换
    task_module_path = os.path.dirname(inspect.getfile(self.task_class))
    logger.debug(f"任务类目录: {task_module_path}")
    os.chdir(task_module_path)
    # 创建任务实例
    instance = self.task_class()
    # 应用配置（新增）
    if self.config:
        if 'max_battle_count' in self.config:
            instance.set_max_battle_count(self.config['max_battle_count'])
    return instance
```

> ⚠️ **重要**: 必须保留 `os.chdir(task_module_path)`，否则任务运行时会因工作目录错误而失败。
>
> **Note**: `loop_interval` 配置暂未在任务类中使用，可后续扩展。当前仅 `max_battle_count` 生效。

- [ ] **Step 3: 修改 start_task 处理接收 config**

定位到约第 250 行，修改 `start_task` 处理：

```python
if message["type"] == "start_task":
    task_name = message["task_name"]
    config = message.get("config", {})  # 新增：接收配置
    task_manager = TaskManager()

    if task_name in task_manager.tasks:
        global executor_thread, current_task
        if executor_thread and executor_thread.is_alive():
            await websocket.send_text(json.dumps({
                "type": "log",
                "data": "已有任务在运行，请先停止当前任务",
                "level": "ERROR"
            }))
            continue

        task_class = task_manager.tasks[task_name]['class']
        current_task = task_name

        executor_thread = TaskExecutor(
            task_name, task_class, log_queue,
            input_queue, response_queue, config  # 传递配置
        )
```

- [ ] **Step 4: Commit**

```bash
git add web_server.py
git commit -m "feat(web_server): support config parameter in TaskExecutor"
```

---

### Task 3: 改造 gui/index.html 为深色主题 UI

**Files:**
- Modify: `gui/index.html` (完整替换)

- [ ] **Step 1: 替换 gui/index.html 为深色主题**

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>阴阳师自动化工具</title>
    <style>
        :root {
            --bg-primary: #0f0f1a;
            --bg-secondary: #1a1a2e;
            --bg-tertiary: #16213e;
            --border-color: #333;
            --text-primary: #fff;
            --text-secondary: #ccc;
            --text-muted: #888;
            --accent-green: #4ade80;
            --accent-yellow: #facc15;
            --accent-red: #ef4444;
            --accent-blue: #3b82f6;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            height: 100vh;
            overflow: hidden;
        }

        .container {
            display: flex;
            height: 100%;
        }

        /* 侧边栏 */
        .sidebar {
            width: 220px;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }

        .section-title {
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .task-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .task-item {
            padding: 10px 12px;
            background: var(--bg-tertiary);
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
            color: var(--text-secondary);
        }

        .task-item:hover { border-color: var(--border-color); }

        .task-item.active {
            border-color: var(--accent-green);
            color: var(--accent-green);
        }

        .config-item { margin-bottom: 12px; }

        .config-item label {
            display: block;
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 4px;
        }

        .config-item input {
            width: 100%;
            padding: 6px 10px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            color: var(--text-primary);
            font-size: 13px;
        }

        /* 主区域 */
        .main {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        /* 控制栏 */
        .control-bar {
            padding: 16px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .control-buttons { display: flex; gap: 8px; }

        .btn {
            padding: 8px 20px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .btn-start { background: var(--accent-green); color: #000; }
        .btn-start:hover:not(:disabled) { background: #22c55e; }

        .btn-pause { background: var(--accent-yellow); color: #000; }
        .btn-pause:hover:not(:disabled) { background: #eab308; }

        .btn-resume { background: var(--accent-blue); color: #fff; }
        .btn-resume:hover:not(:disabled) { background: #2563eb; }

        .btn-stop { background: var(--accent-red); color: #fff; }
        .btn-stop:hover:not(:disabled) { background: #dc2626; }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-left: auto;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--text-muted);
        }

        .status-indicator.running .status-dot { background: var(--accent-green); }
        .status-indicator.paused .status-dot { background: var(--accent-yellow); }
        .status-indicator.error .status-dot { background: var(--accent-red); }

        .status-text { font-size: 13px; color: var(--text-secondary); }

        /* 统计栏 */
        .stats-bar {
            padding: 16px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            gap: 32px;
        }

        .stat-item { display: flex; flex-direction: column; gap: 4px; }

        .stat-label { font-size: 12px; color: var(--text-muted); }

        .stat-value { font-size: 24px; font-weight: 600; }

        /* 日志区 */
        .log-container { flex: 1; overflow: hidden; padding: 16px; }

        .log-area {
            height: 100%;
            overflow-y: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 12px;
            line-height: 1.6;
        }

        .log-line { padding: 2px 0; }
        .log-line.INFO { color: var(--text-primary); }
        .log-line.WARNING { color: var(--accent-yellow); }
        .log-line.ERROR { color: var(--accent-red); }
        .log-line.SUCCESS { color: var(--accent-green); }
    </style>
</head>
<body>
    <div class="container">
        <!-- 左侧栏 -->
        <aside class="sidebar">
            <div class="sidebar-section">
                <h3 class="section-title">任务列表</h3>
                <div id="task-list" class="task-list"></div>
            </div>

            <div class="sidebar-section">
                <h3 class="section-title">配置</h3>
                <div class="config-item">
                    <label>战斗次数:</label>
                    <input type="number" id="config-battles" value="103" min="1" max="999">
                </div>
                <div class="config-item">
                    <label>循环间隔(秒):</label>
                    <input type="number" id="config-interval" value="5" min="1" max="60">
                </div>
            </div>
        </aside>

        <!-- 主区域 -->
        <main class="main">
            <!-- 控制栏 -->
            <div class="control-bar">
                <div class="control-buttons">
                    <button id="btn-start" class="btn btn-start">启动</button>
                    <button id="btn-pause" class="btn btn-pause" disabled>暂停</button>
                    <button id="btn-resume" class="btn btn-resume" disabled style="display:none">恢复</button>
                    <button id="btn-stop" class="btn btn-stop" disabled>停止</button>
                </div>
                <div id="status-indicator" class="status-indicator">
                    <span class="status-dot"></span>
                    <span class="status-text">空闲</span>
                </div>
            </div>

            <!-- 统计栏 -->
            <div class="stats-bar">
                <div class="stat-item">
                    <span class="stat-label">当前战斗</span>
                    <span class="stat-value"><span id="cur-battles">0</span>/<span id="max-battles">103</span></span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">胜利次数</span>
                    <span class="stat-value" id="victories">0</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">运行时长</span>
                    <span class="stat-value" id="runtime">00:00</span>
                </div>
            </div>

            <!-- 日志区 -->
            <div class="log-container">
                <div id="log-area" class="log-area"></div>
            </div>
        </main>
    </div>

    <script>
        class YYSUI {
            constructor() {
                this.ws = null;
                this.currentTask = null;
                this.status = 'idle';
                this.taskStartTime = null;
                this.logs = [];
                this.maxLogs = 500;
                this.reconnectAttempts = 0;
                this.maxReconnectAttempts = 3;

                this.elements = {
                    taskList: document.getElementById('task-list'),
                    btnStart: document.getElementById('btn-start'),
                    btnPause: document.getElementById('btn-pause'),
                    btnResume: document.getElementById('btn-resume'),
                    btnStop: document.getElementById('btn-stop'),
                    statusIndicator: document.getElementById('status-indicator'),
                    curBattles: document.getElementById('cur-battles'),
                    maxBattles: document.getElementById('max-battles'),
                    victories: document.getElementById('victories'),
                    runtime: document.getElementById('runtime'),
                    logArea: document.getElementById('log-area'),
                    configBattles: document.getElementById('config-battles'),
                    configInterval: document.getElementById('config-interval')
                };

                this.init();
            }

            init() {
                this.connectWebSocket();
                this.bindEvents();
                this.loadConfig();
                this.startRuntimeClock();
            }

            connectWebSocket() {
                const wsUrl = 'ws://localhost:8000/ws';
                this.ws = new WebSocket(wsUrl);

                this.ws.onopen = () => {
                    console.log('WebSocket connected');
                    this.reconnectAttempts = 0;
                };

                this.ws.onclose = () => {
                    console.log('WebSocket disconnected');
                    this.attemptReconnect();
                };

                this.ws.onerror = (err) => console.error('WebSocket error:', err);

                this.ws.onmessage = (event) => {
                    const msg = JSON.parse(event.data);
                    this.handleMessage(msg);
                };
            }

            attemptReconnect() {
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    setTimeout(() => this.connectWebSocket(), 2000);
                }
            }

            handleMessage(msg) {
                switch (msg.type) {
                    case 'tasks':
                        this.renderTaskList(msg.data);
                        break;
                    case 'log':
                        this.appendLog(msg.data, msg.level);
                        break;
                    case 'status':
                        this.updateStatus(msg.data);
                        break;
                    case 'ping':
                        this.ws.send(JSON.stringify({ type: 'pong' }));
                        break;
                }
            }

            renderTaskList(tasks) {
                this.elements.taskList.innerHTML = tasks.map(task => `
                    <div class="task-item" data-task="${task.name}">${task.name}</div>
                `).join('');

                this.elements.taskList.querySelectorAll('.task-item').forEach(item => {
                    item.addEventListener('click', () => this.selectTask(item.dataset.task));
                });

                if (tasks.length > 0 && !this.currentTask) {
                    this.selectTask(tasks[0].name);
                }
            }

            selectTask(taskName) {
                if (this.status !== 'idle') return;
                this.currentTask = taskName;
                this.elements.taskList.querySelectorAll('.task-item').forEach(item => {
                    item.classList.toggle('active', item.dataset.task === taskName);
                });
            }

            updateStatus(status) {
                this.status = status;
                const indicator = this.elements.statusIndicator;
                indicator.className = 'status-indicator ' + status;

                const statusTexts = {
                    idle: '空闲', running: '运行中', paused: '已暂停',
                    stopped: '已停止', completed: '已完成', error: '错误'
                };
                indicator.querySelector('.status-text').textContent = statusTexts[status] || status;

                this.elements.btnStart.disabled = status !== 'idle';
                this.elements.btnPause.disabled = status !== 'running';
                this.elements.btnResume.style.display = status === 'paused' ? 'inline-block' : 'none';
                this.elements.btnStop.disabled = status === 'idle';

                if (status === 'running' && !this.taskStartTime) {
                    this.taskStartTime = Date.now();
                } else if (status === 'idle' || status === 'stopped') {
                    this.taskStartTime = null;
                    this.elements.curBattles.textContent = '0';
                    this.elements.victories.textContent = '0';
                }
            }

            appendLog(text, level = 'INFO') {
                this.logs.push({ text, level, time: new Date() });
                if (this.logs.length > this.maxLogs) this.logs.shift();

                const line = document.createElement('div');
                line.className = `log-line ${level}`;
                line.textContent = text;
                this.elements.logArea.appendChild(line);
                this.elements.logArea.scrollTop = this.elements.logArea.scrollHeight;

                this.parseBattleStats(text);
            }

            parseBattleStats(text) {
                const battleMatch = text.match(/战斗完成.*?(\d+)\/(\d+)/);
                if (battleMatch) {
                    this.elements.curBattles.textContent = battleMatch[1];
                    this.elements.maxBattles.textContent = battleMatch[2];
                }
                const victoryMatch = text.match(/胜利(\d+)次/);
                if (victoryMatch) {
                    this.elements.victories.textContent = victoryMatch[1];
                }
            }

            startRuntimeClock() {
                setInterval(() => {
                    if (this.taskStartTime) {
                        const elapsed = Math.floor((Date.now() - this.taskStartTime) / 1000);
                        const mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
                        const secs = (elapsed % 60).toString().padStart(2, '0');
                        this.elements.runtime.textContent = `${mins}:${secs}`;
                    }
                }, 1000);
            }

            bindEvents() {
                this.elements.btnStart.addEventListener('click', () => this.startTask());
                this.elements.btnPause.addEventListener('click', () => this.pauseTask());
                this.elements.btnResume.addEventListener('click', () => this.resumeTask());
                this.elements.btnStop.addEventListener('click', () => this.stopTask());
            }

            loadConfig() {
                const saved = localStorage.getItem('yys-ui-config');
                if (saved) {
                    const config = JSON.parse(saved);
                    this.elements.configBattles.value = config.maxBattles || 103;
                    this.elements.configInterval.value = config.loopInterval || 5;
                }
            }

            saveConfig() {
                const config = {
                    maxBattles: parseInt(this.elements.configBattles.value),
                    loopInterval: parseInt(this.elements.configInterval.value)
                };
                localStorage.setItem('yys-ui-config', JSON.stringify(config));
            }

            startTask() {
                if (!this.currentTask || !this.ws) return;
                this.saveConfig();
                this.elements.logArea.innerHTML = '';
                this.logs = [];

                const config = {
                    max_battle_count: parseInt(this.elements.configBattles.value),
                    loop_interval: parseInt(this.elements.configInterval.value)
                };

                this.ws.send(JSON.stringify({
                    type: 'start_task',
                    task_name: this.currentTask,
                    config: config
                }));
            }

            pauseTask() {
                if (this.ws) this.ws.send(JSON.stringify({ type: 'pause_task' }));
            }

            resumeTask() {
                if (this.ws) this.ws.send(JSON.stringify({ type: 'resume_task' }));
            }

            stopTask() {
                if (this.ws) this.ws.send(JSON.stringify({ type: 'stop_task' }));
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            window.ui = new YYSUI();
        });
    </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add gui/index.html
git commit -m "refactor(gui): replace UI with dark theme design"
```

---

### Task 4: 创建配置文件 config/ui_config.json

**Files:**
- Create: `config/ui_config.json`

- [ ] **Step 1: 创建配置目录和文件**

```bash
mkdir -p config
```

```json
{
  "last_selected_task": "御魂",
  "tasks": {
    "御魂": { "max_battle_count": 103, "loop_interval": 5 },
    "结界突破": { "max_battle_count": 9, "loop_interval": 3 },
    "探28": { "max_battle_count": 50, "loop_interval": 3 },
    "御灵": { "max_battle_count": 50, "loop_interval": 5 }
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add config/ui_config.json
git commit -m "feat(config): add UI configuration file"
```

---

### Task 5: 验证和测试

- [ ] **Step 1: 验证 Python 后端单独运行**

```bash
python web_server.py
# 确认无报错，8000 端口监听中
```

- [ ] **Step 2: 验证 Electron 启动**

```bash
cd gui && npm install && npm start
# 确认窗口打开，Python 后端自动启动
```

- [ ] **Step 3: 验证完整流程**

1. 选择任务
2. 点击启动
3. 确认 WebSocket 连接成功
4. 验证日志输出
5. 验证暂停/恢复/停止

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "test(gui): add verification results"
```

---

## 验证步骤总结

| 步骤 | 命令 | 预期结果 |
|------|------|---------|
| 1. Python 后端 | `python web_server.py` | 无报错，8000 端口监听 |
| 2. Electron 启动 | `cd gui && npm start` | 窗口打开，Python 自动启动 |
| 3. 任务启动 | UI 点击启动 | 日志输出，状态变化 |
| 4. 暂停/恢复 | UI 点击暂停/恢复 | 状态正确切换 |
| 5. 停止 | UI 点击停止 | 任务停止，状态重置 |

## 风险与注意事项

- 确保 Python 路径正确（`python` 命令可用）
- 8000 端口不能被占用
- 游戏窗口需先打开并处于可识别状态
- Electron 日志可查看 `View > Toggle DevTools`
