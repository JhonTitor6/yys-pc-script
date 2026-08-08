# P0/P1 桌面工作台总体设计

## 边界

```text
脚本/控制器
  -> RunManager（生命周期、阶段、动作、错误与证据）
  -> Storage（run、日志、快照、证据、工作流、调度字段）
  -> FastAPI（规范化快照、历史详情、控制/调度命令）
  -> EventHub（带序号的增量事件 + 重连快照）
  -> 原生 GUI（状态 reducer、运行现场、历史/调度视图）
```

P0 只改变运行事实的表达和读取方式，不改变具体游戏脚本的识别/点击逻辑。P1 复用 P0 的运行快照和事件，不在前端另造一套状态机。

## 统一数据契约

运行快照对外至少包含：

```json
{
  "id": 1,
  "run_id": 1,
  "task_id": "soul_raid",
  "workflow_id": null,
  "step_id": null,
  "action_id": null,
  "status": "running",
  "stage": "script_running",
  "progress": {"current": 2, "total": 103, "percent": 1.9},
  "error_code": null,
  "error_message": null,
  "retry_count": 0,
  "available_actions": ["pause", "stop"],
  "config": {},
  "latest_snapshot": {},
  "latest_evidence": null,
  "updated_at": "2026-08-08T00:00:00Z"
}
```

字段扩展采用 SQLite 增量迁移和 JSON 兼容读取；保留 `id`、旧状态值和既有 endpoint 响应字段。没有活动 run 时返回 `null`（旧 API 兼容），WebSocket 额外发送 `run_snapshot` 的 `snapshot: null`。

## 事件契约

EventHub 在唯一入口补齐 `seq`、`event_id`、`timestamp`，业务事件仍保留原 `type` 与原字段。重连流程为：

1. WebSocket 接受后发送当前规范化快照。
2. 根据 `after_seq` 回放该序号之后的事件；没有参数时回放近期事件以兼容旧客户端。
3. GUI 先用快照覆盖状态，再按序号应用事件；重复序号忽略。

## 失败与证据

RunManager 在启动异常、脚本异常和停止超时路径统一写入错误码、错误日志和 `run_evidence` 记录。截图捕获器只依赖脚本当前已有的控制器/图像缓存能力；捕获失败记录 `capture_error`，不构造虚假图片。证据通过 API 读取，GUI 不直接访问数据库或任意本地路径。

## P1 兼容与调度

- `ConfigField` 新增的说明/单位/敏感性均有默认值；旧注册表无需同时修改即可工作。
- workflow/step 新字段通过 `ALTER TABLE` 只增不删；旧 `failure_policy` 映射为 stop/continue/retry 语义。
- `SchedulerService` 由一个时间计算函数同时生成预览和实际触发时间；应用生命周期启动/停止后台调度线程，手动触发仍走现有异步接口。
- 调度线程只调用 RunManager 单执行槽；槽被占用时发布 `scheduler_status`，不创建第二个脚本线程。

## 回滚形状

新增列和表均可被旧代码忽略；API 新字段为附加字段。若调度线程或前端视图出现问题，可关闭调度启动并继续使用手动运行/执行页，不需要回滚已有运行记录。
