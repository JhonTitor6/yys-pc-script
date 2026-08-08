# P0 运行可靠性与可观察性设计

## 数据流和状态边界

```text
脚本生命周期/日志/截图
  -> RunManager：解析阶段、动作、错误码，计算 available_actions
  -> RunRepository：保存运行快照字段
  -> EventHub：为同一快照发布带 seq 的事件
  -> API current / WebSocket run_snapshot
  -> GUI：先恢复快照，再按 seq 更新日志、进度和按钮
```

连接状态由 GUI 管理，运行/步骤/动作状态由后端管理；连接状态不能覆盖运行状态。工作流步骤沿用已有 `workflow_id/workflow_step_id`，对外提供 `step_id` 别名；原子动作先以当前 RunManager 生命周期动作（start/pause/resume/stop/retry/skip/manual）表示，不要求改造所有游戏脚本内部操作。

## 后端改动

- `models.py`：增加四层状态枚举和快照/恢复动作常量，扩展 `RunRequest` 的 task/step/action 上下文。
- `database.py` / `repositories.py`：为 runs 增加阶段、进度、错误码、重试次数、可用动作、最新证据等可空列；增加证据表和列表/详情查询；初始化时执行幂等增量迁移。
- `events/hub.py`：统一序列化事件元数据，支持按序号读取；不破坏现有近期事件测试。
- `runs/manager.py`：集中更新状态快照、恢复动作和失败证据；旧 `start/pause/resume/stop/wait` 方法签名继续工作。
- `app.py`：提供 current snapshot、历史/详情、evidence 和 retry/skip/manual takeover API；WebSocket 首包先发送快照。

## 状态和错误规则

| 状态 | 可用动作 |
| --- | --- |
| queued | stop |
| running | pause, stop |
| paused | resume, stop |
| error | retry, skip, stop, manual_takeover |
| success/stopped/skipped/manual | 无 |

错误码至少包括 `SCRIPT_START_FAILED`、`SCRIPT_EXCEPTION`、`STOP_TIMEOUT`、`BACKEND_RESTART`，并保留原始 traceback 在日志中。`retry` 建立新 run，`skip`/`manual_takeover` 更新原 run 的审计状态并发布事件。

## 前端边界

`renderer.js` 增加一个以快照为源的 `state.currentRun` reducer 和通用 `renderRunSnapshot`，主运行区域与脚本卡片共用 `available_actions`；证据只通过后端 URL 加载。连接状态只负责显示“连接中/已连接/重连中”，不把断线误报为空闲。

## 验证

- 用 FakeScript 覆盖成功、异常、停止超时、重试和动作约束。
- 用 FastAPI TestClient 覆盖 current/history/evidence、WebSocket 快照优先和 `after_seq`。
- 用 Node 语法检查和现有 GUI 后端检测验证前端兼容。
