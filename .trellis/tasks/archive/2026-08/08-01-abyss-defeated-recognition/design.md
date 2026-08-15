# 狭间暗域已击破识别设计

## Problem Boundary

识别发生在战报截图缓存内，每个 `Enemy` 已持有头像与标签的矩形区域。业务层只需要得到稳定的布尔结果，不应依赖 OCR 能否读出倾斜、描边的小号艺术字。

## Detection Design

1. 从 `image_finder.screenshot_cache` 按 `Enemy.label_and_pic_position` 裁剪候选区域。
2. 转换到 HSV 色彩空间，提取高饱和度、高亮度的红色像素。
3. 对红色二值图执行连通区域统计。
4. 将连通区域的宽度、高度、面积和长宽比与候选裁剪尺寸比较。
5. 只要存在符合印章几何特征的连通区域，即判定为已击破。

所有阈值使用裁剪尺寸的比例表示；颜色阈值集中定义，避免散落魔法值。旧 1154×680 夹具中，已击破印章的最大红色连通区域面积为 811–1002 像素，未击破样本最大为 0–434 像素，具备可验证分界。新增 1136×640 录制必须用于复核比例阈值，不能把旧图的绝对面积直接固化为判断条件。

## Fixture Strategy

- 旧 1154×680 夹具覆盖副将和精英印章，以及无印章首领。
- 新 1136×640 录制覆盖首领和副将印章，以及无印章精英。
- 原始录制顶部含聊天内容，只能留在 Git 忽略的 `recordings/`；提交的测试素材必须裁取检测所需最小区域并经过人工隐私复核。
- 完整战斗录制用于理解真实流程，不纳入本任务的状态转换夹具，因为它没有捕获胜利后返回战报的稳定终态。

## State Flow

```text
get_next_enemy
  → 跳过 has_challenged=True
  → _is_enemy_defeated(enemy.label_and_pic_position)
      → True：写入 has_challenged=True，继续扫描
      → False：返回当前 enemy
  → 无候选：_handle_no_enemy_available
```

`has_challenged` 在这里同时表示“本轮脚本已尝试”和“战报已显示击破”。切换到新暗域后继续复用 `_reset_enemies_challenge_status()` 清空内存状态，并在新截图上重新识别。

## Boundary Fix

`_handle_no_enemy_available()` 应在递增前判断 `cur_scene_index >= len(scene_name_list) - 1`。最后一个区域完成时直接停止；否则再递增并切换区域，避免访问越界。

## Compatibility and Rollback

- 不改变公共 OCR、图像查找器或 `Enemy` 数据结构。
- 检测失败默认视为“未击破”，保持当前选择行为，避免误跳过可挑战目标。
- 如真实新素材显示颜色规则不足，可独立回滚检测函数或增加经过确认的印章模板，不影响状态机接口。

## Trade-offs

- OCR 语义明确，但已被真实夹具证明无法识别该艺术字。
- 完整模板匹配更强调形状，但需要新增二进制模板并受底层头像干扰。
- HSV 连通区域无需新增模板，能屏蔽大部分底图内容；代价是必须通过正负真实夹具约束阈值和误报。
