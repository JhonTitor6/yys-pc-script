# 狭间暗域印章形状识别实施计划

## 0. 开始前门禁

- [x] 已创建独立 Trellis 任务，当前工作树和其他活动任务不纳入本任务。
- [x] 已读取 `AGENTS.md`、Trellis workflow、backend 规范、质量契约和代码复用指南。
- [x] 已确认现有脏文件并保留，不覆盖用户改动。
- [x] 审核本任务 `prd.md`、`design.md`、`implement.md` 后运行 `task.py start`。

## 1. 资源与生产识别

- [x] 将已验证的 `recordings/abyss_stamp_validation/2026-09-05/template_mask.png` 复制为 `yys/abyss_shadows/images/defeated_stamp_mask.png`。
- [x] 在 `Main` 中新增最小资源路径/阈值常量和一次性模板加载；使用 `to_project_path()`、`np.fromfile()`、`cv2.imdecode()`，校验尺寸、dtype、二维和非纯色。
- [x] 删除旧连通块几何常量、`connectedComponentsWithStats()` 和填充率判断。
- [x] 实现红色掩膜的 `TM_CCOEFF_NORMED` 匹配，处理截图/尺寸/结果边界，阈值固定为 0.50。

## 2. 真实图像回归

- [x] 从已核实的完整战斗录制和黑豹截图各提取 `(342,120,905,435)` 局部 PNG，保存到 `tests/fixtures/abyss_shadows/defeated_stamp/`；视觉确认不含顶部聊天或账户信息。
- [x] 扩展 `yys/abyss_shadows/test_abyss_shadows_flow.py`，让测试直接调用生产 `_is_enemy_defeated()`，覆盖 30 个人工标签、原漏判的首领/左副将、红色衣饰/头饰、纯红/纯黑及异常输入。
- [x] 保留并验证既有候选顺序、挑战计数、跳过逻辑和最后区域停止断言；测试注释标明产品契约来源。

## 3. 检查与交付

- [x] 运行生产相关 pytest：`test_abyss_shadows_flow.py`、`test_abyss_shadows_scene_replay.py`。
- [x] 运行生产代码 Ruff、`py_compile` 和 `git diff --check`；确认资源位于既有打包资源收集范围内。
- [x] 用 `git diff --name-only` 和 `git status --short` 确认只报告本任务新增/修改文件，既有无关脏文件不混入。
- [x] 按 `trellis-check` 做最终质量核对；已将固定模板匹配契约固化到 `.trellis/spec/backend/quality-guidelines.md`。
- [ ] 向用户报告离线结果、未做实机验证和提交前状态；不执行提交或归档，等待用户明确决定。

## 验证命令

```powershell
& 'D:/ProgramData/anaconda3/envs/win_macro/python.exe' -m pytest yys/abyss_shadows/test_abyss_shadows_flow.py yys/abyss_shadows/test_abyss_shadows_scene_replay.py -q
& 'D:/ProgramData/anaconda3/envs/win_macro/python.exe' -m ruff check yys/abyss_shadows/abyss_shadows_script.py
& 'D:/ProgramData/anaconda3/envs/win_macro/python.exe' -m py_compile yys/abyss_shadows/abyss_shadows_script.py yys/abyss_shadows/test_abyss_shadows_flow.py
git diff --check
git status --short
```
