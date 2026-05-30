# 阴阳师脚本桌面工作台设计

## 背景

`yys-pc-script` 已有事件驱动脚本、FastAPI WebSocket 后端雏形和 Electron UI 原型。本次目标是将现有“启动单个脚本”的界面升级为本地桌面工作台，覆盖单脚本执行、脚本编排、执行日志和进度状态记录。

本设计面向第一版可交付桌面工具。用户入口为 Electron 桌面窗口，Electron 启动时自动拉起 Python 后端；关闭主窗口默认隐藏到系统托盘，调度器继续运行；用户选择真正退出时才停止后端。

## 目标

- 支持从桌面界面选择脚本并执行。
- 支持根据脚本参数 schema 渲染脚本特有参数表单。
- 支持可命名、可分组、可持久化的编排任务。
- 支持定时、间隔、顺序步骤和“运行到指定时间”的编排表达。
- 支持实时展示当前运行日志，并持久化每次执行的历史记录。
- 支持记录脚本结构化状态，如已战斗次数、胜利次数、狭间暗域挑战记录。
- 第一版只记录和展示进度状态，不从快照自动恢复执行。

## 非目标

- 第一版不支持多客户端并行执行。
- 第一版不支持一个客户端同时运行多个脚本。
- 第一版不实现 Windows 后台服务或完全退出后继续调度。
- 第一版不实现自动识别游戏场景并从快照续跑。
- 第一版不重构具体游戏脚本的核心识别和点击逻辑。

## 核心决策

### 产品形态

采用“本地桌面工作台”形态：

- Electron 是用户入口，负责窗口、托盘、Python 后端进程生命周期。
- Python 后端继续使用 FastAPI，负责脚本注册、执行、编排、日志和状态持久化。
- 前端采用工作台布局，执行页是唯一运行现场，编排页只负责任务定义。

### 脚本范围

脚本列表分为稳定脚本和实验脚本：

- 稳定脚本默认展示，例如御魂、结界突破、探28、御灵。
- 实验脚本折叠展示，例如狭间暗域、斗技和活动脚本。
- 脚本注册表保留分类字段，后续可以调整脚本所属类别。

### 执行模型

第一版只有一个全局执行槽：

- 手动执行和编排触发都必须经过 `RunManager`。
- 当已有脚本运行时，新任务进入队列、跳过或按编排失败策略处理。
- UI 和调度逻辑都按单客户端处理。
- 数据模型可预留 `client_id`，但第一版不在 UI 中暴露多客户端能力。

### 参数 schema

采用混合 schema 方案：

- 第一版通过集中注册表快速定义脚本参数。
- 后续脚本类可以提供类内 schema。
- 类内 schema 优先于集中注册表。
- 前端只根据后端返回的 schema 渲染表单，不为具体脚本写定制表单。

### 断点状态

第一版实现“进度记录与展示”：

- 通用脚本状态包含已战斗次数、胜利次数、最大战斗次数、运行时长。
- 复杂脚本可以上报专属状态，例如狭间暗域当前区域、敌人类型、挑战计数。
- 状态快照写入数据库并推送到执行页。
- 快照不写回脚本，也不用于自动续跑。

## 架构

整体分为三层：

```text
Electron 桌面层
  - 主窗口工作台
  - 系统托盘
  - Python 后端进程管理
        |
        | HTTP + WebSocket
        v
FastAPI 后端层
  - ScriptRegistry：脚本发现、分类、参数 schema
  - RunManager：单客户端全局执行槽
  - Scheduler：编排队列、定时和间隔触发
  - LogHub：实时日志推送和历史日志写入
  - StateTracker：结构化状态快照
        |
        v
持久化与脚本层
  - SQLite：编排、运行历史、日志、状态快照
  - JSON：默认脚本注册和 UI 偏好
  - YYSBaseScript：暂停、恢复、停止、状态上报接口
```

### Electron 桌面层

Electron 负责桌面体验和后端生命周期：

- 启动应用时拉起 Python 后端。
- 监听后端端口就绪后加载 UI。
- 主窗口关闭时默认隐藏到托盘。
- 托盘菜单提供显示窗口、暂停当前脚本、停止当前脚本、退出应用。
- 真正退出时优雅停止调度器和 Python 后端。

Electron 不直接调用游戏脚本，也不直接读写业务数据库。

### FastAPI 后端层

现有 `web_server.py` 会拆分为模块化后端：

- `ui_backend/app.py`：FastAPI 应用入口。
- `ui_backend/scripts/registry.py`：脚本注册和 schema 合并。
- `ui_backend/runs/manager.py`：运行槽、线程生命周期、暂停恢复停止。
- `ui_backend/scheduler/service.py`：编排调度和步骤推进。
- `ui_backend/storage/`：SQLite 初始化、仓库类、迁移。
- `ui_backend/events/hub.py`：WebSocket 事件广播。

后端通过 HTTP 提供查询和命令接口，通过 WebSocket 推送实时事件。

### 持久化层

SQLite 保存会变化的运行事实：

- 编排任务和步骤。
- 每次执行的 run 记录。
- run 日志。
- run 状态快照。
- 应用设置。

JSON 只用于较静态的默认注册和偏好配置，例如脚本分类、默认参数和最近选择。

## 页面设计

页面视觉方向采用原型 A“控制台工作台”：

- 整体为深色工具型界面，强调长时间运行时的可读性和状态稳定感。
- 左侧为窄图标导航栏，承载执行、编排、进度、日志、设置等主入口。
- 脚本列表位于导航栏右侧，以单列形式展示；点击脚本后在列表内展开参数编辑。
- 主区域是唯一运行现场，上方展示当前运行脚本、来源、参数和进度，下方大面积展示实时日志。
- 右侧辅助栏展示调度预告、断点快照和关键日志摘要。
- 控制按钮使用明确的图标或短文本，状态色保持克制：绿色表示运行或成功，黄色表示等待或警告，红色表示停止或错误。

### 执行页

执行页是唯一运行现场。

左侧为单列脚本列表：

- 稳定脚本默认展开在主列表。
- 实验脚本位于折叠区。
- 点击脚本后在列表内展开参数编辑。
- 参数表单由脚本 schema 渲染。
- 用户可以保存当前参数为该脚本默认值。

右侧为运行时区域：

- 当前运行脚本名称。
- 运行来源：手动执行或编排触发。
- 本次运行参数。
- 当前进度摘要。
- 启动、暂停、恢复、停止按钮。
- 大面积实时日志区域。

编排触发的脚本也统一在执行页展示。

### 编排页

编排页只负责编排任务定义，不承载运行现场。

功能包括：

- 创建、编辑、删除编排任务。
- 自定义任务名称。
- 按分组管理任务，例如日常、活动、临时。
- 启用或禁用编排任务。
- 立即运行某个编排任务。
- 编辑步骤顺序、脚本参数、时间条件和失败策略。

示例：

- “斗技挂机到 21:03 → 狭间暗域”。
- “200 次探索 → 结界突破 → 200 次探索 → 结界突破”。

当编排真正触发脚本后，运行过程统一进入执行页。

### 进度页

进度页用于回看最近状态快照：

- 当前 run 的最新状态。
- 最近历史 run 的最终状态。
- 按脚本展示关键计数。
- 对有结构化状态的脚本展示专属字段。

第一版不提供“从快照继续运行”按钮。

### 日志页

日志页用于历史回看：

- 按 run 查看完整日志。
- 按脚本、编排来源、状态和时间过滤。
- 展示开始时间、结束时间、耗时、最终状态。
- 支持查看错误摘要和 traceback 摘要。

实时日志仍以执行页为主。

### 设置页

设置页管理本地偏好：

- Python 路径。
- 后端端口。
- 关闭窗口行为。
- 日志保留天数或最大条数。
- 默认打开页面。

## 数据模型

### 脚本定义

脚本定义主要来自注册表和类内 schema，不作为主要业务表保存。

字段包括：

- `script_id`：稳定唯一标识，例如 `soul_raid`。
- `display_name`：界面展示名，例如 `御魂`。
- `module_path`：脚本类导入路径。
- `class_name`：脚本类名。
- `category`：`stable` 或 `experimental`。
- `description`：脚本说明。
- `config_schema`：参数 schema。
- `default_config`：默认参数。

### workflows

保存编排任务元数据。

- `id`：主键。
- `name`：自定义名称。
- `group_name`：分组名称。
- `enabled`：是否启用。
- `trigger_type`：手动、定时、间隔。
- `trigger_config_json`：触发配置。
- `failure_policy`：失败策略。
- `created_at`：创建时间。
- `updated_at`：更新时间。

### workflow_steps

保存编排步骤。

- `id`：主键。
- `workflow_id`：所属编排任务。
- `sort_order`：步骤顺序。
- `step_type`：`run_script`、`wait_duration`、`run_until_time`。
- `script_id`：脚本步骤关联的脚本。
- `config_json`：该步骤使用的脚本参数。
- `condition_json`：等待时长、目标时间等条件。
- `retry_count`：失败重试次数。

### runs

保存每次脚本执行记录。

- `id`：主键。
- `script_id`：执行脚本。
- `source_type`：`manual` 或 `workflow`。
- `workflow_id`：来源编排任务，可为空。
- `workflow_step_id`：来源步骤，可为空。
- `status`：`queued`、`running`、`paused`、`success`、`error`、`stopped`。
- `config_json`：本次执行参数。
- `started_at`：开始时间。
- `ended_at`：结束时间。
- `error_message`：错误摘要。

### run_logs

保存运行日志。

- `id`：主键。
- `run_id`：所属 run。
- `level`：日志级别。
- `message`：日志内容。
- `created_at`：日志时间。

### state_snapshots

保存结构化状态快照。

- `id`：主键。
- `run_id`：所属 run。
- `script_id`：脚本标识。
- `state_json`：状态内容。
- `created_at`：快照时间。

示例状态：

```json
{
  "battle_count": 45,
  "victory_count": 43,
  "max_battle_count": 103,
  "abyss_area": "abyss_dragon",
  "challenge_counts": {
    "boss": 1,
    "commander": 2,
    "elite": 3
  }
}
```

## 后端接口

### HTTP 接口

- `GET /api/scripts`：获取脚本列表和参数 schema。
- `GET /api/runs/current`：获取当前 run。
- `POST /api/runs/start`：手动启动脚本。
- `POST /api/runs/{run_id}/pause`：暂停脚本。
- `POST /api/runs/{run_id}/resume`：恢复脚本。
- `POST /api/runs/{run_id}/stop`：停止脚本。
- `GET /api/runs`：查询历史 run。
- `GET /api/runs/{run_id}/logs`：查询 run 日志。
- `GET /api/runs/{run_id}/snapshots`：查询 run 状态快照。
- `GET /api/workflows`：查询编排任务。
- `POST /api/workflows`：创建编排任务。
- `PUT /api/workflows/{workflow_id}`：更新编排任务。
- `DELETE /api/workflows/{workflow_id}`：删除编排任务。
- `POST /api/workflows/{workflow_id}/run-now`：立即运行编排任务。
- `POST /api/workflows/{workflow_id}/enable`：启用编排任务。
- `POST /api/workflows/{workflow_id}/disable`：禁用编排任务。

### WebSocket 事件

`WS /ws/events` 推送实时事件：

- `run_started`：run 开始。
- `run_status_changed`：状态变化。
- `log`：实时日志。
- `state_snapshot`：状态快照。
- `workflow_event`：编排任务触发、步骤开始、步骤结束。
- `scheduler_status`：调度器状态变化。

前端断线重连后先调用 `GET /api/runs/current` 拉取当前状态，再继续接收 WebSocket 事件。

## 编排语义

### 步骤类型

`run_script`：

- 启动指定脚本。
- 使用步骤自己的参数。
- 脚本结束后根据结果推进下一步。

`wait_duration`：

- 等待指定时长。
- 不占用执行槽。

`run_until_time`：

- 启动指定脚本并运行到目标时间。
- 到点后请求停止当前脚本。
- 停止完成后推进下一步。

### 触发类型

`manual`：

- 用户点击立即运行。

`scheduled_time`：

- 在指定时间触发。

`interval`：

- 按固定间隔触发。

### 失败策略

`stop_workflow`：

- 当前步骤失败后停止整个编排。

`continue_next`：

- 当前步骤失败后记录错误并进入下一步。

`retry_then_stop`：

- 当前步骤失败后重试指定次数，仍失败则停止编排。

## 运行与错误处理

### 脚本生命周期

继续复用现有 `YYSBaseScript` 的生命周期接口：

- `run()`：启动主循环。
- `pause()`：暂停。
- `resume()`：恢复。
- `stop()`：请求停止。

`RunManager` 在独立线程中运行脚本，并负责：

- 创建 run。
- 注入参数。
- 捕获 stdout、stderr 和 loguru 日志。
- 推送运行事件。
- 写入 run 状态、日志和快照。
- 恢复线程环境。

### 停止语义

停止当前脚本时：

1. 调用脚本 `stop()`。
2. 等待线程在超时时间内退出。
3. 如果正常退出，run 标记为 `stopped`。
4. 如果超时未退出，run 标记为 `stopped`，并写入停止超时日志。

第一版不强杀 Python 线程。

### 常见错误

找不到游戏窗口：

- run 标记为 `error`。
- 执行页提示检查游戏窗口。
- 编排按失败策略处理。

脚本异常：

- run 标记为 `error`。
- 保存错误摘要和 traceback 摘要。
- 执行页显示错误日志。

后端连接断开：

- 前端显示重连状态。
- 重连成功后拉取当前 run。
- 无法重连时提示重启应用。

编排触发时执行槽被占用：

- 按编排配置处理：排队、跳过或停止当前编排。
- 第一版默认排队。

## 测试策略

### 后端测试

使用 pytest 覆盖：

- 脚本注册表加载和 schema 合并。
- SQLite 仓库的创建、更新、查询。
- `RunManager` 单执行槽约束。
- 手动启动、暂停、恢复、停止状态流转。
- `Scheduler` 顺序步骤推进。
- `run_until_time` 到点停止语义。
- 编排失败策略。
- 状态快照写入。

测试使用 Mock 脚本，不依赖游戏窗口。

### 前端测试

使用浏览器自动化覆盖：

- 执行页脚本列表展开和参数编辑。
- 手动启动后运行区域展示。
- 实时日志渲染。
- 编排任务创建、分组和步骤编辑。
- 编排立即运行后跳转或聚焦执行页。
- 断线重连后的状态恢复显示。

### 集成测试

使用 FastAPI TestClient 或本地服务测试：

- HTTP API 和 WebSocket 事件一致性。
- run 日志同时进入数据库和实时事件。
- 编排触发后执行页能看到对应 run。

真实游戏窗口相关验证作为手动集成测试，不纳入默认单元测试。

## 迁移计划

第一阶段：

- 新增模块化后端目录。
- 初始化 SQLite 仓库。
- 实现脚本注册表和基础 API。
- 保留旧 `web_server.py` 作为过渡入口或将其改为新应用入口。

第二阶段：

- 实现 `RunManager`。
- 接入现有脚本执行、参数注入、暂停恢复停止。
- 实现日志和状态快照持久化。

第三阶段：

- 重写 Electron UI 为桌面工作台。
- 实现执行页、日志页和基础设置。

第四阶段：

- 实现编排任务持久化和调度器。
- 支持分组、命名、顺序步骤、定时、间隔和运行到指定时间。
- 接入托盘后台运行。

第五阶段：

- 为御魂、探索、结界突破、御灵补齐参数 schema。
- 为狭间暗域补齐结构化状态上报。
- 补充自动化测试和手动集成测试说明。

## 验收标准

- 打开 Electron 后能自动启动后端并进入工作台。
- 执行页能展示稳定脚本和折叠的实验脚本。
- 点击脚本能展开参数编辑并启动脚本。
- 当前运行区域能展示脚本、来源、参数、进度和实时日志。
- 每次执行都能在历史记录中查看日志和最终状态。
- 能创建带名称和分组的编排任务。
- 编排任务重启应用后仍存在。
- 编排任务能按顺序执行多个脚本步骤。
- “运行到指定时间”能在到点后停止当前脚本并进入下一步。
- 关闭主窗口后应用进入托盘，已启用的调度继续生效。
- 真正退出应用后后端和调度器停止。
- 第一版不会尝试从快照自动恢复脚本执行。

## 第一版实现备注

- 编排页第一版支持创建、列表和立即运行；编辑、删除、启用、禁用仍保留为后续能力。
- `failure_policy` 第一版会持久化，调度执行暂按失败即停止处理；`continue_next` 和 `retry_then_stop` 后续补齐。
- `progress`、`logs`、`settings` 导航入口暂禁用，当前实时状态与日志集中在执行页。
- 后端接口第一版已实现脚本列表、当前运行、启动与控制、运行日志和快照、编排列表、创建和立即运行；历史 run 查询、编排更新、删除、启停仍按设计保留。
- 编排等待步骤使用 `condition.seconds`，运行到指定时间使用 `condition.until`。
- Electron 启动时会生成一次性 UI token，并传给 Python 后端和渲染进程；启用 token 后 `/api/*` 和 `/ws/events` 会拒绝未授权请求。

## 2026-05-31 验证记录

- `D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend tests/common/test_yys.py::test_base_script_state_snapshot -v`：30 passed。
- `D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/ yys/soul_raid/test_soul_raid.py -v`：50 passed，3 failed；失败为既有基线：`test_config_persistence`、`TestYYS.test_ocr`、`TestYYS.test_yuhun`。
- `D:/ProgramData/anaconda3/envs/win_macro/python.exe -m ui_backend.main` + `/api/scripts`：后端启动并返回脚本列表。
- `cd gui; npm start`：本机 `electron` 命令不可用，未完成窗口和托盘手动验证；需安装前端依赖后复测。

## 2026-06-01 最终验证记录

- `D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend tests/common/test_yys.py::test_base_script_state_snapshot -v`：38 passed。
- `node tests/gui/test_backend_detection.js`、`node --check gui/main.js`、`node --check gui/preload.js`、`node --check gui/renderer.js`、`git diff --check`：均通过。
- `D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/ yys/soul_raid/test_soul_raid.py -v`：49 passed，4 failed；失败为既有或环境型问题：`test_config_persistence`、`TestYYS.test_find_window`、`TestYYS.test_ocr`、`TestYYS.test_yuhun`。
- `D:/ProgramData/anaconda3/envs/win_macro/python.exe -m ui_backend.main` + `/api/scripts`：后端启动并返回脚本列表。
- `cd gui; npm start`：本机 `electron` 命令不可用，未完成窗口和托盘手动验证；需安装前端依赖后复测。
