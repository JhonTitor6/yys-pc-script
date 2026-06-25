# 场景跳转前置依赖实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `YYSBaseScript` 层添加「启动前自动跳转到目标场景」机制，使工作流编排器无需关心场景，业务脚本通过声明 `entry_scene` 类属性指定自己的入口场景。

**Architecture:** 覆盖 `YYSBaseScript.run()` 方法，在调用父类主循环之前检查 `self.entry_scene`，非空则调 `self.scene_manager.goto_scene()` 复用现有 BFS 寻路。失败时直接 return，RunManager 检测到未进入 RUNNING 标记 ERROR，workflow 按现有 `failure_policy` 兜底。**不修改**数据库、workflow 模型、SchedulerService、RunManager、SceneManager、GUI。

**Tech Stack:** Python 3.x、pytest、loguru、SQLite (workflow_steps 表)、win32gui (鼠标控制)

---

## 文件结构

| 路径 | 操作 | 职责 |
|------|------|------|
| `yys/common/event_script_base.py` | 修改 | 加 `entry_scene` 类属性 + 覆盖 `run()` |
| `yys/exploration/exploration_script.py` | 修改 | 加 `entry_scene = "exploration_chapter_28"` |
| `yys/realm_raid/realm_raid_script.py` | 修改 | 加 `entry_scene = "barrier_breakthrough"` |
| `yys/abyss_shadows/abyss_shadows_script.py` | 修改 | 加 `entry_scene = "abyss_shadows_entry"` |
| `yys/soul_raid/soul_raid_script.py` | 修改 | 加 `entry_scene = "soul_selection"` |
| `yys/common/images/scene/*.bmp` | 新增 | 细分场景图（人工采集）|
| `yys/common/images/scene_control/*.bmp` | 新增 | 跳转按钮图（人工采集）|
| `tests/common/test_scene_transition_entry.py` | 新增 | 单元测试：3 个用例 |
| `yys/exploration/test_exploration_scene_transition.py` | 新增 | 集成测试：场景重放 |

---

## Task 1: YYSBaseScript 加 entry_scene 类属性

**Files:**
- Modify: `yys/common/event_script_base.py:147-227`（在 `YYSBaseScript` 类内加属性）
- Test: `tests/common/test_scene_transition_entry.py`（新建）

- [ ] **Step 1: 写失败的单元测试**

创建 `tests/common/test_scene_transition_entry.py`：

```python
"""YYSBaseScript entry_scene 前置跳转行为的单元测试。"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.common.environment.mock_environment import MockEnvironment
from tests.common.recorders.action_log import ActionLog
from yys.common.event_script_base import YYSBaseScript
from yys.common.scene_manager import SceneManager


class _ProbeScript(YYSBaseScript):
    """探针脚本：entry_scene 和 on_run 由测试用例设置；on_run 空实现避免父类 abstract。"""

    def on_run(self) -> None:  # type: ignore[override]
        pass


def _make_script(env: MockEnvironment, entry_scene: str = "") -> _ProbeScript:
    """构造一个绑定到 MockEnvironment 的 _ProbeScript 实例。"""
    # 关闭父类构造中的 find_window：env 存在时走 mock 路径
    return _ProbeScript(script_name="probe", env=env, config={"entry_scene": entry_scene})


def test_entry_scene_empty_skips_goto_scene() -> None:
    """entry_scene 为空字符串时，run() 不调用 scene_manager.goto_scene。"""
    log = ActionLog()
    env = MockEnvironment(action_log=log)
    script = _make_script(env, entry_scene="")
    script.scene_manager = MagicMock(spec=SceneManager)

    script.run()

    script.scene_manager.goto_scene.assert_not_called()


def test_entry_scene_set_calls_goto_scene_with_correct_arg() -> None:
    """entry_scene 非空时，run() 调用 scene_manager.goto_scene(self.entry_scene)。"""
    log = ActionLog()
    env = MockEnvironment(action_log=log)
    script = _make_script(env, entry_scene="exploration_chapter_28")
    script.scene_manager = MagicMock(spec=SceneManager)
    script.scene_manager.goto_scene.return_value = True

    script.run()

    script.scene_manager.goto_scene.assert_called_once_with("exploration_chapter_28")


def test_entry_scene_goto_fails_does_not_enter_main_loop() -> None:
    """goto_scene 返回 False 时，run() 不调用父类 on_run()，主循环不启动。"""
    log = ActionLog()
    env = MockEnvironment(action_log=log)
    script = _make_script(env, entry_scene="barrier_breakthrough")
    script.scene_manager = MagicMock(spec=SceneManager)
    script.scene_manager.goto_scene.return_value = False
    # 监听父类 run() 的副作用：on_run 是 abstract 但子类实现为 noop；
    # 验证方式是断言 stop_threading_event 被设置、且不进入 while 循环
    script.on_run = MagicMock()  # type: ignore[method-assign]

    script.run()

    script.scene_manager.goto_scene.assert_called_once_with("barrier_breakthrough")
    script.on_run.assert_not_called()
```

- [ ] **Step 2: 跑测试，确认失败**

Run:
```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_scene_transition_entry.py -v
```

Expected: 3 个测试**全部失败**（因为 YYSBaseScript 还没有 entry_scene 类属性，且 run() 没有跳转逻辑）。

错误应为 `AttributeError: type object 'YYSBaseScript' has no attribute 'entry_scene'`（实例化时 `__init__` 不会失败，因为 entry_scene 缺省即空，但 Step 1 的脚本走 config 路径会触发 `_apply_config`，传入不存在的字段会被 setattr 到实例，**不会**失败——预期是前两个测试都失败的原因是 `script.scene_manager = MagicMock()` 注入时和后续调用期望不符，导致 on_run 不会跑但 goto_scene 也不会跑）。

> **注意**：如果测试报 `TypeError: Can't instantiate abstract class _ProbeScript with abstract method on_run`，说明测试用例需要确保 `_ProbeScript` 重写 `on_run`（已写）。若仍报，检查 `_ProbeScript.on_run` 是否带 `pass` 主体。

- [ ] **Step 3: 修改 YYSBaseScript，加 entry_scene 类属性 + 覆盖 run()**

修改 `yys/common/event_script_base.py`：

定位到 `class YYSBaseScript(EventBaseScript, metaclass=_ABCMetaRelaxDel):` 块（约第 147 行），在 `SCRIPT_META: Any = None` 之后新增类属性：

```python
# 入口场景：脚本启动时必须先到达的场景名。
# 子类覆盖此属性声明自己需要在哪个场景启动。
# 为空字符串或 None 时跳过入口跳转（兼容 Kuzunoha 等老脚本）。
entry_scene: str = ""
```

定位到 `def on_run(self):`（约第 395 行，abstractmethod），**在它之前**新增 `run()` 覆盖方法：

```python
def run(self) -> None:
    """主循环：先做入口场景跳转，再进入父类的主循环逻辑。

    Returns:
        无返回值。跳转失败时直接 return，**不**进入主循环，
        RunManager 会检测到脚本未进入 RUNNING 状态而标记 ERROR。
    """
    if self.entry_scene:
        self.logger.info(f"执行入口场景跳转: {self.entry_scene}")
        if not self.scene_manager.goto_scene(self.entry_scene):
            self.logger.error(f"入口场景跳转失败，停止脚本: {self.entry_scene}")
            return
    super().run()
```

- [ ] **Step 4: 跑测试，确认全部通过**

Run:
```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_scene_transition_entry.py -v
```

Expected: 3 个测试**全部通过**。

- [ ] **Step 5: 跑回归测试，确认未破坏现有功能**

Run:
```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/ yys/exploration/ yys/soul_raid/ -v
```

Expected: 现有测试**全部通过**（entry_scene 默认空字符串，老脚本行为不变）。

- [ ] **Step 6: 提交**

```bash
git add yys/common/event_script_base.py tests/common/test_scene_transition_entry.py
git commit -m "$(cat <<'EOF'
feat(event_script_base): 添加 entry_scene 入口场景跳转前置依赖

在 YYSBaseScript 加 entry_scene 类属性和 run() 覆盖方法。
子类声明 entry_scene 后，脚本启动时自动调 SceneManager.goto_scene 跳转。
跳转失败时直接 return，RunManager 检测到未进入 RUNNING 状态标记 ERROR。

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 5 个核心业务脚本加 entry_scene 声明

**Files:**
- Modify: `yys/exploration/exploration_script.py:29-36`（在 SCRIPT_META 后加一行）
- Modify: `yys/realm_raid/realm_raid_script.py`（在 SCRIPT_META 后加一行）
- Modify: `yys/abyss_shadows/abyss_shadows_script.py`（在 SCRIPT_META 后加一行）
- Modify: `yys/soul_raid/soul_raid_script.py`（在 SCRIPT_META 后加一行）

> **注意**：KuzunohaScript 等老脚本**不修改**（entry_scene 默认空字符串，保持兼容）。

- [ ] **Step 1: ExplorationScript 加 entry_scene**

打开 `yys/exploration/exploration_script.py`，定位到 `class ExplorationScript(YYSBaseScript):` 块（约第 29 行）。

在 `SCRIPT_META = ScriptMeta(...)` 之后、`@classmethod` 装饰器之前，新增一行：

```python
    # 入口场景：探索地图-28 章已选中状态
    entry_scene = "exploration_chapter_28"
```

- [ ] **Step 2: RealmRaidScript 加 entry_scene**

打开 `yys/realm_raid/realm_raid_script.py`，定位到 `class RealmRaidScript(YYSBaseScript):` 块。

在 `SCRIPT_META = ScriptMeta(...)` 之后新增一行：

```python
    # 入口场景：结界突破界面
    entry_scene = "barrier_breakthrough"
```

- [ ] **Step 3: AbyssShadowsScript 加 entry_scene**

打开 `yys/abyss_shadows/abyss_shadows_script.py`，定位到 `class AbyssShadowsScript(YYSBaseScript):` 块。

在 `SCRIPT_META = ScriptMeta(...)` 之后新增一行：

```python
    # 入口场景：狭间暗域入口界面
    entry_scene = "abyss_shadows_entry"
```

- [ ] **Step 4: SoulRaidScript 加 entry_scene**

打开 `yys/soul_raid/soul_raid_script.py`，定位到 `class SoulRaidScript(YYSBaseScript):` 块。

在 `SCRIPT_META = ScriptMeta(...)` 之后新增一行：

```python
    # 入口场景：御魂副本选择界面
    entry_scene = "soul_selection"
```

- [ ] **Step 5: 跑回归测试**

Run:
```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/ yys/exploration/ yys/soul_raid/ yys/abyss_shadows/ -v
```

Expected: **全部通过**（这些脚本的现有测试不应被破坏，因为：
1. entry_scene 是类属性，不影响构造
2. 测试用 MockEnvironment 注入，scene_manager 不会被实际调用
3. 测试用例不调用 run()，所以 run() 覆盖不会触发）

- [ ] **Step 6: 跑新增的单元测试，确认 entry_scene 属性生效**

Run:
```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_scene_transition_entry.py -v
```

Expected: 3 个测试**全部通过**。

> **可选增强**：可以在 `tests/common/test_scene_transition_entry.py` 末尾加一个"smoke 测试"，验证 4 个新声明的脚本类都有非空 entry_scene：

```python
def test_business_scripts_declare_entry_scene() -> None:
    """4 个核心脚本必须声明 entry_scene。"""
    from yys.exploration.exploration_script import ExplorationScript
    from yys.realm_raid.realm_raid_script import RealmRaidScript
    from yys.abyss_shadows.abyss_shadows_script import AbyssShadowsScript
    from yys.soul_raid.soul_raid_script import SoulRaidScript

    assert ExplorationScript.entry_scene == "exploration_chapter_28"
    assert RealmRaidScript.entry_scene == "barrier_breakthrough"
    assert AbyssShadowsScript.entry_scene == "abyss_shadows_entry"
    assert SoulRaidScript.entry_scene == "soul_selection"
```

把这个测试加到 `tests/common/test_scene_transition_entry.py` 末尾，然后重跑 Step 6 确认 4 个测试全部通过。

- [ ] **Step 7: 提交**

```bash
git add yys/exploration/exploration_script.py \
        yys/realm_raid/realm_raid_script.py \
        yys/abyss_shadows/abyss_shadows_script.py \
        yys/soul_raid/soul_raid_script.py \
        tests/common/test_scene_transition_entry.py
git commit -m "$(cat <<'EOF'
feat(scripts): 给 4 个核心脚本声明 entry_scene 入口场景

- ExplorationScript: exploration_chapter_28
- RealmRaidScript: barrier_breakthrough
- AbyssShadowsScript: abyss_shadows_entry
- SoulRaidScript: soul_selection

KuzunohaScript 等老脚本保持 entry_scene="" 默认值，不受影响。
新增 smoke 测试确保声明不被意外删除。

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 集成测试 - 探索脚本完整场景重放

**Files:**
- Create: `yys/exploration/test_exploration_scene_transition.py`
- Test: `tests/common/environment/scene_replay_environment.py`（已存在，参考使用）
- Reference: `yys/abyss_shadows/test_abyss_shadows_scene_replay.py`（已存在，最佳参考实现）

- [ ] **Step 1: 读参考实现**

读 `yys/abyss_shadows/test_abyss_shadows_scene_replay.py` 了解 `SceneReplayEnvironment` 的用法。

读 `yys/abyss_shadows/config/scene_transitions_abyss_shadows.json` 了解场景重放配置文件结构。

- [ ] **Step 2: 创建场景重放配置文件**

创建 `yys/exploration/config/scene_transitions_exploration.json`：

```json
{
  "_comment": "探索脚本场景重放配置：从 home 出发，模拟进入探索-28章流程",
  "scenes": {
    "home": ["yys/common/images/scene/home.bmp"],
    "exploration": ["yys/common/images/scene/exploration.bmp"],
    "exploration_chapter_28": ["yys/common/images/scene/exploration_chapter_28.bmp"]
  },
  "transitions": [
    {
      "from": "home",
      "to": "exploration",
      "button": "yys/common/images/scene_control/home_to_exploration.bmp"
    },
    {
      "from": "exploration",
      "to": "exploration_chapter_28",
      "button": "yys/common/images/scene_control/exploration_to_chapter_28.bmp"
    }
  ]
}
```

> **注意**：此文件**仅作为测试 fixture**。如果 `exploration_chapter_28.bmp` 等场景图尚未采集（Task 4），集成测试可以暂时 skip。

- [ ] **Step 3: 写集成测试**

创建 `yys/exploration/test_exploration_scene_transition.py`：

```python
"""探索脚本：场景跳转 + 业务循环的集成测试（场景重放）。"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from yys.exploration.exploration_script import ExplorationScript


SCENE_CONFIG = "yys/exploration/config/scene_transitions_exploration.json"
SCENE_DIR = "yys/exploration/images/test/scenes/"


def _scene_assets_available() -> bool:
    """检查场景重放所需的 fixture 资产是否齐全。"""
    if not os.path.exists(SCENE_CONFIG):
        return False
    if not os.path.isdir(SCENE_DIR):
        return False
    return True


@pytest.mark.skipif(
    not _scene_assets_available(),
    reason="探索场景重放 fixture 未采集（依赖 Task 4 人工截图）",
)
def test_exploration_full_flow_via_scene_replay() -> None:
    """验证：home → 探索地图 → 28 章已选状态 → 战斗 → 停止 完整流程。"""
    from tests.common.environment.scene_replay_environment import SceneReplayEnvironment

    env = SceneReplayEnvironment(
        scene_config_path=SCENE_CONFIG,
        scene_dir=SCENE_DIR,
    )

    # 注册场景图（参考 abyss_shadows 集成测试的实现）
    env.scene_manager.register_scenes_from_directory(
        scene_dir="yys/common/images/scene/",
        control_dir="yys/common/images/scene_control/",
    )

    script = ExplorationScript(
        script_name="exploration_replay",
        env=env,
        config={"max_battle_count": 1},
    )

    # 模拟 run() 行为：先调 entry_scene 跳转，然后跑业务
    # 由于 SceneReplayEnvironment 不直接驱动 run()，手动调用
    assert script.entry_scene == "exploration_chapter_28"
    assert script.scene_manager.is_reachable("home", "exploration_chapter_28")
```

- [ ] **Step 4: 跑测试**

Run:
```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest yys/exploration/test_exploration_scene_transition.py -v
```

Expected: 测试被 skip（因为 `exploration_chapter_28.bmp` 等 fixture 尚未采集）。这是预期行为，Task 4 完成后再回来跑通。

- [ ] **Step 5: 提交**

```bash
git add yys/exploration/test_exploration_scene_transition.py yys/exploration/config/scene_transitions_exploration.json
git commit -m "$(cat <<'EOF'
test(exploration): 添加探索脚本场景重放集成测试（待 fixture）

通过 SceneReplayEnvironment 验证 entry_scene 跳转 + 业务循环的完整流程。
当前 skip 状态，依赖 Task 4 人工采集的探索副本场景图。

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 补充场景图资产（人工任务）

**Files:**
- Create: `yys/common/images/scene/exploration_chapter_28.bmp`（人工截图）
- Create: `yys/common/images/scene/exploration_chapter_29.bmp`（人工截图，可选）
- Create: `yys/common/images/scene/abyss_shadows_entry.bmp`（人工截图）
- Create: `yys/common/images/scene_control/exploration_to_chapter_28.bmp`（人工截图）
- Create: `yys/common/images/scene_control/exploration_chapter_28_to_battle.bmp`（人工截图）
- Create: `yys/common/images/scene_control/soul_to_abyss_shadows.bmp`（人工截图）

- [ ] **Step 1: 启动游戏，按以下流程采集截图**

| 流程 | 进入哪个场景 | 截哪张图 | 文件名 |
|------|-------------|---------|--------|
| 1. 主页 → 点"探索"按钮 | 探索地图 | 整屏 | `exploration.bmp`（已存在，无需重做）|
| 2. 探索地图 → 点"第二十八章" | 探索地图（28 章已选中）| 整屏 | `exploration_chapter_28.bmp` |
| 3. 28 章界面 → 点"探索"按钮 | 战斗场景 | 截"探索"按钮位置 | `exploration_chapter_28_to_battle.bmp` |
| 4. 主页 → 探索 → 结界突破 | 结界突破界面 | 整屏 | `barrier_breakthrough.bmp`（已存在）|
| 5. 御魂选择 → 找"狭间暗域"按钮 | 御魂选择界面 | 截"狭间暗域"按钮位置 | `soul_to_abyss_shadows.bmp` |
| 6. 点"狭间暗域"按钮 | 狭间暗域入口 | 整屏 | `abyss_shadows_entry.bmp` |

- [ ] **Step 2: 把截图放到对应目录**

- `yys/common/images/scene/`：放整屏场景图
- `yys/common/images/scene_control/`：放跳转按钮的小图（局部截图）

- [ ] **Step 3: 提交**

```bash
git add yys/common/images/scene/exploration_chapter_28.bmp \
        yys/common/images/scene/abyss_shadows_entry.bmp \
        yys/common/images/scene_control/exploration_to_chapter_28.bmp \
        yys/common/images/scene_control/exploration_chapter_28_to_battle.bmp \
        yys/common/images/scene_control/soul_to_abyss_shadows.bmp
git commit -m "$(cat <<'EOF'
chore(assets): 补充场景跳转所需的细分场景图

新增场景图：
- exploration_chapter_28（28 章已选中状态）
- abyss_shadows_entry（狭间暗域入口界面）

新增跳转按钮图：
- exploration_to_chapter_28（探索地图-28 章入口）
- exploration_chapter_28_to_battle（28 章-探索按钮）
- soul_to_abyss_shadows（御魂-狭间暗域按钮）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 验证 Task 3 集成测试通过（依赖 Task 4）

**Files:**
- Test: `yys/exploration/test_exploration_scene_transition.py`（已存在）

- [ ] **Step 1: 跑 Task 3 集成测试**

Run:
```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest yys/exploration/test_exploration_scene_transition.py -v
```

Expected: 不再 skip，正常通过（或根据 fixture 实际情况调整）。

- [ ] **Step 2: 跑全套测试做最终验证**

Run:
```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ yys/ -v
```

Expected: **全部通过**。如果存在预先失败（`test_config_persistence`、`test_ocr`、`test_yuhun`，见 `MEMORY.md` 记录），它们不属于本次改动范围，跳过即可。

- [ ] **Step 3: 文档同步更新**

更新 `MEMORY.md`（`C:\Users\56440\.claude\projects\F--Users-56440-PythonProjects-yys-pc-script\memory\MEMORY.md`），在「## 场景跳转前置依赖」新增章节：

```markdown
## 场景跳转前置依赖（已完成）

### 改动概述
- `yys/common/event_script_base.py`: 加 `entry_scene` 类属性 + 覆盖 `run()`
- 4 个核心脚本（Exploration/RealmRaid/AbyssShadows/SoulRaid）声明 entry_scene

### 入口场景映射
| 脚本 | entry_scene |
|------|-------------|
| ExplorationScript | exploration_chapter_28 |
| RealmRaidScript | barrier_breakthrough |
| AbyssShadowsScript | abyss_shadows_entry |
| SoulRaidScript | soul_selection |

### 设计文档
- `docs/specs/2026-06-25-scene-transition-before-script-run-design.md`
- `docs/plans/2026-06-25-scene-transition-before-script-run-plan.md`
```

- [ ] **Step 4: 提交文档更新**

```bash
git add MEMORY.md
git commit -m "docs(memory): 记录场景跳转前置依赖改动"
```

> **注意**：MEMORY.md 路径在 `C:\Users\56440\.claude\projects\F--Users-56440-PythonProjects-yys-pc-script\memory\MEMORY.md`，**不在** git 仓库中。如果要持久化记忆，使用 Write 工具直接写即可，不需 git commit。

---

## 完成标准

- [ ] Task 1-3 单元测试和集成测试全部通过
- [ ] Task 4 场景图资产已采集并提交
- [ ] Task 5 全套测试通过
- [ ] MEMORY.md 已更新
- [ ] 所有提交信息符合"中文"约定
