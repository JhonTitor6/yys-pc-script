# 狭间暗域已击破识别实施计划

## Implementation

1. 在狭间暗域脚本中实现红色印章连通区域检测，补齐类型提示和中文公共说明。
2. 将检测接入 `get_next_enemy()`，识别后写入 `has_challenged` 并继续按既有优先级扫描。
3. 修正 `_handle_no_enemy_available()` 的最后区域索引边界。
4. 更新已有单元测试：识别结果影响候选选择，但不改变次数上限和优先级。
5. 基于旧 1154×680 场景图和新录制事件 1 的 1136×640 战报画面制作隐私安全的最小素材，覆盖首领、副将、精英的正负样本。
6. 增加跨两种客户区尺寸的真实图片回归测试，确保检测阈值使用裁剪比例而非固定像素面积。

## Validation

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest `
  yys/abyss_shadows/test_abyss_shadows_flow.py `
  yys/abyss_shadows/test_abyss_shadows_scene_replay.py `
  -v -s
```

同时运行：

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m py_compile `
  yys/abyss_shadows/abyss_shadows_script.py `
  yys/abyss_shadows/test_abyss_shadows_flow.py `
  yys/abyss_shadows/test_abyss_shadows_scene_replay.py
```

## Review Gates

- 正样本中五个印章全部命中，未盖章首领不命中。
- 新录制最小素材中的首领、两个副将印章全部命中，三个未盖章精英不命中。
- 负样本六个目标全部不命中。
- 测试必须经过真实 OpenCV 路径，不能用 `MagicMock` 代替 `cv2`、`numpy` 或根 `PIL`。
- 原始录制及含聊天内容的完整截图不得加入 Git。
- 提交前确认不包含 `yys/douji/douji_script.py`。

## Rollback

检测逻辑与状态机接入保持为局部改动；若误报率不满足要求，可回退新增检测和对应测试，不影响现有伤害配置功能。
