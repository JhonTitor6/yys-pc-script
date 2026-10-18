# 工作流实施计划

1. 先用两步工作流复现 stopped 被误判成功、未知状态仍推进、缺失尾步骤在首步后才报错。
2. 最小修改调度器，保持公开 run_step 接口、旧错误策略和按时停止语义。
3. 添加六步默认禁用 JSON 配置草案，单人魂土默认 10 次可配置；不增加占位脚本。
4. 验证 `pytest tests/ui_backend/test_scheduler.py tests/ui_backend/test_p1_workbench.py tests/ui_backend/test_app_api.py`，并运行修改文件 Ruff、编译及 Git 空白检查。
5. 记录缺失素材及真实执行边界，六步联调和正式启用待对应脚本就绪，不自动提交、推送或归档。
