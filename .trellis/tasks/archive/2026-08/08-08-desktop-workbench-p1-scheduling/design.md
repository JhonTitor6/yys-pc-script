# P1 任务工作台与调度体验设计

## 后端数据边界

- `ConfigField` 是脚本参数唯一 schema 来源；API 序列化 `description/unit/sensitive`，GUI 只按 schema 渲染。
- workflow 增加 `priority/success_interval_seconds/failure_interval_seconds/next_run_at`；step 增加 `failure_policy`。迁移只增列，旧数据使用 `manual`、优先级 0 和默认间隔。
- `RunRepository.list` 返回规范化摘要；详情接口组合 run、workflow/step、日志、最新快照和证据，避免前端拼接数据库字段。

## 失败策略

执行单个步骤后读取 run 终态：

1. 成功：发布步骤完成事件并进入下一步。
2. `stop`：发布失败并停止工作流。
3. `continue/skip`：记录跳过原因并进入下一步。
4. `retry`：按步骤 `retry_count` 或工作流策略的次数重新提交，耗尽后停止。
5. `manual`：发布 `manual_intervention_required`，保留恢复入口，不假装继续。

旧值 `stop_workflow/continue_next/retry_then_stop` 保持可读并映射到上述语义。

## 调度算法

使用一个纯函数计算 `next_run_at`：

- `manual`：无下一次时间。
- `interval`：以上次终态时间加成功/失败间隔。
- `scheduled_time`：按本地时区的 `HH:MM` 计算下一次未来触发；已过时滚到下一天。

同一轮按 `priority DESC, id ASC` 选择任务。预览和后台线程都调用同一函数；线程只在应用生命周期内运行，单执行槽占用时发布状态事件并等待下一轮。

## 前端信息架构

- 执行：当前唯一运行现场，保留左侧任务区/中央运行区/右侧证据区。
- 工作流：任务定义和步骤编辑，不承载实时运行控制。
- 进度：当前快照和最近 run 摘要。
- 日志/历史：历史列表、过滤和详情；实时日志仍在执行页。
- 设置：展示当前连接/调度能力和明确的暂不支持项。

页面组件保持原生 JS 函数边界：`renderConfigField`、`renderRunSnapshot`、`renderHistory`、`renderSchedulePreview`、`renderWorkflowStep`；不新增构建链。

## 验证

- schema 元数据和旧注册表兼容测试。
- workflow/step 迁移、策略推进、历史详情和调度时间计算测试。
- 前端 Node 语法/后端检测及必要的浏览器静态 DOM 测试。
