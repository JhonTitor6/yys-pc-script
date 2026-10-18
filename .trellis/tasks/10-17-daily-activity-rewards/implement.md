# 实施计划：每日活跃度奖励独立脚本

## 顺序

1. 核验录制元数据、事件序号/坐标、25 帧视频解码结果和关键画面；原始录制只读。
2. 从已确认帧提取必要裁切并遮蔽个人/动态信息，存放在任务分配的夹具目录；需要的控件模板只保存到新模块 `images/`。
3. 实现 guarded `DailyActivityRewardsScript`：庭院 → 菜单 → 花合战今日页 → 领奖状态判断 → 一次领取与有限弹窗清理 → 返回庭院确认。
4. 在 `yys/daily_activity_rewards/test_daily_activity_rewards.py` 覆盖状态分类、基于真实裁切帧的识别、领取只触发一次、奖励弹窗重复帧上限、停止/观察和庭院终态确认。
5. 运行指定模块测试、Ruff、编译检查和 Git diff/状态审阅；不改变已有工作区修改、不执行实机输入。

## 验证命令

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest yys/daily_activity_rewards -q
& 'D:/ProgramData/anaconda3/envs/win_macro/Scripts/ruff.exe' check yys/daily_activity_rewards
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m compileall -q yys/daily_activity_rewards
git diff --check
```

## 主会话接线清单

- 在 `ui_backend/scripts/default_registry.py` 注册 `daily_activity_rewards` → `DailyActivityRewardsScript`。
- 在 `build_backend.spec` 的 `YYS_MODULES` 中加入 `yys.daily_activity_rewards`。
- 在主会话管理的父工作流/注册测试里确认脚本导入、步骤顺序及 `stopped` / 非完成状态不误推进。
- 当前 `RunManager` 会把正常返回的观察结果标为成功；接线时需将 `[DAILY_OBSERVE]` 映射为非成功终态，避免工作流推进。
- 注册接线与跨层测试不属于本子任务修改范围。

## 完成门槛

- 仅在本模块离线验证通过且状态/失败边界有测试后报告代码完成。
- 不提交、不推送、不归档、不操作真实游戏；未录制的返回庭院路径和无可领实机状态保持未验证。

## 2026-10-18 实施记录

- 导出类：`DailyActivityRewardsScript`；`SCRIPT_META.config_schema=None`、`default_config={}`，没有配置字段。
- 测试：`D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest yys/daily_activity_rewards -q`，5 项通过。
- Ruff：`D:/ProgramData/anaconda3/envs/win_macro/Scripts/ruff.exe check yys/daily_activity_rewards`，通过。
- 编译：`D:/ProgramData/anaconda3/envs/win_macro/python.exe -m compileall -q yys/daily_activity_rewards`，通过。
- `git diff --check` 退出码为 0；只报告工作区原有文件的 LF/CRLF 提示。
- 未执行真实游戏。无奖励状态和返回庭院路径仅做代码/合成帧回放验证，仍需主会话接线后安排实机验证。
