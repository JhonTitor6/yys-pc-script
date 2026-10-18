# 单人魂土实施计划

- [x] 核验录制元数据、21 个事件、42 张截图及视频完整解码；归纳界面与返回证据边界。
- [x] 评审需求、技术方案和父任务接线边界；激活既有子任务。
- [x] 新建 `yys/soul_soil/`，实现 `SoulSoilScript`、`SCRIPT_META`、三字段反射 schema 与包导出。
- [x] 提取必要生产模板与脱敏关键页 JPEG 夹具；原始录制未改动。
- [x] 编写包内离线测试：模板正负样本、单人/组队按钮、Lobby 御魂/魂土预设、重复名消歧、结算防重/次数上限、停止与观察模式、返回控件。
- [x] 使用项目 Conda 环境运行：`python -m pytest yys/soul_soil/test_soul_soil.py -q` → 10 passed；`python -m ruff check yys/soul_soil` → All checks passed；`python -m compileall -q yys/soul_soil` → 通过。
- [x] 检查限定目录并确认未修改其他会话文件；注册表、打包和父工作流接线清单见下。

## 主会话共享接线

- `ui_backend/scripts/default_registry.py` 增加 `script_id="soul_soil"`、`module_path="yys.soul_soil"`、`class_name="SoulSoilScript"`，显示名“单人魂土”；schema 留空以便现有注册表反射 `get_config_schema()`。实机验证前建议分类为 `experimental`。
- `build_backend.spec` 加入 `yys.soul_soil` 包及图片资源。
- 父工作流的御魂步骤改用 `soul_soil` 和 `max_battle_count=10`、`lineup_group="御魂"`、`lineup_name="魂土"`；旧 `soul_raid` 保持不变。
- 更新全局脚本注册/运行管理测试，验证 ID、反射 schema 和模块可导入，不启动真实游戏。
- 2026-10-18 用户纠正只有首行是魂土，下方为魂王；已删除按首行取同名的适配器。共享名称识别排除应用按钮不可操作的底部残缺行，单人准备页也只查完整卡片，真实重名仍拒绝。

## 验收边界

录制只证明一场挑战到“发现宝藏”弹窗。第二场起的循环、宝藏关闭后 `to_home` 返回庭院、RunManager 注册/打包均未实机或集成验证；上述单元测试只证明离线截图和状态契约，不等于实机通过。本子任务保持 `in_progress`，等待主会话完成共享接线；不提交、不推送、不归档。
