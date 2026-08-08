# 通用入口与恢复运行时技术设计

## 1. 设计结论

本次采用“公共入口准备器 + 御魂试点 + 兼容旧入口”的渐进方案，不重写全部业务脚本。

核心决策：

1. `RunStatus` 继续表示粗粒度生命周期，新增 `RunStage` 表示准备、等待、导航、验证和业务运行等阶段。
2. 御魂通过 `TaskEntrySpec` 选择新入口准备器；未声明该契约的脚本保持现有 `run()` 行为。
3. 场景图片和按钮文件名不再直接成为未经校验的业务节点；旧名称只通过显式别名归一化。
4. 自动恢复只在当前 run 内执行；人工接管终结当前 run，后续重试创建有关联的新 run。
5. 战斗等待使用独立的 180 秒阶段窗口；“继续等待”只新增一个 180 秒窗口，不绕过紧急停止、动作预算或 run 级安全限制。
6. 未知画面不执行随机点击；所有动作必须有识别前置条件和可验证后置条件。

## 2. 当前问题边界

现有调用链：

```text
RunManager.start
  → 立即写入 running/script_running
  → 线程调用 script.run()
  → YYSBaseScript.run()
  → SceneManager.goto_scene(entry_scene)
  → 未知场景或无路径时返回 False
  → script.run() 正常返回
  → RunManager 可能标记 success
```

根因不是单一模板缺失，而是四个边界同时不完整：

- 场景身份由不同文件名独立推导，存在幽灵节点。
- 场景识别只返回首个命中结果，缺少候选分数、覆盖层和稳定性。
- 入口准备和业务主循环没有独立生命周期。
- RunManager 无法区分“准备失败”与“业务成功返回”。

## 3. 目标架构

```text
RunManager
  ├─ 创建 queued run
  ├─ 构造脚本与运行上下文
  ├─ entry_spec 存在？
  │    ├─ 否：保持旧 script.run()
  │    └─ 是：EntryPreparer.prepare()
  │           ├─ resolve_state
  │           ├─ handle_safe_overlay
  │           ├─ wait_battle_safe_end
  │           ├─ navigate
  │           └─ verify_entry_stable
  └─ READY 后调用 script.run_business()
```

建议新增或扩展的职责：

| 组件 | 职责 |
| --- | --- |
| `SceneManager` | 场景注册、显式别名归一化、图完整性校验、候选识别证据 |
| `SceneSnapshot` | 一次截图的基础场景、覆盖层、模式、置信度、证据和稳定性 |
| `TaskEntrySpec` | 业务脚本声明目标入口、稳定条件、战斗等待和安全弹窗策略 |
| `EntryPreparer` | 状态机、阶段截止时间、恢复阶梯和后置验证 |
| `RunManager` | run/stage 持久化、可用操作、终态、证据和关联重试 |
| GUI | 展示统一快照并只发送后端声明为可用的操作 |

## 4. 核心数据契约

### 4.1 SceneSnapshot

```python
@dataclass(frozen=True)
class RecognitionEvidence:
    target_id: str
    image_path: str
    similarity: float
    position: tuple[int, int] | None
    matched: bool


@dataclass(frozen=True)
class SceneSnapshot:
    base_scene: str | None
    overlays: tuple[str, ...]
    mode: SceneMode
    confidence: float
    evidence: tuple[RecognitionEvidence, ...]
    stable: bool
```

`SceneMode` 首个 MVP 至少包含：

- `STABLE`：可作为导航节点。
- `TRANSITION`：已知短暂过渡，不执行新动作。
- `BATTLE`：战斗进行中，只等待和观察。
- `SETTLEMENT`：已确认结算，可执行白名单关闭动作。
- `UNKNOWN`：无可靠识别，进入有界重新识别或失败。

识别器必须收集最高候选分数。现有 `ImageFinder.bg_find_pic_all()` 已返回相似度；如不足以获得阈值以下的最佳候选，应在 `ImageFinder` 内增加只读的“最佳匹配”接口，复用同一模板匹配实现，不在 `SceneManager` 重写 OpenCV 逻辑。

### 4.2 TaskEntrySpec

```python
@dataclass(frozen=True)
class TaskEntrySpec:
    target_scene: str
    stable_observations: int = 2
    stable_interval_seconds: float = 0.5
    battle_wait_window_seconds: float = 180.0
    safe_overlay_policy: SafeOverlayPolicy = SafeOverlayPolicy()
```

御魂声明 `target_scene="soul_selection"`。探索、结界突破和 `entry_scene is None` 的脚本本次不声明 `TaskEntrySpec`。

### 4.3 Transition

```python
@dataclass(frozen=True)
class Transition:
    source: str
    target: str
    action_image: str
    timeout_seconds: float
    retries: int
    risk: TransitionRisk
```

首个 MVP 只允许 `SAFE` 导航边。动作成功的定义是目标场景通过稳定验证，不是图片命中或点击函数返回。

### 4.4 RunStage

`RunStatus` 保持现有 `queued/running/paused/success/error/stopped/skipped/manual`。新增 `RunStage`：

- `queued`
- `preparing`
- `waiting_safe_entry`
- `waiting_safe_entry_timeout`
- `navigating`
- `verifying_entry`
- `script_running`
- `paused`
- 各终态阶段，如 `entry_failed`、`manual_takeover`、`stopped`

API、WebSocket、SQLite 和 GUI 使用相同字符串值。GUI 不从日志推导阶段。

## 5. 场景注册与图校验

### 5.1 显式归一化

在公共场景注册层声明别名：

```text
battle     → battling
chapter_28 → exploration_chapter_28
soul       → soul_selection
```

归一化同时应用于：

- 场景注册名称；
- 显式跳转的源和目标；
- 通用跳转目标；
- `TaskEntrySpec.target_scene`；
- 对外输出的 `SceneSnapshot.base_scene`。

别名表是唯一兼容入口。业务脚本、测试和 GUI 不自行转换名称。

### 5.2 建图失败边界

`_build_scene_graph()` 完成后校验：

- 每条边的源和目标均存在于已注册场景。
- 每个别名最终指向已注册规范场景，且不存在循环别名。
- 同一源/目标没有冲突动作。
- `TaskEntrySpec.target_scene` 存在且至少能从一个受支持页面到达。

校验失败抛出结构化 `SceneGraphValidationError`，在 run 准备阶段记录为 `ENTRY_GRAPH_INVALID`，不进入业务循环。

## 6. 入口准备状态机

```text
PREPARING
  → resolve_state
      ├─ stable target → VERIFYING_ENTRY
      ├─ safe overlay → handle → PREPARING
      ├─ battle → WAITING_SAFE_ENTRY
      ├─ settlement → dismiss safely → PREPARING
      ├─ known stable page → NAVIGATING
      └─ unknown → bounded re-recognition → ERROR/MANUAL

WAITING_SAFE_ENTRY
  ├─ battle remains → observe only
  ├─ settlement → dismiss safely → PREPARING
  ├─ safe page → NAVIGATING
  └─ 180s reached → WAITING_SAFE_ENTRY_TIMEOUT

WAITING_SAFE_ENTRY_TIMEOUT
  ├─ continue_waiting → new 180s window
  ├─ manual_takeover → MANUAL terminal
  └─ stop → STOPPED terminal

NAVIGATING
  ├─ verified next scene → next edge / VERIFYING_ENTRY
  └─ failed edge → bounded re-identification/retry → recovery escalation

VERIFYING_ENTRY
  ├─ stable target reached → SCRIPT_RUNNING
  └─ unstable → PREPARING or bounded failure
```

### 6.1 战斗规则

- `battling` 必须由真实战斗早、中、晚帧验证，且不能匹配结算帧。
- 战斗标记回调或轮询不得发送输入。
- 不点击退出、取消战斗、投降或其他会改变战斗结果的控件。
- 180 秒窗口到期后停止自动动作并等待用户命令；用户未选择前保持当前 run 活跃并占用单执行槽。
- `continue_waiting` 从用户命令时刻开始新的 180 秒窗口，并记录事件。

### 6.2 弹窗规则

- 准备阶段使用独立结算处理器，不能调用会增加 `_cur_battle_count` 或 `_cur_battle_victory_count` 的业务回调。
- 悬赏封印只有 `accept_wq_type=REFUSE` 时允许点击确认的拒绝模板。
- 接受类策略、OCR 继续、私有弹窗和未知弹窗均转人工或失败，不点击推测位置。

## 7. 脚本兼容集成

`YYSBaseScript` 提供：

- `entry_spec: TaskEntrySpec | None = None`
- `prepare_entry(reporter) -> EntryPreparationResult`
- `run_business() -> None`，只调用现有事件主循环
- `run()` 作为兼容包装：新契约走 prepare + business；旧 `entry_scene` 继续现有跳转；无入口脚本直接运行

`RunManager` 只对 `entry_spec is not None` 的脚本拆分准备和业务运行。其余脚本仍调用 `script.run()`，避免一次性迁移。

御魂是唯一试点。实施前需要核对当前 `SoulRaidScript.entry_scene` 与现有测试的漂移：源码当前注释了该声明，而测试仍期望 `soul_selection`。新契约以 `entry_spec` 为唯一产品来源，测试随契约更新，但不得借机修改探索或结界突破入口。

## 8. RunManager、存储与 API

### 8.1 生命周期

`RunManager.start()` 只创建 `queued` run 和脚本线程。线程开始后：

1. 新入口脚本写 `status=running, stage=preparing`。
2. 每个入口阶段通过 reporter 更新 `stage/progress/available_actions`。
3. 准备成功后写 `stage=script_running`，再调用业务循环。
4. `EntryPreparationResult.MANUAL` 写终态 `manual/manual_takeover` 并清理线程与活动槽。
5. 准备错误写 `error/entry_failed`，保存稳定错误码和证据。
6. 业务循环只有在真正开始后正常返回，才允许写 `success`。

### 8.2 可用操作

可用操作由 `(status, stage)` 共同派生：

| 状态/阶段 | 操作 |
| --- | --- |
| `queued` | `stop` |
| `running/preparing` | `stop` |
| `running/waiting_safe_entry` | `stop` |
| `running/waiting_safe_entry_timeout` | `continue_waiting`、`manual_takeover`、`stop` |
| `running/script_running` | `pause`、`stop` |
| `paused` | `resume`、`stop` |
| `error` | 保留现有 `retry/skip/stop/manual_takeover` |
| `manual` | `retry`，GUI 文案为“重新识别并重试” |

后端是操作真源，GUI 只渲染返回数组。

### 8.3 关联重试

SQLite `runs` 新增可空 `parent_run_id`，引用来源 run。迁移必须幂等，旧库读写不受影响。

从 `manual` 重试时：

- 新 run 复制脚本配置、`source_type`、`workflow_id`、`workflow_step_id`、`task_id`、`step_id` 和 `action_id`。
- `parent_run_id=原 run.id`，`retry_count+1`。
- 原 run 保持不可变。
- 新 run 重新构造脚本并从 `PREPARING` 开始。

工作流服务等待新 run 的结果；只有关联新 run 成功才推进原步骤。不得把原 `manual` run 改回 running。

### 8.4 API

- 复用 `POST /api/runs/{run_id}/manual-takeover`，允许在超时等待阶段请求终态人工接管，同时保留现有 error → manual 行为。
- 新增 `POST /api/runs/{run_id}/continue-waiting`，仅在 `waiting_safe_entry_timeout` 可用。
- 扩展现有 retry，使 `manual` run 也能创建关联新 run。
- 所有非法阶段操作返回明确 409/业务错误，不静默忽略。

## 9. 证据与错误码

入口错误至少包含：

- `ENTRY_GRAPH_INVALID`
- `ENTRY_SCENE_UNKNOWN`
- `ENTRY_BATTLE_WAIT_TIMEOUT`
- `ENTRY_OVERLAY_UNSAFE`
- `ENTRY_TRANSITION_NOT_FOUND`
- `ENTRY_TRANSITION_FAILED`
- `ENTRY_TARGET_UNSTABLE`
- `ENTRY_CAPTURE_FAILED`

每次失败证据包含：

- run、阶段、目标入口和当前路径；
- `SceneSnapshot` 与最高候选相似度；
- 最近动作、重试次数和阶段耗时；
- 真实截图路径，或显式 `capture_error`；
- 原 run / 关联重试 run 标识。

证据写入现有 evidence repository 和规范化 run snapshot，不新建平行日志系统。

## 10. 安全与 Guard

- EntryPreparer 只能通过脚本已注入的 `GameEnvironment` 截图和输入。
- 每个点击/按键先申请现有 `RunGuard` 动作预算。
- 战斗观察和稳定性验证不消耗动作预算，但仍检查紧急停止和 run 级总限制。
- 180 秒是战斗阶段窗口，不替代 run 级总限制。用户延长阶段窗口时，不修改已有总限制、动作数或未知画面计数。
- 若 run 级保险丝先触发，以保险丝终态为准；不得因为等待阶段可延长而覆盖紧急停止或总限制。

## 11. GUI

执行页新增阶段文案：准备中、等待战斗安全结束、等待用户选择、正在导航、验证入口、业务运行。

等待超时时显示：

- 当前截图和识别摘要；
- 已等待时长与 3 分钟窗口；
- “继续等待 3 分钟”“转人工接管”“停止”。

`manual` 历史记录显示原失败证据和“重新识别并重试”。关联新 run 显示来源 run 链接。刷新或 WebSocket 重连后，所有按钮仍由规范化快照恢复。

## 12. 兼容、发布与回滚

### 兼容

- 数据库只增可空列；旧 run 的 `parent_run_id` 为 `null`。
- 旧脚本不声明 `entry_spec`，运行路径不变。
- 旧 `entry_scene` API 暂不删除。
- 现有 error retry、skip、stop、manual_takeover 语义保持。

### 发布顺序

1. 先提交纯契约、图校验和离线测试。
2. 接入 EntryPreparer 与御魂离线回放。
3. 接入 RunManager/存储/API。
4. 最后开放 GUI 操作。

### 回滚

- 御魂可移除 `entry_spec` 回到旧运行路径；公共代码和可空数据库列可保留。
- 若 GUI 阶段操作异常，后端仍保留 stop 与结构化证据，不允许退回盲点恢复。

## 13. 关键权衡

| 选择 | 原因 | 放弃的方案 |
| --- | --- | --- |
| status + stage 双层模型 | 复用现有终态和数据库，降低跨层迁移风险 | 把每个准备阶段都新增为 RunStatus |
| 御魂单试点 | 先验证完整链路 | 同时迁移探索和结界突破 |
| 显式别名 + 建图校验 | 最小修复文件名漂移且保留资产 | 立即建立完整 Page 对象体系 |
| 人工后新 run | 消除过期状态并保留审计链 | 原 run 原地恢复 |
| 未知画面零盲点点击 | 安全优先 | 照搬外部项目随机安全区点击 |

