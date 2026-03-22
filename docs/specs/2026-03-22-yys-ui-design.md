# 阴阳师 UI 界面设计

## 概述

为 yys-pc-script 项目开发一个本地桌面 UI 界面，用于控制阴阳师自动化脚本的启动、监控和配置。

## 需求确认

- **使用场景：** 本地桌面工具
- **界面风格：** 简约深色工具型
- **核心功能：** 任务控制 + 实时日志 + 配置管理
- **技术选型：** Electron Shell + 现有 FastAPI 后端

---

## 一、架构设计

### 整体架构

```
┌─────────────────────────────────────────┐
│           Electron 渲染进程              │
│  ┌─────────────────────────────────────┐│
│  │         HTML/CSS/JS 前端             ││
│  │  任务选择 | 配置 | 控制按钮 | 日志     ││
│  └─────────────────────────────────────┘│
│                  ↕ IPC/Bidirectional    │
├─────────────────────────────────────────┤
│           Electron 主进程                │
│  ┌─────────────────────────────────────┐│
│  │     Python 子进程 (web_server.py)    ││
│  │  FastAPI + WebSocket + 任务执行器     ││
│  └─────────────────────────────────────┘│
└─────────────────────────────────────────┘
```

### 核心思路

- Electron 仅作为桌面包装，启动时唤起 Python 后端进程
- 前端通过 WebSocket (`ws://localhost:8000/ws`) 与 FastAPI 通信
- 日志/状态通过 WebSocket 实时推送，最大程度复用现有代码

### 项目结构调整

```
yys-pc-script/
├── electron/                 # 新增 Electron 部分
│   ├── main.js              # Electron 主进程
│   ├── preload.js           # 预加载脚本
│   └── ui/                 # 前端资源
│       ├── index.html
│       ├── styles.css
│       └── renderer.js
├── web_server.py            # 现有 FastAPI 后端
└── yys/                    # 现有业务逻辑
```

---

## 二、组件设计

### 1. 任务选择区（左侧栏）

- 任务列表：御魂、结界突破、探28、御灵
- 当前任务高亮显示（绿色边框+背景）
- 配置项：战斗次数、循环间隔
- 仅在未运行时可切换任务

**配置管理：**
- 配置文件路径：`config/ui_config.json`（项目根目录下）
- 格式：JSON，包含各任务的默认配置
- 生命周期：
  - 启动时：从 JSON 文件加载配置到 UI 输入框
  - 修改后：实时保存到 JSON 文件
  - 任务启动时：将当前配置通过 WebSocket 传给后端
- 配置内容：
  - `max_battle_count`：每局最大战斗次数
  - `loop_interval`：每轮循环间隔（秒）
  - `last_selected_task`：上次选中的任务名

### 2. 控制区（右侧顶部）

- 三个按钮：启动、暂停、停止
- 右侧显示运行状态指示器

**状态流转（与 WebSocket status 对应）：**
- idle（空闲）→ 点击启动 → running（运行中）
- running → 点击暂停 → paused（已暂停）
- paused → 点击恢复 → running（运行中）
- running/paused → 点击停止 → idle（空闲）
- running → 任务正常结束 → completed
- running → 任务异常 → error

### 3. 统计区

- 当前战斗次数：`45/103`
- 胜利次数：`43`
- 运行时长：`12:35`

### 4. 日志区

- 自动滚动到底部
- 日志级别颜色区分：
  - INFO: 白色
  - WARNING: 黄色
  - ERROR: 红色
  - SUCCESS: 绿色
- 最大保留 500 条，超出自动清理
- 任务重启时清空日志

---

## 三、数据流设计

### WebSocket 通信协议

**客户端 → 服务端：**
```json
{ "type": "start_task", "task_name": "御魂" }
{ "type": "pause_task" }
{ "type": "resume_task" }
{ "type": "stop_task" }
```

**服务端 → 客户端：**
```json
{ "type": "tasks", "data": [{ "name": "御魂", "description": "..." }] }
{ "type": "log", "data": "[14:23:01] 消息内容", "level": "INFO" }
{ "type": "status", "data": "running" | "paused" | "resumed" | "stopped" | "completed" | "error" }
{ "type": "ping", "timestamp": 1234567890 }
{ "type": "pong" }
```

### Electron 启动流程

1. `electron/main.js` 启动
2. 读取端口配置（默认 8000）
3. `spawn` Python 子进程，运行 `web_server.py`
4. 等待 FastAPI 就绪（检测 8000 端口）
5. 打开 BrowserWindow 加载 UI
6. UI 通过 WebSocket 连接后端

### 窗口管理

- 默认窗口尺寸：900 x 650 px
- 可调整大小，最小 800 x 600
- 关闭主窗口时：优雅终止 Python 子进程（发送 SIGTERM，等待 5s 超时后强制杀死）

---

## 四、错误处理

| 场景 | 处理方式 |
|------|---------|
| Python 后端启动失败 | 显示错误弹窗，退出 Electron |
| WebSocket 连接断开 | 自动重连（3次重试，间隔 2s），重连后不恢复状态，前端显示 idle |
| 任务执行异常 | 日志输出 ERROR，状态置为 error |
| 游戏窗口未找到 | 后端抛异常，前端显示错误日志 |
| Python 进程意外退出 | 前端状态置为 stopped，提示重新启动 |

---

## 五、测试策略

- **前端单元测试：** 使用 Playwright 测试 UI 组件
- **集成测试：** Mock WebSocket，测试前端状态流转
- **E2E 测试：** 启动完整 Electron + FastAPI，验证任务启动/停止流程

---

## 六、技术依赖

- Electron ^28.0.0
- Python 3.11+
- 现有 FastAPI + WebSocket 基础设施（已实现）
- 无需新增 Python 依赖
