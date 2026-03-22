# yys-pc-script 项目记忆

## 项目概述
阴阳师 PC 端自动化脚本，基于事件驱动架构，支持后台运行。

## UI 界面开发进度

### 已完成
- Electron 主进程 (gui/main.js) - Python 后端启动 + IPC
- preload.js 简化 - 移除未使用的 IPC
- web_server.py - 配置传递支持 (max_battle_count)
- gui/index.html - 深色主题 UI (纯 HTML/CSS/JS，无外部依赖)
- config/ui_config.json - UI 配置文件

### 技术架构
```
gui/
├── main.js       # Electron 主进程
├── preload.js    # 预加载脚本（窗口控制 IPC）
├── index.html    # 深色主题 UI
└── package.json

web_server.py    # FastAPI + WebSocket 后端
```

### 待办
1. config/ui_config.json 尚未被 UI 加载（目前用 localStorage）
2. loop_interval 配置未实现
3. 完整流程验证（任务启动/暂停/恢复/停止）
4. Electron 打包（electron-builder）

### 已知问题
- loguru 日志在 Windows 终端显示乱码（不影响功能）
- UI 用 localStorage 存储配置，而非 config/ui_config.json

## 分支状态
- master: 完成 UI 实现，但有 bug 待修复

## 最近提交
- 772dced: fix(web_server): remove loguru encoding config causing errors
- d178b0b: fix(web_server): add UTF-8 encoding for loguru
- d7166e1: fix(web_server): use logger.add() instead of logger.configure()
- 8517d2b: fix(gui): address XSS vulnerability and JSON parse error
- b657b02: refactor(gui): replace UI with dark theme design
- 74f2660: feat(web_server): support config parameter in TaskExecutor
- ff0c534: fix(gui): address code quality issues
- cb635f3: fix(gui): add Python backend spawn and IPC handlers

## 运行方式
```bash
cd gui && npm install && npm start
```
