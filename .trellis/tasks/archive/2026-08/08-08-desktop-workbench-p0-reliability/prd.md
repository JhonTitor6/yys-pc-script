# P0 运行可靠性与可观察性

## Goal

在不改变既有脚本执行语义的前提下，建立连接、运行、工作流步骤、原子动作四层状态的可观察闭环，让用户无需读源码即可判断“哪里失败、为什么失败、现在能做什么”。

## Confirmed facts and anchors

- `ui_backend/models.py:15` 只有运行状态枚举，`RunRequest` 仅覆盖脚本、配置和工作流关联。
- `ui_backend/runs/manager.py:32` 使用 `_active_run_id` 实现单执行槽；`_run_script` 在 `:155` 记录最终快照和异常日志，但失败没有统一错误码、步骤/动作上下文或证据记录。
- `ui_backend/storage/database.py:59` 的 `runs` 表只有状态、配置、时间和错误文本；`run_logs`、`state_snapshots` 已存在。
- `ui_backend/events/hub.py:11` 可广播并保留近期事件，但事件没有统一序号/时间/运行快照，WebSocket 只回放近期事件。
- `ui_backend/app.py:29` 的 `/api/runs/current` 直接返回数据库 run，刷新时没有补发快照、日志和可用动作。
- `gui/renderer.js:759` 重连只再次连接并刷新 current run；`gui/index.html` 的主控制区没有完整的恢复操作或证据展示。

## Requirements

### P0-1 状态与快照契约

- 定义连接状态、运行状态、工作流步骤状态和原子动作状态；既有运行状态字符串继续兼容。
- 规范化运行快照至少包含 `run_id/task_id/workflow_id/step_id/status/stage/progress/error_code/error_message/retry_count/available_actions/config/updated_at`，并能关联最新日志、状态快照和证据。
- `available_actions` 必须由后端状态计算：运行中可暂停/停止，暂停可恢复/停止，失败可重试/跳过/停止/人工接管；已完成状态不暴露不可用动作。

### P0-2 事件与重连

- 所有 WebSocket 事件统一包含事件类型、序号、时间和运行标识；保留现有 `log`、`run_status_changed`、`state_snapshot` 事件的兼容字段。
- 新连接先收到当前运行快照，再接收指定序号之后的增量事件；无活动运行时也明确返回空闲快照。
- API 与 WebSocket 使用同一规范化快照，前端重连后不能依赖事件顺序猜测当前状态。

### P0-3 失败证据

- 脚本异常、启动失败和停止超时都要关联错误码、步骤/动作上下文、错误日志和证据记录。
- 真实运行优先从脚本当前截图缓存或控制器截图捕获 PNG；捕获失败必须记录原因，不能伪造成功证据。
- 提供按 run 查询日志、最新快照和证据的接口，前端至少展示错误摘要、关键日志和最新可用截图。

### P0-4 恢复动作

- 提供 retry、skip、stop、manual takeover 四类基础动作接口；未实现的编排恢复能力不得返回成功。
- 重试使用原 run 的脚本/配置/来源上下文创建新 run；跳过和人工接管要留下可审计事件；停止沿用现有停止语义。

### P0-5 首屏可观察性

- 首屏同时显示连接状态、当前阶段、进度、来源/配置、实时日志、关键错误、最新截图和状态驱动的控制按钮。
- 页面刷新、页面切换和 WebSocket 重连后保留当前运行控制入口。

## Acceptance Criteria

- [x] 运行成功、暂停、恢复、停止、启动异常和脚本异常均能通过规范化快照表达，且旧 API 返回字段仍可用。
- [x] 失败快照至少包含非空错误码和错误日志；真实截图可用时存在可读取证据路径/接口，截图不可用时明确记录捕获失败原因。
- [x] `GET /api/runs/current` 和 WebSocket 首条快照给出相同的运行标识、状态和可用动作；重连后可继续收到增量事件。
- [x] retry/skip/stop/manual takeover 的可用性和执行结果受状态约束；无效状态返回明确的 4xx/错误，不改变既有运行事实。
- [x] GUI 的控制按钮与 `available_actions` 一致；用户可看到失败步骤、错误原因、关键日志和最新证据。
- [ ] 新增后端单元/API/WebSocket 测试通过，既有 `tests/ui_backend` 不因契约扩展回归。

## 验收记录

- P0 定向 API、存储、运行管理和可观察性测试：35 passed。
- 完整 `tests/ui_backend`：63 passed，1 个既有 `realm_raid` 默认值断言失败，详见 P1 验收记录。

## Out of scope

- 不实现游戏脚本自动续跑，不修改游戏脚本的识别、点击和场景逻辑，不强杀无法退出的 Python 线程。
