# 修正御魂组队页入口契约

## Goal

让御魂脚本只把“协战队伍”组队界面视为入口准备完成；战斗中启动时保持零输入等待，识别到白名单结算页后自动关闭结算，回到组队界面后进入 `READY`。

## Background

- `SoulRaidScript.entry_spec.target_scene` 当前仍为 `soul_selection`。
- `yys/common/images/scene/soul_selection.bmp` 是御魂选择页标记；`yys/common/images/scene/soul_selection/soul_selection_captain.bmp` 是组队页“队长”标记。目录注册会把两者合并为同一个 `soul_selection` 场景，因此选择页和组队页都可能满足同一目标契约。
- `EntryPreparer._step_waiting_battle()` 已在当前截图识别为 `SETTLEMENT` 时调用 `_dismiss_settlement()`；现有真实帧回放可证明战斗帧零输入、结算点击一次、组队页进入 `READY`，但最终场景仍被命名为 `soul_selection`。
- 真实运行发现 `_LegacyControllerEnv.capture_screen()` 仅在缓存为 `None` 时刷新；`ImageFinder` 初始化后缓存已非空，导致入口等待重复识别启动帧，无法看到后来出现的结算页。逐帧回放替身会自动前进，因此此前测试未覆盖该生产适配器差异。

## Requirements

- R1：新增语义明确的组队页场景 ID `soul_team`，`SoulRaidScript.entry_spec.target_scene` 必须使用该 ID，不再用 `soul_selection` 表达组队页。
- R2：`soul_selection` 继续只表示御魂选择页；组队页标记不得再注册到该场景。选择页不得直接进入 `READY`。
- R3：战斗进行中只截图识别和等待，不发送鼠标或键盘输入。
- R4：战斗等待过程中识别到 `SafeOverlayPolicy.settlement_templates` 白名单内的结算页后，必须点击当前截图匹配到的结算位置，然后重新截图识别。
- R5：入口准备阶段关闭结算不得增加业务战斗数或胜利数。
- R6：重新识别并连续确认组队页稳定后进入 `READY`，随后才允许御魂业务循环处理“挑战”按钮。
- R7：从御魂选择页进入组队页所需的导航动作缺少已确认模板时，必须安全失败且零输入，不得增加固定坐标或猜测点击。
- R8：只修改御魂入口场景边界、相关真实帧回放测试及必要的场景注册约定；保留其他脚本和现有未提交改动。
- R9：真实入口准备的每次观察必须刷新截图缓存；不得因已有缓存而重复返回旧帧。

## Acceptance Criteria

- [x] AC1：`SoulRaidScript.entry_spec.target_scene == "soul_team"`。
- [x] AC2：生产场景注册后，御魂选择页模板属于 `soul_selection`，组队页“队长”模板只属于 `soul_team`。
- [x] AC3：真实组队页帧解析为 `STABLE/soul_team`，并在连续稳定观察后返回 `READY`。
- [x] AC4：回放“战斗帧 → 结算帧 → 组队页帧”时，战斗阶段点击数为 0，结算阶段只点击 1 次，最终结果为 `READY/soul_team`。
- [x] AC5：以 `soul_selection` 作为当前稳定页且没有已验证的 `soul_selection → soul_team` 导航边时，返回结构化入口失败并保持零输入，不得误报 `READY`。
- [x] AC6：相关 pytest、`compileall`、变更文件 Ruff 与 `git diff --check` 通过；无法进行的真实游戏验证必须明确标注。
- [x] AC7：生产使用的 `_LegacyControllerEnv` 连续两次截图会调用两次刷新 API，并返回对应的新帧。

## Out of Scope

- 不新增“御魂选择页 → 组队页”的猜测导航或固定坐标点击；取得真实按钮模板和后置页面证据后另行补充。
- 不修改御魂业务战斗计数、挑战按钮处理和其他脚本入口行为。
- 不在本任务中改动、提交或覆盖用户现有的 `AGENTS.md` 修改。
