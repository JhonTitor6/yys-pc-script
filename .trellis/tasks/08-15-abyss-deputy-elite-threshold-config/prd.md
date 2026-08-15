# 狭间暗域副将与精英阈值配置

## Goal

用户可通过现有 schema 配置流程分别设置狭间暗域副将和精英伤害阈值，下一次运行严格使用保存值。

## Background

- `boss_damage_limit` 已接入 schema 和运行时；副将阈值 `1`、精英阈值 `6000000` 仍在 `Main.__init__()` 中硬编码。
- 三类敌人都使用 `Enemy.target_damage`，现有退出条件是 `current_damage > target_damage`，无需新增阈值判断分支。
- GUI 根据 `config_schema` 通用渲染并提交原始键；生产注册优先反射 `SCRIPT_META`，`default_registry.py` 仍需同步兜底字段。
- `boss_count`、`commander_count`、`elite_count` 当前未接入硬编码的 `max_challenge_counts`，不属于本任务。

## Requirements

- R1：在 `AbyssShadowsConfig` 增加非热重载数值字段 `commander_damage_limit` 与 `elite_damage_limit`，标签分别为“副将伤害限制”“精英伤害限制”，范围与首领阈值一致。
- R2：`Main.SCRIPT_META.default_config` 和 `ui_backend/scripts/default_registry.py` 增加原始 snake_case 键；默认值分别保持 `1` 和 `6000000`，旧配置缺字段时正常回退。
- R3：`Main.__init__()` 只使用实例配置属性初始化敌人：BOSS 使用 `boss_damage_limit`，副将使用 `commander_damage_limit`，精英使用 `elite_damage_limit`。
- R4：保留现有严格大于比较；伤害等于阈值不退出，超过阈值才执行既有退出流程。
- R5：挑战次数、敌人优先级、位置、识别、OCR、BOSS 阈值和退出按键行为保持不变。

## Acceptance Criteria

- [ ] AC1：`/api/scripts` 和 GUI 配置页显示两个新字段，保存请求使用 `commander_damage_limit`、`elite_damage_limit` 原始键，并明确下次启动生效。
- [ ] AC2：重新打开配置可读取保存值；下一次构造脚本时，所有副将只取得副将阈值，所有精英只取得精英阈值，BOSS 仍只取得 BOSS 阈值。
- [ ] AC3：旧配置缺少新字段时脚本正常启动，副将默认为 `1`、精英默认为 `6000000`；`default_registry` 回退结果一致。
- [ ] AC4：修改任一阈值不会改变另外两类敌人的 `target_damage`，也不会改变三个挑战次数与敌人选择顺序。
- [ ] AC5：伤害等于各自阈值时不退出，超过阈值时执行现有退出流程。
- [ ] AC6：既有狭间流程/API 回归测试通过，GUI schema 通用渲染不增加脚本专属分支。

## Out of Scope

- 不接线或重构三个挑战次数配置，不改变 OCR、敌人优先级、退出流程或阈值比较符。
