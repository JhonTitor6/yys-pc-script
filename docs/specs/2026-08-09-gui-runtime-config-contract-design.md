# GUI 运行状态与配置字段冻结规格

- 状态：已冻结，作为 GUI 进入开发前的跨层契约
- 日期：2026-08-09
- 范围：桌面 GUI 的运行态展示、运行控制、脚本配置表单和启动请求
- 非范围：本次不修改后端运行语义、不实现热更新、不新增脚本配置字段、不接真实 GUI

这份规格以当前后端代码为准。原型中的展示字段可以继续作为视觉占位，但进入开发时必须按本文的真实字段和动作来源收敛。

## 1. Scope / Trigger

### 1.1 触发场景

以下场景都必须使用本文契约：

1. 打开运行页并读取当前运行。
2. 选择脚本并从脚本定义生成配置表单。
3. 保存脚本配置偏好。
4. 启动、暂停、恢复、停止、继续等待、重试、跳过或人工接管。
5. REST、WebSocket 或重新连接后刷新运行状态。

### 1.2 设计边界

- 后端规范化运行快照是 UI 的唯一状态来源。
- `available_actions` 是按钮显示、可用性和控制权限的唯一来源。
- 脚本 `config_schema` 是配置表单和请求字段的唯一来源。
- 运行进入 `queued`、`running` 或 `paused` 后，当前运行的配置全部只读；停止请求进入终态前也保持只读。
- 配置保存只影响下一次启动，不注入当前运行实例。

## 2. Signatures

### 2.1 运行相关接口

| 接口 | 输入 | 输出/用途 |
| --- | --- | --- |
| `GET /api/runs/current` | 无 | 当前活动运行的规范化快照；没有活动运行时为 `null` |
| `GET /api/runs/{run_id}` | `run_id` | 单次运行详情，另含 `logs`、`snapshots`、`evidence` |
| `POST /api/runs/start` | `script_id`、`config`，以及可选的来源和工作流字段 | 创建运行，返回 `{ "id": number }` |
| `POST /api/runs/{run_id}/pause` | `run_id` | 暂停当前允许暂停的运行 |
| `POST /api/runs/{run_id}/resume` | `run_id` | 恢复当前允许恢复的运行 |
| `POST /api/runs/{run_id}/stop` | `run_id` | 请求停止运行 |
| `POST /api/runs/{run_id}/continue-waiting` | `run_id` | 安全进入等待超时时继续等待 |
| `POST /api/runs/{run_id}/retry` | `run_id` | 为失败运行创建关联重试运行 |
| `POST /api/runs/{run_id}/skip` | `run_id` | 跳过失败运行 |
| `POST /api/runs/{run_id}/manual-takeover` | `run_id` | 将失败运行转人工接管 |

动作名称到接口的固定映射如下：

```text
pause             -> POST /api/runs/{run_id}/pause
resume            -> POST /api/runs/{run_id}/resume
stop              -> POST /api/runs/{run_id}/stop
continue_waiting  -> POST /api/runs/{run_id}/continue-waiting
retry             -> POST /api/runs/{run_id}/retry
skip              -> POST /api/runs/{run_id}/skip
manual_takeover   -> POST /api/runs/{run_id}/manual-takeover
```

### 2.2 配置相关接口

| 接口 | 输入 | 输出/用途 |
| --- | --- | --- |
| `GET /api/scripts` | 无 | 返回脚本定义、`config_schema` 和合并后的 `default_config` |
| `PATCH /api/scripts/{script_id}/config` | 与 schema 对应的键值对象 | 保存用户偏好；当前固定返回 `saved: true`、`applied: false`，并说明下次启动生效 |
| `POST /api/runs/start` | `{ script_id, config, ... }` | 将本次配置注入新建运行；`config` 只允许使用选中脚本的真实 schema 键 |

### 2.3 规范化运行快照

`GET /api/runs/current`、运行详情和事件推送使用相同含义的快照字段。当前存储层规范化后的核心字段为：

```json
{
  "id": 1,
  "run_id": 1,
  "run_uuid": "",
  "script_id": "soul_raid",
  "task_id": "soul_raid",
  "source_type": "manual",
  "workflow_id": null,
  "workflow_step_id": null,
  "step_id": null,
  "action_id": null,
  "status": "running",
  "stage": "script_running",
  "progress": {},
  "config": {},
  "started_at": null,
  "ended_at": null,
  "error_code": null,
  "error_message": null,
  "retry_count": 0,
  "available_actions": ["pause", "stop"],
  "latest_evidence": null,
  "parent_run_id": null,
  "updated_at": ""
}
```

字段的空值、时间格式和额外字段以实际 API 返回为准；GUI 不得通过日志内容推断 `status`、`stage` 或动作。

### 2.4 冻结动作矩阵

| `status` | `stage` | `available_actions` | GUI 行为 |
| --- | --- | --- | --- |
| `queued` | 任意 | `stop` | 显示停止 |
| `running` | `preparing`、`waiting_safe_entry`、`navigating`、`verifying_entry` 或其他未单独列出的阶段 | `stop` | 只显示停止 |
| `running` | `waiting_safe_entry_timeout` | `continue_waiting`、`manual_takeover`、`stop` | 按返回数组显示三个动作 |
| `running` | `script_running` | `pause`、`stop` | 显示暂停和停止 |
| `paused` | 任意 | `resume`、`stop` | 显示恢复和停止 |
| `error` | 任意 | `retry`、`skip`、`stop`、`manual_takeover` | 显示返回的四个恢复动作 |
| `manual` | 任意 | `retry` | 只显示重试 |
| `success`、`stopped`、`skipped` | 任意 | `[]` | 不显示运行控制 |

实现规则：

- 顶部朱红色“停止”按钮仅在当前快照的 `available_actions` 包含 `stop` 时显示。
- 运行页的暂停、恢复、继续等待、重试、跳过、人工接管同样只由 `available_actions` 决定。
- 本地 loading、按钮点击次数、日志关键词、模拟开关都不能改变动作权限。
- 发送动作后必须重新读取或等待新的规范化快照；旧快照中的动作不保证仍然有效。

## 3. Contracts

### 3.1 配置 schema wire format

`GET /api/scripts` 返回的每个 `config_schema` 项使用以下键名。字段表单、校验和请求 payload 必须保留这些键名：

| 键 | 约束 |
| --- | --- |
| `key` | 后端真实配置键；请求中原样使用，禁止改成 camelCase 或视觉别名 |
| `label` | 展示名称 |
| `field_type` | `number`、`text`、`select`、`boolean`；脚本元数据中的 `checkbox` 已规范化为 `boolean` |
| `default` | 字段默认值 |
| `min_value` / `max_value` | 数值字段的边界，可为空 |
| `options` | 选择字段的值和展示标签，可为空 |
| `hot_reloadable` | 当前仅为 schema 元数据，不是本 GUI 的运行中编辑许可 |
| `description` | 字段说明，可为空 |
| `unit` | 单位，可为空 |
| `sensitive` | 敏感值展示标记；敏感值不得在日志或调试面板明文回显 |

字段来源优先级：

1. 选中脚本的 `config_schema` 定义字段集合和类型。
2. `default_config` 提供默认/最近保存的值。
3. 用户草稿只覆盖 schema 中存在的键。
4. 后端启动校验是最终权威，前端校验只用于及时提示。

### 3.2 配置生命周期

1. 读取 `GET /api/scripts`，根据选中脚本的 `config_schema` 动态生成左侧配置区。
2. 输入控件使用 `field.key` 作为内部键；数字、布尔和选项值按 `field_type` 保持真实类型。
3. 用户点击保存时，调用 `PATCH /api/scripts/{script_id}/config`，payload 只包含真实 schema 键。返回的 `applied: false` 必须在 UI 中理解为“未修改当前运行”。
4. 用户点击执行时，调用 `POST /api/runs/start`，发送 `{ "script_id": selectedScriptId, "config": exactConfig }`。
5. 运行快照处于 `queued`、`running`、`paused` 或停止过渡状态时，所有脚本配置控件只读。
6. 运行进入终态后，配置区恢复可编辑；修改只影响下一次启动。

### 3.3 当前脚本字段映射

| 脚本 | 当前真实配置键 | 当前默认值/范围摘要 |
| --- | --- | --- |
| `soul_raid` | `max_battle_count`、`accept_wq_type`、`loop_interval` | `103`（1-999）；`accept_wq_type` 为 0/1/2；`loop_interval` 为 300（50-5000） |
| `realm_raid` | `max_battle_count`、`quit_3_times_config` | `30`（1-99）；布尔值默认 `true` |
| `exploration_28` | `max_battle_count` | `244`（1-9999） |
| `abyss_shadows` | `boss_count`、`boss_damage_limit`、`commander_count`、`elite_count` | 依次为 2（0-99）、1（0-999999999）、4（0-99）、6（0-99） |
| 其他当前注册脚本 | 以各自 `config_schema` 为准；目前通用次数字段使用 `max_battle_count` | 禁止由 GUI 猜测范围或补造字段 |

`abyss_shadows.boss_damage_limit` 的字段语义冻结为：

- 请求键：`boss_damage_limit`。
- 数值范围：`0` 至 `999999999`。
- 原型展示文案可以使用“达到阈值后停止当前目标”。
- 该文案只解释现有后端行为，不新增 `damage_mode` 或其他停止策略字段。

### 3.4 原型字段到生产契约的映射

| 原型字段/文案 | 生产处理 | 冻结结论 |
| --- | --- | --- |
| `battleCount` / `battle_count` | 对有该 schema 的脚本映射为 `max_battle_count` | 仅允许作为视觉别名；payload 不得发送原型键 |
| `bossDamageLimit` | 仅对 `abyss_shadows` 映射为 `boss_damage_limit` | 允许映射；不得改名或扩展语义 |
| `failurePolicy` | 工作流步骤的 `failure_policy`，不是脚本 `config` | 不放入手动脚本启动配置 |
| `manualTakeover` | `manual_takeover` 运行控制动作 | 不作为布尔配置字段 |
| `evidenceCapture` | 后端运行证据契约 | 不作为当前脚本配置字段 |
| `teamSlot`、`soulLevel` | 当前脚本 schema 未提供 | 不发送、不渲染为生产配置 |
| `chapter`、`autoAdvance` | 当前 `exploration_28` schema 未提供 | 不发送、不渲染为生产配置 |
| `targetArea`、`damageMode`、`leaderMode` | 当前 `abyss_shadows` schema 未提供 | 不发送、不渲染为生产配置 |
| `script` | 顶层 `script_id` | 不放进 `config` 对象 |
| `CONFIGURATION`、`CURRENT RUN` | 视觉层级标题 | 可以保留；它们不是后端字段，也不承载额外语义 |

### 3.5 `hot_reloadable` 冻结解释

当前 GUI 不依据 `hot_reloadable` 开放运行中编辑。即使某字段标记为 `true`，运行期间仍然只读；`PATCH /api/scripts/{script_id}/config` 也不会把值注入当前运行。未来如果要支持热更新，必须另行冻结：注入接口、实例更新范围、并发一致性、失败回滚和测试，不得仅修改按钮状态。

## 4. Validation / Error Matrix

| 场景 | 前端处理 | 后端契约 |
| --- | --- | --- |
| 数字低于 `min_value` 或高于 `max_value` | 阻止启动并显示 schema 范围 | 后端仍做最终校验；不得依赖前端校验绕过边界 |
| `select` 值不在 `options` | 阻止提交并恢复合法选项 | 后端拒绝非法值 |
| 配置出现未知键 | 不渲染、不发送；保留原始响应时不得把未知键伪装成控件 | 启动 payload 只接受当前脚本真实配置键 |
| 配置保存成功 | 显示“已保存，下次启动生效” | 返回 `saved: true`、`applied: false` |
| 运行中尝试修改配置 | 控件保持只读，不调用当前运行热更新 | 当前接口不应用到运行实例；当前运行配置不变 |
| 动作不在 `available_actions` | 不显示对应按钮 | 后端按当前运行状态拒绝过期或非法动作；GUI 刷新快照 |
| 动作请求返回 404/409 或其他失败 | 保留当前页面，提示失败并重新读取快照 | 不得把失败请求显示成已执行 |
| WebSocket 重连 | 先读取最新快照，再恢复按钮和状态 | REST 与事件使用相同字段含义 |

## 5. Good / Base / Bad Cases

### 5.1 Good Case：御魂启动

1. `GET /api/scripts` 返回 `soul_raid` 的三个真实字段。
2. 左侧表单显示“最大战斗次数”“悬赏封印”“循环间隔(ms)”。
3. 用户修改后保存，收到 `applied: false`。
4. 启动 payload 使用 `max_battle_count`、`accept_wq_type`、`loop_interval`。
5. 快照为 `running + script_running` 时，右侧显示暂停/停止，左侧全部锁定。

### 5.2 Good Case：狭间暗域伤害阈值

1. 选择 `abyss_shadows` 后显示 `boss_count`、`boss_damage_limit`、`commander_count`、`elite_count`。
2. `boss_damage_limit` 以数值输入呈现，范围为 `0-999999999`。
3. 说明使用“达到阈值后停止当前目标”，但 payload 只发送 `boss_damage_limit`。
4. 不出现 `damage_mode`、`target_area` 或 `leader_mode` 的生产配置控件。

### 5.3 Base Case：无当前运行

- `GET /api/runs/current` 为 `null`。
- 左侧配置可编辑，执行入口可用。
- 顶部不显示停止按钮，也不由本地状态猜测其他运行动作。

### 5.4 Bad Case：原型字段泄漏

- 发送 `{ "battleCount": 10, "damageMode": "达到上限后停止" }`。
- 在 `soul_raid` 表单中显示 `teamSlot`、`soulLevel`，但后端 schema 没有这些键。
- 运行中允许修改 `boss_damage_limit` 并提示“已应用”。
- 根据“失败策略”文案自行显示 `retry`、`skip` 或 `manual_takeover`，即使快照没有这些动作。

这些行为都视为契约违例，不得带入生产实现。

## 6. Tests Required

进入开发阶段后，至少补齐以下产品契约断言：

1. 对 `available_actions_for_run` 的每一行矩阵逐项断言，包含 `waiting_safe_entry_timeout`、`script_running`、终态和 `manual`。
2. 使用同一个规范化快照断言：顶部停止按钮、运行页动作按钮和配置只读状态一致。
3. `GET /api/scripts` 的 `config_schema` 键名、类型、默认值、范围和选项能直接驱动表单。
4. `soul_raid`、`realm_raid`、`exploration_28`、`abyss_shadows` 启动请求断言使用真实 snake_case 键，不出现原型别名。
5. `boss_damage_limit` 的默认值、边界和启动 payload 断言覆盖 `0`、最大值和越界值。
6. `PATCH /api/scripts/{script_id}/config` 断言 `applied` 为 `false`，且当前运行的 `config` 不改变。
7. 运行从 `queued` 到终态前配置控件保持只读，终态后才恢复可编辑。
8. 动作请求失败后，GUI 不伪造成功状态，并重新读取规范化快照。
9. REST、WebSocket 和重连后的快照使用同一套字段含义，不从日志推导状态或动作。

## 7. Wrong vs Correct

| Wrong | Correct |
| --- | --- |
| 用本地 `isRunning`、演示开关或日志文本决定按钮 | 只读取快照的 `available_actions` |
| 用 `battleCount`、`bossDamageLimit` 直接发请求 | 使用 schema 的 `max_battle_count`、`boss_damage_limit` |
| 把所有脚本都渲染成同一组配置 | 按选中脚本的 `config_schema` 动态渲染 |
| `hot_reloadable: true` 就允许运行中修改 | 当前运行统一只读；热更新另立契约 |
| 保存配置后显示“已应用到当前运行” | 显示“已保存，下次启动生效” |
| 用 `failurePolicy`、`manualTakeover` 等视觉概念伪造配置 | 分别使用工作流字段或运行动作；不存在的字段不发送 |
| 用固定“已连接”、固定进度或固定预计时间代表后端状态 | 只展示后端实际返回的数据；原型模拟值不得进入生产实现 |

## 8. Implementation Gate

本规格冻结后，GUI 开发可以进入实现，但必须以本文为验收基线：

- 可以实现真实 API 适配和 schema 驱动表单。
- 可以保留 `CONFIGURATION`、`CURRENT RUN` 作为视觉层级标题。
- 不得把当前原型中的模拟动作、模拟连接状态、固定进度、虚构配置字段直接搬入生产。
- 本规格不授权修改后端热更新语义；若发现后端字段或动作矩阵变化，应先更新本文和对应测试。

### 现有代码矛盾记录

`yys/common/script_meta.py` 的 `ConfigMeta.hot_reloadable` 注释仍描述“PATCH 端点会立即注入当前 run 的实例属性”，但当前 `ui_backend/app.py` 的 PATCH 实现明确返回 `applied: false` 并说明“下次启动生效”。本次冻结按实际接口行为处理：不支持运行中改配置。后续若要统一注释或实现热更新，应作为独立变更处理。
