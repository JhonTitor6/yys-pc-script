# 设计：每日活跃度奖励独立脚本

## 边界

- 包：`yys/daily_activity_rewards/`；公开 `DailyActivityRewardsScript`。
- 夹具：`tests/fixtures/daily_activity_rewards/`，只保存必要的脱敏裁剪帧；原始 `recordings/` 不变。
- 不改共享注册表、打包清单、公共模块、父工作流或全局测试。主会话接入时使用注册 ID `daily_activity_rewards`。

## 接口与配置

- 构造：`DailyActivityRewardsScript(script_name="daily_activity_rewards", config=None, env=None)`。
- 继承 `YYSBaseScript`，由 `ScriptMeta("每日活跃度奖励", "日常", None, {})` 暴露空配置 schema；不增加没有用户决策价值的配置项。
- `run()` 保持脚本既有同步接口。`get_state_snapshot()` 增加阶段、领奖状态、已确认领取次数和业务结果，且不改变通用战斗计数。

## 数据流

1. 通过 `GameEnvironment.capture_screen()` 每次取新帧；校验客户区比例，缩放到录制基准坐标供识别，再按实际尺寸换算点击点。识别使用 OCR 与已有 `SceneManager` / `ImageFinder`，截图失败不回退到缓存帧。
2. 必须先识别庭院。菜单收起时只点击录制帧裁出的展开控件；菜单展开后只点击底部唯一的“花合战”OCR 结果。等待并重新识别标题“花合战”及“今日”标签。
3. 读取领取按钮区域和“今日获得经验”字段：唯一的“全部”+“领取”判为可领；按钮缺失且经验大于零判为已领；按钮缺失且经验为零判为未达条件；OCR 不全、重复或矛盾时失败。
4. 可领时只点击一次 OCR 定位的按钮。必须看到“获得奖励”标题后，调用 `YYSBaseScript._on_battle_end()` 清理已确认的弹窗；覆盖 `_should_count_battle_end()` 返回 `False`，避免活跃奖励改变战斗计数。基类清理会随机偏移点击位置，本模块覆盖 `bg_left_click()` 将 OCR 命中点原样交给 guarded environment，避免点到弹窗外。弹窗持续帧最多清理 3 次；不在循环里重新点领取。
5. 奖励弹窗消失后重新识别今日页，并验证领取按钮消失且今日经验高于领取前。随后用已识别的公共 `return.bmp` 返回，重新截图并要求 `SceneManager` 识别为 `home`。
6. 每次输入前走同一个 guarded environment 与 `RunGuard`。暂停/停止在读取和输入检查点生效；观察模式只记录计划动作，并以非成功结果结束，不继续下一步。

## 识别校准

- 录制正样本：庭院场景模板 `home.bmp` 的 `ImageFinder.best_match` 相似度约 0.856；花合战菜单展开模板约 0.933；返回箭头模板在今日页约 0.725。返回模板仅在花合战标题已确认且限定左上 ROI 时使用。
- 可领取按钮在录制帧中拆成两行 OCR：“全部”约 (834,551)、“领取”约 (831,574)；以当帧结果聚合点击，不使用事件坐标。
- “获得奖励”OCR 在弹窗中置信度约 0.98；领取后画面为今日经验 36、等级 20/进度 33/100。共用 `gained_reward.bmp` 与 `battle_end*.bmp` 对弹窗的最佳灰度相似度分别最高约 0.257 和 0.541，不足以作为弹窗识别，因此不误用这些模板。

## 失败策略

- 未从庭院启动、无法唯一识别菜单/按钮/弹窗、转场超时、经验未增加、弹窗超出清理上限、返回后未识别到庭院：设置失败状态并抛出明确错误。
- 用户停止或观察模式保留各自状态，不将其记录为业务完成。
- `not_eligible` 与 `already_claimed` 不执行领取输入；记录状态后安全返回庭院。
- 观察模式抛出 `[DAILY_OBSERVE]`：当前 `RunManager` 会把正常返回标为成功，因此主会话接线时需将该码映射为非成功终态，或确保工作流不会推进。

## 验证

- 单元/录制帧测试位于模块目录，固定夹具只含裁切和脱敏后的控件/页面区域。
- 运行模块 pytest、Ruff、Python 编译检查；不运行真实游戏。
- 真实游戏的返回动作与无可领状态没有本录制证据，验收报告需保留该验证边界。
