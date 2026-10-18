# 实施清单

1. 从指定录制提取最小脱敏场景帧与识别模板；保留来源和遮盖说明，不改 `recordings/`。
2. 实现 `DailyCollectScript`、状态快照、空配置元数据、每次新鲜截图与受保护输入。
3. 只实现已录制的一键完成、领取成功弹层确认、列表完成信号和庭院返回；禁止重复点击；停止或观察模式不得报告完成。
4. 在 `yys/daily_collect/test_daily_collect.py` 用真实模板匹配脱敏正负样本，并以模拟环境验证成功、重复帧、未知页、无成功信号、停止和观察模式。
5. 运行本模块 pytest、Ruff 和 `py_compile`；查看 diff 与 `git status --short`，确认没有触及分配目录以外文件。
6. 向主会话报告注册表 ID `daily_collect`、打包条目、父工作流依赖需要的共享接线，以及未覆盖的启动时已完成分支和实机边界。

## 验证命令

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest yys/daily_collect/test_daily_collect.py -q
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m ruff check yys/daily_collect
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m py_compile yys/daily_collect/__init__.py yys/daily_collect/daily_collect_script.py yys/daily_collect/test_daily_collect.py
```

## 本次结果

- 已实现并导出 `DailyCollectScript`；配置 schema 为空。原始视频与事件通过项目解码器检查；视频为 43 帧并完整解码。元数据为 `completed`，但 `stop_reason=emergency_stop`；末段仍包含稳定庭院帧。
- 模块测试：7 项通过；Ruff、`py_compile` 和 `git diff --check` 通过。`git diff --check` 仅显示其他现有工作区文件的换行格式提示。
- 未运行真实游戏；当前未完成初始页、其它庭院皮肤或已领取状态分支的实机验证。初始事务页若已有完成印章会安全停止，不执行一键点击。
- 注册表、打包清单和父工作流尚未接线，按任务分工由主会话完成；本任务未提交、推送或归档。
