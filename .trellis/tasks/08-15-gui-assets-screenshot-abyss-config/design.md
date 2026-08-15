# GUI资源、截图与狭间配置增强集成设计

## 1. Responsibility Boundary

父任务没有独立生产代码，只冻结三个子任务之间的契约：

```text
Electron userData
├── image-overrides/ ← 资源子任务 ← 截图裁剪确认替换
└── screenshots/     ← 截图子任务 → run_evidence 关联

狭间 ConfigMeta → 现有 schema/API/GUI → Enemy.target_damage
```

- 资源子任务拥有持久化根传递和资源覆盖 API。
- 截图子任务复用该持久化根与覆盖 API，拥有截图文件、元数据和运行证据触发。
- 狭间配置子任务只走现有 schema 数据流，不依赖前两个子任务。

## 2. Implementation Order

1. `08-15-gui-image-resource-persistence`：先建立 `userData`、动态资源 ID 与原子替换契约。
2. `08-15-gui-game-screenshot`：在资源 API 之上接入 Cropper.js 的“替换当前资源”。
3. `08-15-abyss-deputy-elite-threshold-config`：技术上独立，可在任一时点实现，但最终统一做 GUI/API 打包回归。

父子关系不是隐式依赖系统；上述顺序同时写入各子任务 `implement.md`。

## 3. Cross-Child Contracts

- 唯一持久化根：Electron 传入的 `YYS_USER_DATA_DIR`。
- 唯一资源 ID：资源子任务产生的规范化 `yys/...` POSIX 相对路径。
- 唯一替换入口：无论本地文件还是裁剪 Blob，都调用同一个资源覆盖服务。
- 截图与覆盖是独立副本：删除截图不影响已生效覆盖，恢复默认不删除截图。
- 工具动作不是运行控制动作：截图与资源替换不加入或篡改 `available_actions`。
- 配置键保持原始 snake_case，GUI 不引入脚本专属 camelCase 映射。

## 4. Integration Verification

- 开发模式：API、路径、自动截图序列、Cropper 交互、三阈值配置。
- 打包模式：后端健康、`userData` 传递、本地 Cropper.js、资源/截图库、`/api/scripts`。
- 重装模式：先创建覆盖和截图，再用新安装包覆盖安装，确认文件与元数据仍可用。
- 回归边界：未覆盖图、其他脚本配置、运行控制矩阵、焦点和输入记录不变。

## 5. Rollback

三个子任务均可独立回滚：资源覆盖缺失时退回内置图；截图 UI/服务移除不改变运行控制；狭间字段移除可回到原硬编码默认。父任务不引入额外迁移或全局开关。
