# P0/P1 集成实施计划

## 顺序清单

1. 完成并激活 P0 子任务，先落地统一运行快照、事件序号、失败证据和恢复动作。
2. 运行 P0 定向测试并确认旧 API、日志、快照和单执行槽行为未改变。
3. 激活 P1 子任务，在 P0 契约上扩展 schema、历史、步骤策略和调度。
4. 运行 P1 定向测试、全量 UI 后端测试、GUI Node 检查和跨层数据流检查。
5. 在父任务做最终集成验收：刷新/重连、运行控制、历史详情、调度预览/实际时间和不支持能力文案。

## 集成验证

```powershell
python ./.trellis/scripts/get_context.py --mode packages
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend -v
node tests/gui/test_backend_detection.js
node --check gui/renderer.js
git diff --check
```

## 回滚和既有变更

- 每个子任务以增量迁移和局部前端修改为主；父任务不回滚用户已有工作树内容。
- 当前工作树实际状态需在每次实现前后用 `git status --short` 核对；交接中提到的未跟踪研究文件在本工作树不存在，不在本次补造。
- 若完整调度线程或新页面验证受环境限制，保留后端契约和测试结果，并明确未验证的 Electron 手动项。
