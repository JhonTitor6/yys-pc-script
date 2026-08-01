# 将首领伤害限制移至界面配置

## Goal

让用户在启动“狭间暗域”脚本前从界面设置首领伤害限制，避免每次调整阈值都要修改源码。

## Background

- `yys/abyss_shadows/abyss_shadows_script.py` 当前在构造首领 `Enemy` 时直接写入伤害阈值。
- 当前工作区的未提交修改已将首领阈值从 `999999999` 调整为 `1`；本任务保留 `1` 作为默认行为，不覆盖该用户修改。
- GUI 已根据 `SCRIPT_META.config_schema` 自动渲染数字配置，并通过用户配置与运行请求将值传入脚本，无需新增专用前端控件。

## Requirements

- 在 `AbyssShadowsConfig` 中新增仅针对首领的整数配置字段 `boss_damage_limit`。
- 界面显示名称使用“首领伤害限制”，默认值为 `1`，允许输入非负整数，最大值覆盖现有“不设上限”历史值 `999999999`。
- `Main.SCRIPT_META.default_config` 必须包含该字段，保持 schema 与默认配置键集合一致。
- 初始化首领敌人时必须使用实例上的 `boss_damage_limit`，不再硬编码阈值。
- 副将和精英的现有阈值及行为不属于本次修改范围。
- 同步 `ui_backend/scripts/default_registry.py` 中狭间暗域的回退 schema，保证脚本反射失败时界面仍能展示该配置。
- 保留 `yys/abyss_shadows/abyss_shadows_script.py` 中现有的其他未提交修改。

## Acceptance Criteria

- [x] `GET /api/scripts` 对狭间暗域返回 `boss_damage_limit` 数字字段，默认值为 `1`。
- [x] 未显式传入配置时，首领 `Enemy.target_damage` 为 `1`。
- [x] 显式传入 `boss_damage_limit` 时，首领 `Enemy.target_damage` 使用传入值。
- [x] 超出 schema 范围的值继续由公共配置校验拒绝。
- [x] 狭间暗域流程测试与脚本注册表相关测试通过。

## Out of Scope

- 不把副将、精英伤害限制迁移到界面。
- 不改变 OCR 识别、伤害比较或退出战斗逻辑。
- 不增加运行中的专用配置编辑界面。
