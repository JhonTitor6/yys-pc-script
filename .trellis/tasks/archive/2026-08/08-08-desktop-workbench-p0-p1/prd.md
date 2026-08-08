# P0/P1 桌面工作台可靠性与调度

## Goal

把现有“能启动脚本”的 Electron/FastAPI 原型收敛为可观察的自动化任务工作台：用户能判断当前连接、运行、步骤和动作状态，失败时能看到原因、证据和可执行恢复动作；随后能创建可复用任务、查看历史并配置最小周期调度。

## Background

- 现有后端入口为 `ui_backend/app.py:29`，运行生命周期集中在 `ui_backend/runs/manager.py:32`，事件广播由 `ui_backend/events/hub.py:11` 负责，数据落在 SQLite。
- 当前已经具备脚本注册、配置 schema、单执行槽、日志和状态快照，但 `GET /api/runs`、运行详情/历史、证据关联、统一快照和恢复动作尚未形成契约。
- `ui_backend/scheduler/service.py:17` 目前按步骤顺序执行，失败策略只等价于停止；工作流的启用、优先级、成功/失败间隔和下一次运行没有真正参与调度。
- `gui/index.html` 与 `gui/renderer.js:677` 已有深色执行页和编排编辑器，但进度、日志、设置导航仍禁用，运行控制主要嵌在左侧脚本卡片中。
- 交接文档提到的 `docs/2026-08-08-external-project-learning-conclusions.md` 在本工作树缺失；本规划只采用仓库现有设计文档、源码和测试可验证的内容。

## Scope and child tasks

- `08-08-desktop-workbench-p0-reliability`：先建立 P0 的状态、事件、证据、恢复和刷新恢复契约。
- `08-08-desktop-workbench-p1-scheduling`：依赖 P0 的运行契约，补齐配置元数据、历史、工作流策略、调度和工作台页面边界。
- P1 不迁移 React/Tailwind，不改写具体游戏脚本识别/点击逻辑；所有运行仍经过既有单客户端 `RunManager`。

## Cross-child requirements

- 保留已有行为：`POST /api/runs/start` 继续接受 `script_id/config` 并返回 `id`；`queued/running/paused/success/error/stopped` 现有状态值和单执行槽约束不被破坏；已有日志、快照、工作流创建接口保持兼容。
- 运行事实必须只有一个来源：API、WebSocket 和 GUI 都消费同一份规范化运行快照，不能各自推断状态。
- 不能把暂未实现的能力显示成可点击的成功路径；按钮和危险操作由快照中的 `available_actions` 驱动。
- 运行期间切换页面、刷新页面或 WebSocket 重连都不能丢失当前运行的状态和控制入口。

## Acceptance Criteria

- [x] P0 子任务的验收标准全部通过：失败可定位到任务/步骤/动作、错误码、日志和证据，刷新/重连可恢复快照，恢复动作状态驱动。
- [x] P1 子任务的验收标准全部通过：配置元数据可渲染，历史详情可回看配置/步骤/日志/快照/证据，工作流策略和周期调度可预览且实际执行时间使用同一计算规则。
- [ ] 现有 `tests/ui_backend` 与 GUI 语法/后端检测测试通过；新增契约测试覆盖成功、失败、重连、历史和调度边界。
- [x] 已知基线失败单独记录，不将与本任务无关的 `realm_raid.default_config["max_battle_count"]` 期望差异误归因于本任务。

## 验收记录

- P0/P1 定向集合和新增契约测试通过；完整 UI 后端集合为 64 passed，保留 1 个既有基线失败。
- GUI Node 检查、后端检测、Python 编译和差异空白检查通过。

## Out of scope

- 不做整套前端框架迁移、外部项目代码搬运、多客户端并行、自动从快照续跑、Windows 后台服务或具体游戏脚本核心逻辑重构。
- 不承诺在无截图能力的脚本/测试替身中伪造游戏截图；此时应记录证据缺失原因，并保证真实运行路径尽力捕获当前画面。
