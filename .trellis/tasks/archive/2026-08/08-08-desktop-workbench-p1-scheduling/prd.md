# P1 任务工作台与调度体验

## Goal

在 P0 统一运行契约上补齐任务定义、历史回看和最小周期调度，让新增任务通过 schema 和组件边界接入，而不是复制整页 HTML。

## Confirmed facts and anchors

- `ui_backend/models.py:50` 的 `ConfigField` 已有类型、默认值、范围和选项，但没有说明、单位和敏感性元数据。
- `ui_backend/scripts/registry.py:76` 负责解析集中注册表/类内 schema，`ui_backend/app.py:68` 直接序列化字段。
- `ui_backend/storage/database.py:18` 已保存 workflow 与 step，但 step 没有独立失败策略，workflow 的触发配置尚未驱动后台调度。
- `ui_backend/scheduler/service.py:17` 当前只顺序执行并按错误停止，未实现 continue/ retry/ manual 的完整语义。
- `ui_backend/app.py:116` 已有日志/快照查询和编排 CRUD 雏形，但没有历史 run 列表/详情；`gui/index.html` 的 progress/logs/settings 导航被禁用。
- `gui/renderer.js:123`、`:677` 已有脚本/运行渲染边界，适合在原生 HTML/CSS/JS 上扩展可复用渲染函数，不引入新前端框架。

## Requirements

### P1-1 配置元数据

- 字段元数据支持类型、默认值、范围、说明、单位、敏感性和热更新能力；后端返回稳定 schema，前端通用渲染。
- 现有注册表字段保持兼容，缺省元数据使用安全默认值。

### P1-2 工作流和步骤

- 工作流可启用/禁用、设置优先级、成功间隔、失败间隔和触发方式；步骤可配置脚本参数和步骤级失败策略。
- 支持 stop/continue/retry/skip/manual 的明确语义；暂不支持的调度类型和恢复能力在 API/UI 中明确标注。

### P1-3 历史与证据回看

- 提供历史运行列表、过滤/分页和单次运行详情；详情包含配置、工作流/步骤、最终状态、错误、日志、状态快照和证据。
- 运行页、历史页和通知/关键日志区域职责分离；切换页面不丢失当前运行控制入口。

### P1-4 周期调度最小闭环

- `interval` 和 `scheduled_time` 至少可预览下一次运行；启用任务按同一时间计算规则实际触发。
- 成功和失败分别使用配置的间隔计算下一次运行；优先级决定同一时刻多个任务的选择顺序。
- 单客户端仍只有一个执行槽；槽被占用时调度结果必须可观察，不得静默丢任务。

### P1-5 前端边界与门槛

- 启用执行、进度、历史日志和设置入口；使用现有深色高对比工作台，长任务不使用持续遮挡的全屏弹窗。
- 增加与当前原生 JS 技术栈匹配的语法检查/基础测试门槛，保持 HTML/CSS/JS 无构建依赖。

## Acceptance Criteria

- [x] `/api/scripts` 返回的每个配置字段包含可渲染的说明/单位/敏感性元数据，前端新增脚本无需复制 HTML。
- [x] 工作流可保存并读取启用状态、优先级、成功/失败间隔、下一次运行和步骤级失败策略；旧工作流数据可正常读取。
- [x] 一个成功步骤推进下一步；continue/skip 会继续，retry 按次数重试，stop/manual 会停止并发布可观察事件。
- [x] 历史列表和详情可查看至少一条已完成/失败 run 的配置、步骤、日志、快照和证据；过滤参数不会影响当前运行。
- [x] 周期调度的预览时间与实际触发使用同一计算函数；成功/失败分别采用对应间隔，优先级可验证。
- [x] 页面切换、刷新和 WebSocket 重连后当前运行控制入口仍可用；不支持的能力显示为禁用/说明而不是伪成功。
- [ ] 后端测试、GUI Node 语法/检测测试和 `git diff --check` 通过。

## 验收记录

- P1 契约与 P0 回归定向集合：46 passed。
- `node --check`、GUI 后端检测、Python 编译和 `git diff --check`：通过。
- 完整 `tests/ui_backend`：64 passed，1 个既有 `realm_raid` 默认值断言失败（类内 SCRIPT_META 为 30，历史注册表断言为 9）；未在本任务中擅自改变脚本默认行为。
- `tests/common`：131 passed，3 个既有配置接口/OCR/图像查找器失败；与本任务无关。

## Out of scope

- 不引入 React/Tailwind、不实现多客户端并行、跨进程持久化调度服务、从快照自动续跑或复杂日历规则；只实现明确支持的手动/间隔/每日时间触发。
