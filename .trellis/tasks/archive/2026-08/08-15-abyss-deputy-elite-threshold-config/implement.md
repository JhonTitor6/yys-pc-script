# 狭间暗域副将与精英阈值配置实施计划

## Order

1. 先更新 `yys/abyss_shadows/test_abyss_shadows_flow.py` 和 registry/API 测试，写出三类阈值隔离、默认值、边界比较的产品契约断言。
2. 在 `AbyssShadowsConfig`、`SCRIPT_META.default_config` 增加两个非热重载字段。
3. 用实例配置属性替换副将和精英局部硬编码，不改敌人列表、位置或退出函数。
4. 同步 `ui_backend/scripts/default_registry.py` 的导入失败兜底 schema。
5. 运行狭间、注册表、API、GUI 配置归一化回归。

## Expected Files

- `yys/abyss_shadows/abyss_shadows_script.py`
- `yys/abyss_shadows/test_abyss_shadows_flow.py`
- `ui_backend/scripts/default_registry.py`
- `tests/ui_backend/test_script_registry.py`
- `tests/ui_backend/test_app_api.py`
- `tests/gui/test_renderer_config.js`（仅在需要补原始键回归时）

## Validation

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest yys/abyss_shadows/test_abyss_shadows_flow.py tests/ui_backend/test_script_registry.py tests/ui_backend/test_app_api.py -v
node tests/gui/test_renderer_config.js
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m compileall yys/abyss_shadows ui_backend/scripts
git diff --check
```

## Risk and Rollback Points

- `tests/ui_backend/test_script_registry.py` 有狭间字段精确集合断言，必须与产品 schema 同步，不能只追加 API 测试。
- 不修改 `max_challenge_counts`，避免把伤害阈值需求扩大为挑战次数修复。
- 不改 OCR、敌人选择和 Enter 退出逻辑；回滚只涉及两个字段和两处运行时赋值。
