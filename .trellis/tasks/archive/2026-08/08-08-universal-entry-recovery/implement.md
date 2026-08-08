# 通用入口与恢复运行时实施计划

## 1. 实施原则

- 当前任务只迁移御魂 `soul_raid`；探索、结界突破和无入口脚本只做回归验证。
- 先写产品契约测试，再写最少实现。共享组件测试注释必须标明契约来源为本任务 PRD 的对应 AC。
- 所有真实输入继续经过 `GameEnvironment`；不新增直接 Win32 点击路径。
- 不修改或清理当前工作树中与本任务无关的用户变更。
- 未获得用户审阅和 `task.py start` 前，不执行本计划中的业务代码修改。

## 2. 预计影响文件

### 公共识别与入口运行时

- `win_util/image.py`
- `yys/common/scene_manager.py`
- `yys/common/event_script_base.py`
- 新增 `yys/common/entry_runtime.py`
- `win_util/environment/guarded.py`（仅在现有接口不足时做局部扩展）

### 御魂试点

- `yys/soul_raid/soul_raid_script.py`
- `yys/common/images/scene/battling.bmp` 或新增经真实帧确认的稳定战斗模板
- 相关确认回放夹具

### 工作台跨层

- `ui_backend/models.py`
- `ui_backend/storage/database.py`
- `ui_backend/storage/repositories.py`
- `ui_backend/runs/manager.py`
- `ui_backend/app.py`
- `ui_backend/scheduler/service.py`
- `gui/index.html`
- `gui/renderer.js`

### 测试

- `tests/common/test_scene_manager.py`
- `tests/common/test_scene_transition_entry.py`
- 新增 `tests/common/test_entry_runtime.py`
- `tests/common/test_guarded_environment.py`
- `tests/ui_backend/test_storage.py`
- `tests/ui_backend/test_run_manager.py`
- `tests/ui_backend/test_run_observability.py`
- `tests/ui_backend/test_app_api.py`
- `tests/ui_backend/test_scheduler.py`
- 御魂真实帧回放测试

## 3. 有序实施清单

### Step 0：基线和冲突保护

- [x] 记录 `git status --short`，确认本任务将修改的文件是否已有用户变更。
- [x] 运行入口、场景、RunManager、存储和御魂现有定向测试，记录基线失败（5 个基线失败已 stash 对比确认）。
- [x] 特别核对 `SoulRaidScript.entry_scene` 已被注释而测试仍期望 `soul_selection` 的现状，不把既有漂移误算为新回归。

验证：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_scene_manager.py tests/common/test_scene_transition_entry.py tests/ui_backend/test_run_manager.py tests/ui_backend/test_storage.py yys/soul_raid/test_soul_raid.py -v
```

### Step 1：锁定场景身份与识别证据契约

- [x] 先写幽灵节点归一化、未知别名、别名循环和缺失端点测试，对应 AC1。
- [x] 为最佳候选分数写 ImageFinder 单元测试（best_match），确保返回位置、模板路径和相似度且不发送输入。
- [x] 实现唯一别名归一化入口和建图校验（SceneGraphValidationError + 显式外部目标声明）。
- [x] 让 `detect_current_scene()` 的兼容返回保持不变，同时新增 `detect_scene_candidates()` 候选识别 API。

回滚点：此步骤不改变任何脚本运行入口；若失败可撤回新 API 与校验，不触碰业务代码。

### Step 2：实现 SceneSnapshot 与 EntryPreparer 离线状态机

- [x] 在 `entry_runtime.py` 定义带类型提示的 `SceneMode`、`RecognitionEvidence`、`SceneSnapshot`、`Transition`、`TaskEntrySpec`、`EntryPreparationResult`。
- [x] 先写稳定页面、战斗等待、结算关闭、拒绝悬赏、未知弹窗、导航重试、入口稳定验证测试，对应 AC2-AC6、AC9。
- [x] 使用可控单调时钟验证 180 秒窗口与每次新增 180 秒。
- [x] 验证战斗观察零输入、准备结算零业务计数、未知画面零盲点输入。
- [x] 所有动作统一走注入环境和现有 guard 预算（GuardedEnvironment 拦截测试）。

回滚点：EntryPreparer 尚未接入脚本，可独立删除。

### Step 3：御魂试点与基类兼容包装

- [x] 为 `YYSBaseScript` 增加 `entry_spec`、`prepare_entry()` 和 `run_business()`，保留旧 `run()` 包装。
- [x] 只给 `SoulRaidScript` 声明 `TaskEntrySpec(target_scene="soul_selection")`。
- [x] 更新入口契约测试：御魂断言新 `entry_spec`，探索/结界突破继续断言旧 `entry_scene`，无入口脚本继续跳过。
- [x] 入口失败使用结构化结果或异常（EntryPreparationError），禁止正常 return 后被识别为业务成功。

验证：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_scene_transition_entry.py tests/common/test_entry_runtime.py yys/soul_raid/test_soul_raid.py -v
```

### Step 4：RunStage、RunManager 和关联重试

- [x] 先写 status/stage/action 矩阵测试（available_actions_for_run），对应 AC2、AC4、AC7、AC12。
- [x] `RunManager` 对新入口脚本先 prepare，READY 后才写 `script_running` 并进入业务循环。
- [x] 实现等待超时命令同步：continue、manual、stop；不在 manager 锁内阻塞脚本线程。
- [x] manual 终态停止输入、结束线程并释放活动槽。
- [x] 允许 manual run 执行 retry，创建新 run，不修改原 run。
- [x] 保留旧脚本和既有 error recovery 行为（既有 15 个 manager 测试原样通过）。

并发重点：复用现有 stop/线程锁测试模式，覆盖命令与线程退出竞态。

### Step 5：SQLite 迁移与规范化快照

- [x] 先写旧 schema 幂等升级测试，对应 AC12、AC13。
- [x] `runs` 增加可空 `parent_run_id`；repository create/normalize 全链路透传。
- [x] `RunRequest` 增加来源 run 字段，retry 复制工作流上下文并递增次数。
- [x] REST、WebSocket 和历史查询返回一致的 `stage`、`available_actions`、`parent_run_id`。

验证：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_storage.py tests/ui_backend/test_run_observability.py tests/ui_backend/test_run_manager.py -v
```

### Step 6：API、工作流与 GUI

- [x] 新增 continue-waiting API 契约测试；扩展 manual/retry 合法阶段测试。
- [x] 工作流等待关联重试结果，manual 原 run 不推进步骤，对应 AC8、AC13。
- [x] GUI 展示阶段、继续等待、人工接管、停止和关联重试（等待时长倒计时为后续增强）。
- [x] WebSocket 重连和 REST 刷新从同一快照恢复按钮，不在前端硬编码第二套动作规则。
- [x] 保留现有暂停、恢复、停止和 error recovery 按钮行为。

验证：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_app_api.py tests/ui_backend/test_scheduler.py tests/ui_backend/test_p1_workbench.py -v
```

### Step 7：真实战斗证据与端到端回放

- [ ] 在用户明确授权的受控录制中采集御魂战斗早、中、晚、结算和安全页面帧。
- [x] 测量现有 `battling.bmp` 的最高候选分数：战斗帧 0.963 命中、结算帧 0.511 负样本达标；无需替换模板。
- [ ] 确认战斗模板覆盖早中晚且不匹配结算帧；不得只用自动隐藏面板。
- [x] 构建真实帧离线回放（战斗启动→等待→结算关闭→未知安全失败）；稳定页启动闭环待录制 soul_selection 帧。
- [x] 通过生产 matcher 与 EntryPreparer 执行端到端回放（AC3/AC5/AC11 离线部分）；完整 READY 路径待录制授权。

真实输入边界：录制或实机验证需要用户单独明确授权；离线夹具测试不需要游戏窗口。

### Step 8：全量回归与一致性检查

- [x] 运行公共、御魂、探索、结界突破、GUI 后端测试（279 通过，5 个基线失败不变）。
- [x] 验证旧 SQLite schema 升级后可重复打开和写入。
- [x] 检查 REST、WebSocket、GUI 四层字段和动作矩阵一致。
- [x] 检查所有新增公共 API 类型提示和中文注释。
- [x] 运行 Trellis `trellis-check`（无 lint/type 配置，以测试+编译+循环依赖检查替代）。

建议命令：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/ yys/soul_raid/test_soul_raid.py yys/exploration/test_exploration.py yys/realm_raid/test_*.py tests/ui_backend/ -v
```

若仓库中不存在某个列出的测试文件，实施时按 `rg --files` 的实际结果调整命令，不创建空测试占位。

## 4. 验收映射

| PRD | 主要实施步骤 |
| --- | --- |
| AC1 | Step 1 |
| AC2、AC6、AC7 | Step 2-4 |
| AC3、AC5、AC11 | Step 2、Step 7 |
| AC4 | Step 2、Step 4、Step 6 |
| AC8、AC13 | Step 4-6 |
| AC9 | Step 1-3 |
| AC10 | Step 0、Step 3、Step 8 |
| AC12 | Step 4-6 |

## 5. 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| 战斗模板只覆盖单一时刻 | 真实录制早/中/晚覆盖 + 结算负样本 |
| 入口准备被误计为业务战斗 | 独立结算处理器 + 计数断言 |
| continue/manual/stop 竞态 | 条件变量/事件 + manager 锁外等待 + 线程退出测试 |
| SQLite 老库升级失败 | 可空列、幂等迁移、旧库往返测试 |
| GUI 与后端动作不一致 | 后端快照作为唯一动作来源 |
| 旧脚本意外迁移 | 仅 `entry_spec` 触发新路径 + 探索/结界突破原子回归 |
| 关联重试推进错误工作流步骤 | 保留 workflow/step/action 字段 + scheduler 集成测试 |

## 6. 开始实施前检查

- [ ] 用户已审阅 `prd.md`、`design.md` 和 `implement.md`。
- [ ] PRD 收敛检查通过，无开放问题或重复临时段落。
- [ ] 用户明确要求开始实施后，再执行 `task.py start`。
- [ ] 实施前加载 `trellis-before-dev`。
- [ ] 不需要子代理派发；当前 Codex inline 工作流跳过 JSONL 上下文门槛。
