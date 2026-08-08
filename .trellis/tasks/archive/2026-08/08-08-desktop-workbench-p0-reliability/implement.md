# P0 实施计划

## 顺序清单

1. 扩展模型、SQLite 幂等迁移、run/证据仓库，并补充回归测试。
2. 统一 EventHub 事件元数据、序号和按序回放能力。
3. 在 RunManager 中接入阶段/进度/错误码、available_actions、失败日志与截图证据。
4. 增加 current snapshot、历史/详情、证据和 retry/skip/manual takeover API；调整 WebSocket 首包顺序。
5. 更新 GUI 首屏的连接/阶段/进度/日志/证据和状态驱动控制按钮；接入重连快照 reducer。
6. 运行 P0 定向测试、全部 `tests/ui_backend`、Node 语法检查和 `git diff --check`。

## 验证命令

```powershell
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend -v
node --check gui/renderer.js
node --check gui/main.js
node --check gui/preload.js
git diff --check
```

## 风险与回滚点

- 数据库迁移只能增列/增表，先用临时数据库测试；若迁移失败不得覆盖原文件。
- RunManager 的线程锁与脚本回调不能互相持锁；沿用现有先取回调、释放锁后调用的模式。
- 证据捕获失败不能阻塞脚本错误收尾；捕获器必须吞掉自身异常并记录原因。
- 前端先保持旧字段兼容，快照字段缺失时使用空闲/未知文案，不抛异常。
