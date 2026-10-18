# 逢魔实施与验证

1. 提取可确认的入口和集结边界模板，核实录制的预设名称。
2. 新增独立实验脚本与注册项，集结和战斗持续识别并保持零输入，复用通用结算／领奖回调，单次计数防重。
3. 运行 `python -m pytest yys/fengmo tests/ui_backend/test_script_registry.py tests/common/test_guarded_cli.py -q`。
4. 按“已识别返回 → 新截图识别 to_home → 已确认庭院”执行退出，覆盖同屏两个按钮、重复结算、战斗零输入、未知页和用户停止；不操作实机。
