# 修复狭间暗域从当前界面启动失败

## Goal

允许狭间暗域脚本从已识别的狭间暗域页面启动，避免把非 Home 页面误当成 Home 执行拖拽并报错。

## Background

- `Main.on_run()` 当前无条件调用 `goto_abyss_shadows()`；后者只先检查 `abyss_selection.bmp`，未命中即按 Home 流程拖拽。
- 2026-08-14 真实窗口只读探测确认：窗口可被现有 `SceneManager` 识别为 `battling`，但选择页模板不命中。
- `check_current_area()` 引用的 `dragon_area.bmp`、`fox_area.bmp`、`leopard_area.bmp`、`peacock_area.bmp` 均不存在，不能作为启动判断依据。

## Requirements

- R1：启动时复用已注册的 `SceneManager` 场景识别，不新增模板或识别框架。
- R2：已在 `abyss_selection` 时保持原行为，进入神龙暗域。
- R3：已在任一具体暗域页或 `abyss_enemy_selection` 时直接进入现有业务循环，不执行 Home 拖拽；具体暗域页须同步 `cur_scene_index`，保持后续区域顺序一致。
- R4：识别为 `battling` 时停止启动并提示等待战斗安全结束后重试，不执行拖拽、点击、按键或伤害监控。
- R5：仅在明确识别为 `home` 时执行既有 Home → 日常 → 狭间暗域入口流程；其他未知或非支持页面安全停止并输出准确场景日志。
- R6：保留原有 Home 入口、选择页到神龙暗域、业务事件和配置行为。

## Acceptance Criteria

- [x] AC1：从 `abyss_selection` 启动仍调用 `goto_scene("abyss_dragon")`。
- [x] AC2：从 `abyss_dragon`、`abyss_fox`、`abyss_leopard`、`abyss_peacock` 启动不调用 `goto_abyss_shadows()` 或 `goto_scene()`，并设置对应 `cur_scene_index`。
- [x] AC3：从 `abyss_enemy_selection` 启动不执行入口导航，保留现有敌人选择业务处理。
- [x] AC4：从 `battling` 启动调用 `stop()`，且不执行任何入口动作。
- [x] AC5：从 `home` 启动仍执行既有 `goto_abyss_shadows()`，成功后进入神龙暗域。
- [x] AC6：未知或不支持场景不执行 Home 拖拽并安全停止。
- [x] AC7：狭间暗域定向流程与场景回放测试通过，且无与本任务相关的新增失败。

## Out of Scope

- 不把狭间暗域迁移到通用 `TaskEntrySpec`；现有 Home 入口包含专用拖拽与点击偏移，迁移属于独立任务。
- 不修复“已击破”OCR、战斗伤害 OCR 或其他狭间暗域业务逻辑。
- 不新增自动接管进行中的战斗；战斗归属无法从通用 `battling` 模板安全判断。
