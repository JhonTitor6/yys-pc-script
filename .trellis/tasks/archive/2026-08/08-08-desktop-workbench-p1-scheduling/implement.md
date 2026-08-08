# P1 实施计划

## 顺序清单

1. 扩展 ConfigField/schema 序列化和默认注册表元数据；补测试。
2. 增量迁移 workflow/step 调度字段和步骤级失败策略；补仓库/API 读写。
3. 扩展 SchedulerService 的策略执行、时间计算、预览和生命周期线程；发布调度事件。
4. 增加历史 run 列表/详情 API 和 GUI 历史、进度、日志、设置页面。
5. 将工作流编辑器接入步骤失败策略、启用/禁用、优先级和间隔配置；显示下一次运行预览。
6. 接入 P0 快照 reducer，验证页面切换、刷新和重连不丢控制入口。
7. 运行后端、GUI 语法/检测和跨层回归检查，记录既有失败。

## 验证命令

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend -v
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/ -v
node --check gui/renderer.js
node tests/gui/test_backend_detection.js
git diff --check
```

## 风险与回滚点

- 旧 SQLite 文件没有新列时必须自动补齐；不要删除或重建用户已有工作流/运行记录。
- 调度线程默认只处理明确启用且有支持触发类型的任务；未知类型只显示“不支持”，不触发。
- 步骤策略扩展不能改变旧 `stop_workflow` 的失败即停行为。
- GUI 页面先复用现有 DOM/CSS，避免一次性重写整个 renderer；每个新接口都有空数据降级文案。
