# GUI 视觉基础与应用框架设计

## 1. 边界

本阶段只改应用壳层和视觉基础。页面内部现有 DOM 可在新壳层中暂时保留，避免同时重写所有业务视图。若旧四栏结构阻碍新壳层，可移动节点，但不改变其 ID、数据来源或事件语义。

## 2. 主题实现

- `document.documentElement.dataset.theme` 是 DOM 主题真源。
- `localStorage` 只保存 `light` 或 `dark`；缺失和非法值都归一化为 `light`。
- 在主 CSS 加载前恢复 `data-theme`，避免闪烁。
- `setTheme(theme)` 同时更新 DOM、存储、顶部按钮和设置页未来可复用的控件状态。
- CSS 变量按 surface/text/border/accent/status/focus/space/radius/shadow/motion 分组；组件不新增散落色值。

## 3. 应用壳层

~~~text
.app-shell
├─ .app-nav
└─ .app-column
   ├─ .app-topbar
   └─ .app-content
~~~

- `.app-nav` 展开时显示品牌、图标和文字，折叠时保留图标、Tooltip 和 `aria-label`。
- `.app-topbar` 不复制完整运行控制，只展示连接、任务/状态、查看运行、条件性停止和主题按钮。
- `.app-content` 承载现有各 view；不再为固定右栏预留永久网格列。
- 当前页面状态继续使用既有 view 切换机制，阶段内只统一入口和选中状态。
- 原进度 view 在阶段 1 作为运行页内部兼容子视图保留，由“查看详细进度”进入；阶段 2 完成信息迁移后删除该入口和重复 view。

## 4. 响应式规则

- 800-899：导航强制图标模式；内容单列。
- 900-1099：导航默认展开，可手动折叠；页面内部仍按当前结构兼容。
- ≥1100：导航展开，内容获得更宽工作区。
- 用户折叠偏好可单独持久化，但自动窄屏折叠优先；回到宽屏后恢复用户偏好。

## 5. 图标与动效

- 在现有 HTML 中维护最小 SVG symbol 集合，仅包含导航、主题、连接、返回、停止等实际图标。
- 图标按钮提供可见 Tooltip、`aria-label`、hover/pressed/disabled/focus-visible。
- 只对颜色、背景、边框、opacity、transform 做 160-220ms 过渡；`prefers-reduced-motion` 下禁用非必要过渡。

## 6. 数据流

- 连接状态继续由 `setConnectionStatus` 更新，顶部与运行页消费同一值。
- current run 继续由 REST/WebSocket 更新 `state.currentRun`。
- 顶部停止按钮检查 `available_actions`，调用已有 `controlCurrentRun('stop')`。
- 页面标题来自当前 view 状态，不建立第二套路由。

## 7. 兼容与回滚

- 不修改 API、状态枚举和已有 DOM 事件的业务行为。
- 保留旧页面 ID，直到后续子任务接管对应视图。
- 本阶段独立提交；失败时可整体回滚壳层和主题，不影响后端与运行数据。
