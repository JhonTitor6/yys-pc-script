# 外部项目恢复与人工接管研究

## 研究范围

- 本地结论文档：`docs/2026-08-08-external-project-learning-conclusions.md`
- OnmyojiAutoScript：页面注册、页面导航、回主页、异常调度、重启和公共邀请处理
- Whimbox / whimbox_app：前后端任务状态与桌面端可用操作

## OnmyojiAutoScript 的实际做法

### 可恢复页面问题留在当前任务内

- `Page` 对象同时持有识别条件与到其他页面的显式链接，导航图使用对象引用，避免由文件名分别推导字符串节点。
- `ui_goto()` 为整个导航设置有界超时；路径不存在或跳转后未到目标页时重新识别当前页，再重新计算/执行路径。
- 每一跳先执行动作，再等待目标页出现并更新 `ui_current`，不会仅凭点击成功就推进。
- `GotoMain` 是独立任务：先识别当前页，再导航到主页，最后以 `TaskEnd` 正常结束。

### 未知页面不是无限恢复

- `ui_get_current_page()` 在约 10 秒窗口内遍历所有已注册页面，并尝试关闭白名单弹窗。
- 如果没有匹配到白名单关闭按钮，当前实现还会点击所谓安全随机区域；该行为不符合本项目“未知画面禁止盲点恢复”的边界，不能照搬。
- 超时后抛出 `GamePageUnknownError`，要求用户切换到受支持页面。

### 异常恢复与人工接管分层

- `GamePageUnknownError`、`GameStuckError` 和点击过多会保存错误证据、发通知并调度 `Restart`；它们结束当前任务，不是继续原任务栈。
- 调度器会记录同一任务连续失败次数；达到 3 次后请求人工接管并退出进程。
- 显式 `RequestHumanTakeover` 同样发通知后直接退出，没有“人工处理后恢复同一运行”的实现。
- 因此该项目的语义是：低风险自动恢复可在当前任务中重试；跨过人工接管边界后终结当前任务，由重启或后续人工操作建立新执行上下文。

### 公共突发事件

- 截图入口会检查邀请弹窗，并按全局配置接受、拒绝或忽略。
- 接受邀请后会单独调度 `WantedQuests`，而不是假装当前业务路径未被改变。
- 这支持本项目的保守范围：入口准备阶段只自动执行不会改变目标任务路径的明确动作；接受类动作转人工或新任务。

## Whimbox 的实际做法

- 后端仓库明确只负责 RPC、模型与工具调用，桌面 UI 位于 `whimbox_app`。
- 一条龙页面只监听 `started`、`stopping`、`completed`、`cancelled`、`error`；用户操作只有启动和停止。
- 当前公开前端没有人工接管后恢复同一 task 的状态或操作，因此它只能作为前后端状态分离的参考，不能作为游戏页面恢复语义的依据。

## 对本项目的规划影响

推荐把恢复边界拆成两层：

1. 自动恢复层：同一次运行内重新截图、重新识别、关闭白名单弹窗、等待战斗安全结束、验证后重试导航。
2. 人工接管层：当前运行进入终态 `manual` 并释放执行槽；用户处理后点击“重新识别并重试”，创建一个关联原运行的新 run，从全新截图和状态解析开始。

关联新 run 应保留 `parent_run_id` 或等价来源字段，使 GUI 能串联原失败证据、人工处理和新尝试。不得复用旧 `SceneSnapshot`、旧路径索引或旧动作游标。

## 参考源码

- https://github.com/runhey/OnmyojiAutoScript/blob/master/tasks/GameUi/game_ui.py
- https://github.com/runhey/OnmyojiAutoScript/blob/master/tasks/GameUi/page.py
- https://github.com/runhey/OnmyojiAutoScript/blob/master/tasks/GotoMain/script_task.py
- https://github.com/runhey/OnmyojiAutoScript/blob/master/tasks/Restart/script_task.py
- https://github.com/runhey/OnmyojiAutoScript/blob/master/script.py
- https://github.com/runhey/OnmyojiAutoScript/blob/master/tasks/base_task.py
- https://github.com/nikkigallery/whimbox_app/blob/main/src/renderer/pages/one-dragon-page.tsx
- https://github.com/nikkigallery/Whimbox/blob/main/README.md
