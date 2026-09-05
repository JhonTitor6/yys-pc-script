# 狭间暗域印章形状识别设计

## 1. 设计结论

- 只替换 `Main._is_enemy_defeated()` 的视觉判定，继续由 `get_next_enemy()` 负责业务跳过，不改变调用者。
- 在 `Main.__init__()` 中加载一次固定 68×30 灰度二值模板；每次识别只对当前敌人矩形生成 HSV 红色掩膜并做二值空间匹配。
- 复用 `to_project_path()` 解析项目资源路径，使用 `np.fromfile()` + `cv2.imdecode()` 读取模板，避免 Windows 中文路径问题。

## 2. 数据流与边界

1. `get_next_enemy()` 传入一个 `Enemy.label_and_pic_position`。
2. `_is_enemy_defeated()` 从 `image_finder.screenshot_cache` 通过现有 `crop_screenshot_cache()` 获取本敌人检测矩形。
3. 输入检查通过后，BGR 图像按现有两个 HSV 红色范围转换为单通道 `uint8` 掩膜。
4. 以模板为搜索图，对掩膜执行 `TM_CCOEFF_NORMED`，取有限最大分数；达到 0.50 才返回 `True`。
5. `True` 只影响现有调用者设置 `enemy.has_challenged=True` 并继续扫描；计数、点击和结算逻辑不接收新分支。

## 3. 资源加载契约

- 资源 ID：`yys/abyss_shadows/images/defeated_stamp_mask.png`。
- 期望形状：高 30、宽 68、二维 `uint8`；必须包含至少两个像素值且非全零。
- 文件不存在、无法解码、通道数错误、尺寸错误或模板无有效变化时抛出明确 `ValueError`；不回退到旧连通块算法。
- 模板作为实例字段保存；不在敌人循环、截图循环或每轮战斗中重复读取。

## 4. 异常与兼容

- 生产截图为 `None`、裁剪为空、非三通道、非 `uint8`、小于模板或 OpenCV 转换/匹配失败时返回 `False`。
- `cv2.matchTemplate()` 返回空结果或非有限最大分数时返回 `False`。
- 生产不调用普通彩色模板匹配，也不复用 `ImageFinder.bg_find_pic*()` 的灰度+HSV 合成分数；本任务使用独立的红色掩膜空间匹配。
- 不改变公共 `ImageFinder.crop_screenshot_cache()` 的越界/缓存行为。

## 5. 测试设计

- 在现有 `test_abyss_shadows_flow.py` 扩展真实生产识别回归，保留真实 `cv2`、`numpy` 和根 `PIL` 包。
- 三张已跟踪完整战报图继续按原坐标测试；新增两个最小 563×315 局部 PNG，分别来自完整战斗录制负样本和黑豹已击破截图，并在测试中还原到原坐标。
- 用人工标签而非检测器输出生成期望值：前三张共 18 区域，负样本局部 6 个 `False`，黑豹局部 6 个 `True`，合计 11 正/19 负。
- 增加纯红、纯黑、截图缺失、空裁剪、无效通道/类型和尺寸不足的安全返回断言；保留原有 `get_next_enemy()` 顺序与最后区域安全停止测试。

## 6. 回滚边界

- 代码回滚只涉及模板资源、`abyss_shadows_script.py` 和狭间 flow 测试/夹具；不回退其他脏文件。
- 由于真实游戏当前不可用，离线回归通过不等价于实机验证；交付时单独标明这一点。
