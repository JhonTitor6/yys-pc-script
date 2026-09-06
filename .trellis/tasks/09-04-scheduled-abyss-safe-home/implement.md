# 定时任务与狭间入口恢复实施计划

## 0. 开始前门禁

- [ ] 用户审阅并批准 `prd.md`、`design.md`、`implement.md` 后才运行 `task.py start`。
- [ ] 运行 `trellis-before-dev`，重新加载当前规范、任务状态和工作树。
- [ ] 记录并避开无关改动：`gui/installer.nsh`、`yys/common/images/scene/home.bmp`；不得覆盖、还原或混入提交。
- [ ] 确认当前 Codex 采用 inline 实施；不填充仅供子代理派发的 JSONL 清单。

## 1. 先固定调度产品契约

- [ ] 在 `tests/ui_backend/test_storage.py` 按 PRD AC9/AC9a 验证旧 interval/scheduled_time 工作流各迁移一次；复制与独立完成标记同事务，迁移失败全部回滚；重复初始化不重复，删除迁移任务后再初始化不重建。
- [ ] 增加迁移时间测试：有效 `next_run_at` 原样保留并按宽限期处理；缺失值只生成未来计划，每天 06:00 的任务在 06:15 升级时安排次日 06:00；停用状态不变。
- [ ] 在 `tests/ui_backend/test_scheduler.py` 增加每日、每周、恰好到点排下一周期、仅一次、间隔和非法配置的纯时间测试。
- [ ] 增加活动槽、30 分钟补跑、过期跳过、不累计、重启补跑、优先级、仅一次终态和调度历史去重测试。
- [ ] 按 PRD AC6a 增加领取前、领取后尚未输入、执行中、终态提交后四个崩溃点的恢复测试；验证未领取按宽限期补跑、已领取无终态只记中断且零自动输入、重复恢复幂等及手动重跑不改变自动计划。
- [ ] 按 PRD AC3/AC16/AC16a 验证首步执行中修改、删除或重排后续定义：本轮按原快照继续且无外键错误，下一轮使用新定义；全局配置变化不影响本轮后续步骤，失败或中断仍保存未执行步骤，重启后历史快照不变。
- [ ] 测试注释标明产品契约来源为本任务 PRD AC4-AC10a，不复述私有实现。

## 2. 实现最小存储与调度核心

- [ ] 在 `ui_backend/storage/database.py` 添加 `scheduled_tasks`、`scheduled_task_occurrences`、`runs.scheduled_task_id`、`runs.occurrence_id` 和一次性旧数据复制；复用 `app_settings` 保存独立完成标记，复制与标记原子提交，不删除旧列。
- [ ] 在 `ui_backend/storage/repositories.py` 增加定时任务与 occurrence 的最小仓库，完成 CRUD、终态历史去重、状态推进、引用查询和规范化 JSON 读写。
- [ ] 在 occurrence 增加 `target_snapshot_json`；一致读取工作流及全部有序步骤，解析有效配置后与领取记录一同持久化，执行及历史使用同一份不可变快照。
- [ ] 在 `ui_backend/models.py` 增加 `RunSourceType.SCHEDULED`、`RunRequest.scheduled_task_id` 与 `RunRequest.occurrence_id`。
- [ ] 在 `ui_backend/scheduler/service.py` 把下一次时间计算收敛为一个纯函数，支持 interval/scheduled_time/weekly/once。
- [ ] 让 `run_pending()` 只消费新任务表，复用现有排序、单运行槽和工作流执行器；单脚本走 `RunManager.start()`，工作流启动时实时加载步骤。
- [ ] 目标启动前原子提交轮次领取记录与自动计划领取状态；终态和计划推进同事务提交。领取失败不得启动目标，槽占用不领取轮次、不写历史。
- [ ] 自动执行、手动重跑、目标缺失、过期和中断路径保存 occurrence 终态；同一轮次步骤与策略重试共享轮次 ID，手动重跑新建轮次。
- [ ] 在 `ui_backend/app.py` 启动调度线程前执行幂等恢复：无终态领取记录转为 `interrupted`，周期任务恢复下一计划，仅一次任务停用；已有终态不变，手动轮次不改变自动计划。

## 3. 打通 API、事件与运行历史

- [ ] 在 `ui_backend/app.py` 增加定时任务 CRUD、启停、预览、立即运行和终态历史接口，并集中执行目标/周期校验。
- [ ] 工作流删除前查询定时任务引用，返回 `409`；保留运行历史外键既有行为。
- [ ] 在 `ui_backend/runs/manager.py`、RunRepository 和运行快照中透传 `scheduled_task_id`、`occurrence_id`；验证同轮步骤/重试关联及不同手动重跑的隔离。
- [ ] 复用 `runs.step_id` 关联快照步骤；在创建运行记录的同一数据库操作中处理来源 `workflow_step_id` 已删除的情况，不让可编辑定义的外键阻断本轮执行。核对共享函数所有调用者，保留普通手动脚本配置合并及工作流步骤/失败策略行为。
- [ ] 调度历史与关联运行详情返回当轮完整工作流快照及实际执行记录；原定义编辑或删除后不改写历史，没有快照的旧历史不补造。
- [ ] WebSocket `scheduler_status` 与 REST 返回相同状态字段，不让 GUI 从日志或本地时钟猜测。
- [ ] 更新 `tests/ui_backend/test_app_api.py`、`test_p1_workbench.py`、`test_run_manager.py` 的跨层往返与兼容测试。

## 4. 独立定时任务 GUI

- [ ] 在 `gui/index.html` 增加“定时任务”导航、列表和编辑子视图。
- [ ] 在 `gui/renderer.js` 复用工作流子视图、dirty 守卫、`scriptSchema()`、`renderField()` 和配置规范化逻辑。
- [ ] 实现目标类型、四种周期、星期多选、仅一次日期时间、30 分钟宽限期及空时间校验。
- [ ] 列表展示规范化状态和后端返回的操作；工作流页面移除调度字段、启停和周期摘要，保留编排与立即运行。
- [ ] 在 `gui/styles.css` 只补充新页面所需布局；800×600 使用现有响应式模式。
- [ ] 扩展 `tests/gui/test_renderer_config.js`，覆盖单脚本参数快照、工作流引用、星期序列化、空时间和默认宽限期。
- [ ] 历史详情渲染当轮完整工作流快照，区分未执行步骤及实际结果/重试；验证编辑原定义后详情仍显示原版本。

## 5. 狭间最短入口与安全兜底

- [ ] 先在 `yys/abyss_shadows/test_abyss_shadows_flow.py` 固定已知区域/敌人选择续跑、daily/selection 捷径、首页入口和手动/定时一致性。
- [ ] 在 `yys/abyss_shadows/abyss_shadows_script.py` 局部整理现有入口步骤，使中途页面能跳过已完成前缀；不修改通用 `EntryPreparer` 未知零输入逻辑。
- [ ] 增加按 `to_home.bmp` → `return.bmp` → `ESC` 的首页恢复，逐动作验证且只通过注入环境发送输入。
- [ ] 按 AC13/AC14 让回首页按钮、返回按钮和 `ESC` 共享 6 次/累计 30 秒退层预算；已知/未知切换、重试或中途战斗/结算后不重置已用预算。加入确认离开哨兵、独立的一次取消 `ESC` 和首页稳定复核。
- [ ] 验证连续命中按钮、三类动作混用、第 6 次到首页、第 6 次出现退出弹窗及停止信号边界；不出现第 7 次退层，取消弹窗不占退层次数且不绕过全局保险丝。
- [ ] 按 AC15/AC15a 为战斗等待使用独立 180 秒截止时间，持续识别并响应停止，超时返回入口失败。
- [ ] 复用现有入口结算模板与不计业务次数的关闭模式，确认结束页后主动点击，逐页刷新截图验证；初始结算页直接处理，不调用会计数的业务回调或固定坐标继续回调。
- [ ] 增加战斗 → 结算 → 稳定场景、多页结算、初始结算、战斗持续超时、停止后零输入及入口清理不增加业务计数的 Mock/回放验收；结算点击必须有真实帧识别依据。
- [ ] 新增确认离开识别证据时使用用户确认的真实画面；不得改动或替换用户当前的 `home.bmp`。
- [ ] 在 `yys/abyss_shadows/test_abyss_shadows_scene_replay.py` 或最小新夹具中验证真实模板；Mock 只验证动作顺序，不代替真实画面匹配。

## 6. 定向验证

```powershell
& 'D:/ProgramData/anaconda3/envs/win_macro/python.exe' -m pytest tests/ui_backend/test_storage.py tests/ui_backend/test_scheduler.py tests/ui_backend/test_p1_workbench.py tests/ui_backend/test_app_api.py tests/ui_backend/test_run_manager.py -q
& 'D:/ProgramData/anaconda3/envs/win_macro/python.exe' -m pytest tests/common/test_entry_runtime.py tests/common/test_scene_manager.py yys/abyss_shadows/test_abyss_shadows_flow.py yys/abyss_shadows/test_abyss_shadows_scene_replay.py -q
node --check gui/renderer.js
node tests/gui/test_renderer_config.js
node tests/gui/test_backend_detection.js
& 'D:/ProgramData/anaconda3/envs/win_macro/python.exe' -m ruff check ui_backend yys/common yys/abyss_shadows tests/ui_backend tests/common
& 'D:/ProgramData/anaconda3/envs/win_macro/python.exe' -m compileall ui_backend yys/common yys/abyss_shadows
git diff --check
```

## 7. 真实验收

- [ ] 启动真实后端与 Electron，分别在 800×600、900×650、1280×720 验证定时任务 CRUD、四种周期、空时间错误、启停、立即运行及工作流删除冲突。
- [ ] 使用临时测试数据库验证升级迁移与重启补跑，不在用户真实任务上制造过期或重复执行。
- [ ] 在用户明确授权的真实游戏窗口验证：已在狭间页续跑、首页入口、中途捷径、未知逐次 `ESC`、确认弹窗再次 `ESC` 取消、战斗持续识别及结束页主动逐页关闭；核对旧结算不计入本轮业务次数。
- [ ] 核对三类退层动作合计不超过 6 次、退层累计 30 秒上限、独立结算/取消动作、最终首页识别、运行历史关联及没有确认退出行为。

## 8. 回归与收尾

- [ ] 运行受影响的完整 UI backend、common 和狭间测试；确认现有工作流步骤/失败策略/立即运行、历史、托盘和停止控制无回归。
- [ ] 执行 `trellis-check`，按 PRD AC1-AC21 逐项核对并修正漂移。
- [ ] 实现完成后执行 `trellis-update-spec`，记录独立定时任务、迁移和狭间专用恢复契约。
- [ ] 向用户报告未验证项；提交前按项目约定单独询问，不执行 `git add` 或提交。

## 风险与回滚点

| 风险 | 防护与回滚 |
|---|---|
| 旧工作流迁移后重复执行或删除后重建 | 独立迁移完成标记与复制同事务提交，`legacy_workflow_id` 唯一键防重；验证删除后重启和迁移失败重试；旧列仍保留 |
| 工作流编辑破坏后续步骤或历史 | 完整有效配置快照与领取记录同事务保存；执行身份与可删除定义外键解耦，历史读取当轮快照；覆盖修改、删除、重排、提前失败及重启 |
| 补跑累计或跨重启漂移 | 持久化原 `next_run_at`，宽限期判断先于槽检查，纯函数推进下一周期 |
| 领取后崩溃导致重复操作或永久失去计划 | 领取记录先于目标启动提交；轮次终态与计划原子更新，重启只记一次中断，不自动重跑该轮 |
| 首页恢复失控或误退出游戏 | 三类退层动作共享 6 次/累计 30 秒预算，逐次截图；确认弹窗只按一次 `ESC` 取消，取消动作独立计限并服从全局保险丝与停止信号 |
| 战斗结束页被动等待或污染统计 | 区分战斗与结算，命中结算后主动逐页关闭且不调用业务计数回调；独立 180 秒战斗等待窗口，覆盖停止、超时与多页真实结算 |
| 新导航与既有 GUI 任务冲突 | 仅更新调度相关字段和导航预期，保留其他子视图与 dirty 契约 |
| 用户图片改动被覆盖 | 把 `home.bmp` 视为外部脏改，新增独立识别证据，不覆盖原文件 |
