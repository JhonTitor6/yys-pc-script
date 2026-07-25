# 场景跳转前置依赖设计

**日期**：2026-06-25
**状态**：Updated（范围收缩为 3 个稳定入口脚本）
**作者**：Claude + 用户

## 背景与目标

### 痛点

当前 `yys-pc-script` 的工作流编排系统（`SchedulerService` + `workflow_steps` 表）已经支持多脚本顺序执行，但**每个脚本启动前缺少「先到达目标场景」的前置步骤**。典型场景：

1. **探索 30 次 → 结界突破 → 探索 30 次**：脚本 A 跑完时停在探索地图，脚本 B 必须自己处理"如何在结界突破界面登录"。当前各脚本在 `on_run` 开头各自硬编码跳转逻辑，缺少统一抽象。
2. **复用入口路径**：探索脚本需要固定进入已存在的第 28 章入口，避免在多个脚本中重复硬编码路径。
3. **狭间暗域入口不稳定**：当前游戏版本没有稳定的统一入口路径，暂不纳入本次自动入口场景范围。

### 现有资源

- `SceneManager`（`yys/common/scene_manager.py`）：已实现 BFS 寻路和 `goto_scene(target_scene)`，支持细分场景跳转。
- `YYSBaseScript`（`yys/common/event_script_base.py`）：所有具体脚本的基类，初始化时已注入 `self.scene_manager`。
- `SchedulerService.run_step`：当前启动脚本前不做场景校验。
- `workflow_steps` 表 / `WorkflowStepType.RUN_SCRIPT`：数据库和模型已就绪。
- GUI 已有 workflow 编辑 Modal（`gui/index.html` 第 79-110 行）。

### 目标

1. **统一入口场景跳转**：在 YYSBaseScript 层提供"启动前先到达目标场景"的统一调用点。
2. **场景归属脚本**：由 3 个入口稳定的脚本类自己声明目标场景（不存到 workflow 配置），保证"场景和业务耦合"+"编排配置保持简洁"。
3. **不破坏现有架构**：不改数据库、不改 workflow 模型、不改 SchedulerService、不改 GUI。
4. **失败即停止**：跳转失败时脚本不进入主循环，workflow 按现有 `failure_policy` 处理。

## 方案选型

### 决策矩阵

| 维度 | A. workflow 步骤加 target_scene | B. RUN_SCRIPT 字段 target_scene | C. 脚本内硬编码 + YYSBaseScript 封装（采用） |
|------|---------------------------------|----------------------------------|---------------------------------------------|
| 数据库改动 | 需要 | 不需要（步骤 JSON 多一个字段）| **不需要** |
| 编排器耦合业务 | 中 | 中 | **无** |
| 脚本可独立运行 | 需要 target_scene 配置 | 需要 target_scene 配置 | **可以**（声明类属性即可）|
| 多 workflow 复用脚本 | 每个 workflow 都要配 | 同上 | **一次声明，全 workflow 生效** |
| 失败处理粒度 | 编排器统一处理 | 同上 | **脚本层处理 + 编排器兜底** |

### 决策

采用 **方案 C：YYSBaseScript 统一封装 + 脚本类声明 `entry_scene` 类属性**。

理由：
- 场景归属业务：跳转目标是最纯粹的业务信息（"我必须在探索-28 章才能跑"），不属于编排范畴。
- 编排器零耦合：SchedulerService 不知道 scene 的存在，符合单一职责。
- 现有架构最小改动：只改一个文件（`event_script_base.py`），加一个类属性约定；暂不为狭间暗域声明入口。
- GUI 不变：用户在 GUI 编排 workflow 时不感知 scene 概念，编排结果与跳转完全正交。

## 设计

### 1. 数据模型

在 `YYSBaseScript`（`yys/common/event_script_base.py`）新增类属性：

```python
class YYSBaseScript(EventBaseScript, metaclass=_ABCMetaRelaxDel):
    # ... 现有代码 ...

    # 入口场景：脚本启动时必须先到达的场景名。
    # 子类覆盖此属性声明自己需要在哪个场景启动。
    # 为空字符串或 None 时跳过入口跳转（兼容 Kuzunoha 等老脚本）。
    entry_scene: Optional[str] = None
```

子类示例：
```python
class ExplorationScript(YYSBaseScript):
    SCRIPT_META = ScriptMeta(...)
    entry_scene = "exploration_chapter_28"  # ← 新增一行
```

### 2. 执行流程

**注入点**：`YYSBaseScript.run()`（覆盖 `EventBaseScript.run()`，见 `win_util/event.py:227`）。

```python
def run(self) -> None:
    """主循环：先做入口场景跳转，再进入父类的主循环逻辑。"""
    if self.entry_scene:
        self.logger.info(f"执行入口场景跳转: {self.entry_scene}")
        if not self.scene_manager.goto_scene(self.entry_scene):
            self.logger.error(f"入口场景跳转失败，停止脚本: {self.entry_scene}")
            return
    super().run()
```

**流程图**：

```
[Scheduler] run_step
    ↓
[RunManager] start(script)
    ↓
[Script] run()
    ├─ entry_scene 非空？──── 否 → super().run()
    │                          是 ↓
    ├─ SceneManager.goto_scene(entry_scene)
    │      ├─ 成功 → super().run()
    │      └─ 失败 → return（不进主循环，RunManager 检测到未进入 RUNNING → 标记 ERROR）
    ↓
[EventBaseScript] run()
    ├─ on_run()（子类重写：业务初始化）
    └─ 循环：pause_point → before_iteration → 事件触发 → after_iteration
```

### 3. 场景图资产

`yys/common/images/scene/` 目录补充稳定入口所需的场景图：

| 文件 | 描述 |
|------|------|
| `exploration_chapter_28.bmp` | 探索地图，28 章已选中状态 |

`yys/common/images/scene_control/` 目录补充跳转按钮：

| 文件 | 描述 |
|------|------|
| `exploration_to_chapter_28.bmp` | 探索地图上的"第二十八章"入口按钮 |
| `exploration_chapter_28_to_battle.bmp` | 28 章界面上的"探索"按钮（进入战斗）|

狭间暗域相关图片不属于本次入口前置依赖：当前游戏版本中御魂选择界面没有狭间暗域入口，探索地图也没有第 29 章；已有的 `abyss_shadows_entry.bmp` 保留为现有资源，但不作为本方案的自动入口验收项。

**场景图注册**：
场景图通过现有 `SceneManager.register_scenes_from_directory()` 自动加载（`YYSBaseScript.__init__` 已调用，见 `event_script_base.py:201-204`），无需手动注册。

### 4. 错误处理

| 失败点 | 处理方式 |
|--------|----------|
| `goto_scene` 返回 False | `YYSBaseScript.run()` 直接 return，**不进主循环** |
| RunManager 检测脚本未进入 RUNNING | 标记为 `RunStatus.ERROR` |
| workflow 调用 `wait(run_id)` | workflow 按 `failure_policy`（默认 `stop_workflow`）停止 |

**关键不变量**：场景跳转失败 ⟺ 脚本未启动 ⟺ workflow 步骤失败。三个层级语义一致。

### 5. 现有脚本迁移清单

| 脚本类 | entry_scene | 备注 |
|--------|-------------|------|
| `ExplorationScript` | `"exploration_chapter_28"` | 默认 28 章；可由子类或 config 覆盖 |
| `RealmRaidScript` | `"barrier_breakthrough"` | |
| `SoulRaidScript` | `"soul_selection"` | |
| `Main`（狭间暗域） | `None` | 当前版本没有稳定统一入口，本次不纳入 |
| `KuzunohaScript` | `""`（默认）| 老脚本，保持兼容 |

**注意**：`ExplorationScript` 的章节由 `entry_scene` 固定为第 28 章。如果未来要支持运行时选择章节，需要让 `entry_scene` 由 `config.chapter` 派生（不在本 spec 范围）。

### 6. 与现有架构的兼容

| 组件 | 是否改动 | 理由 |
|------|----------|------|
| `workflow_steps` 数据库表 | 否 | 跳转是脚本内部细节，不属于编排配置 |
| `WorkflowStepType` 枚举 | 否 | 跳转不是独立 step 类型 |
| `SchedulerService` | 否 | 编排器对 scene 无感知 |
| `RunManager` | 否 | 启动流程不变 |
| `SceneManager` | 否 | 复用现有 BFS 寻路和 goto_scene |
| GUI（`gui/index.html`、`gui/renderer.js`）| 否 | workflow 编辑界面不感知 scene |
| `YYSBaseScript` | **是** | 新增 1 个类属性 + 1 个 run 覆盖方法 |

## 测试策略

### 单元测试（不需要游戏窗口）

文件：`tests/common/test_scene_transition_entry.py`（新建）

```python
def test_yys_base_script_runs_goto_scene_when_entry_scene_set():
    """验证 entry_scene 非空时，run() 入口会调 SceneManager.goto_scene。"""
    # 构造 MockEnvironment，验证 goto_scene 被调用且参数正确
    # 验证 goto_scene 返回 False 时 run() 不进入主循环

def test_yys_base_script_skips_goto_scene_when_entry_scene_empty():
    """验证 entry_scene 为空字符串时，跳过跳转直接 super().run()。"""

def test_yys_base_script_stops_when_goto_scene_fails():
    """验证 goto_scene 失败时，脚本不进入主循环，stop 事件被设置。"""
```

### 集成测试（场景重放）

文件：`yys/exploration/test_exploration_scene_transition.py`（新建）

```python
def test_exploration_full_flow_with_entry_scene():
    """探索脚本完整流程：home → exploration → chapter_28 → battle → ... → stop。"""
    # 使用 SceneReplayEnvironment 加载真实场景截图
    # 验证 entry_scene="exploration_chapter_28" 时进入副本
```

### 回归测试

确认探索、结界突破和御魂脚本的入口声明测试通过；狭间暗域继续保持 `entry_scene=None`，其现有业务测试不作为本次入口前置依赖的验收条件。

## 实施步骤

| Step | 任务 | 验证标准 |
|------|------|----------|
| 1 | 在 `YYSBaseScript` 加 `entry_scene: str = ""` 类属性 | 现有所有脚本不破坏 |
| 2 | 在 `YYSBaseScript.run()` 注入入口跳转逻辑 | 单元测试验证调和不调两种情况 |
| 3 | 补充第 28 章场景图和跳转按钮图（`scene/` 和 `scene_control/` 目录）| 视觉检查（人工）|
| 4 | 给 3 个稳定入口脚本类加 `entry_scene` 类属性 | 单元测试通过 |
| 5 | 新增单元测试和集成测试 | 全部测试通过 |

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| SceneManager BFS 找不到路径 | goto_scene 返回 False，run() 直接 return，工作流停止（人介入）|
| 场景图识别失败 | 现有 BFS 已有重试机制（`scene_manager.py:344-353`），行为一致 |
| 老脚本（Kuzunoha）兼容性 | `entry_scene = ""` 默认值，兼容现有调用 |
| 狭间暗域入口不稳定 | `Main` 保持 `entry_scene=None`，未来单独设计真实入口路径 |
| 跳转动画耗时 | 复用现有 `time.sleep(3.0)`（`scene_manager.py:338`） |

## 未来扩展

本 spec 不涉及，但为后续扩展预留：

1. **场景依赖继承**：脚本 B 可声明"依赖脚本 A 的 exit_scene"，自动接续
2. **场景图谱可视化**：前端展示 SceneManager 的有向图
3. **运行时场景切换**：配置变更时自动重新跳转
4. **章节参数化**：`ExplorationScript.entry_scene` 由 `config.chapter` 派生，支持 GUI 选章节
