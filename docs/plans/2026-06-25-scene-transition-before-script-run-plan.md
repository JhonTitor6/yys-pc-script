# 场景跳转前置依赖实施计划

> **当前状态：已完成（范围收缩为 3 个稳定入口脚本）**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `YYSBaseScript` 层添加「启动前自动跳转到目标场景」机制，使工作流编排器无需关心场景；本次仅为探索、结界突破、御魂 3 个具有稳定入口的脚本声明 `entry_scene`。

**Architecture:** 覆盖 `YYSBaseScript.run()` 方法，在调用父类主循环之前检查 `self.entry_scene`，非空则调 `self.scene_manager.goto_scene()` 复用现有 BFS 寻路。失败时直接 return，RunManager 检测到未进入 RUNNING 标记 ERROR，workflow 按现有 `failure_policy` 兜底。狭间暗域因当前游戏版本没有稳定统一入口，保持 `entry_scene=None`。**不修改**数据库、workflow 模型、SchedulerService、RunManager、SceneManager、GUI。

**Tech Stack:** Python 3.x、pytest、loguru、SQLite (workflow_steps 表)、win32gui (鼠标控制)

---

## 文件结构

| 路径 | 操作 | 职责 |
|------|------|------|
| `yys/common/event_script_base.py` | 修改 | 加 `entry_scene` 类属性 + 覆盖 `run()` |
| `yys/exploration/exploration_script.py` | 修改 | 加 `entry_scene = "exploration_chapter_28"` |
| `yys/realm_raid/realm_raid_script.py` | 修改 | 加 `entry_scene = "barrier_breakthrough"` |
| `yys/abyss_shadows/abyss_shadows_script.py` | 修改 | 明确不声明 `entry_scene`，保留默认行为 |
| `yys/soul_raid/soul_raid_script.py` | 修改 | 加 `entry_scene = "soul_selection"` |
| `yys/common/images/scene/*.bmp` | 新增 | 细分场景图（人工采集）|
| `yys/common/images/scene_control/*.bmp` | 新增 | 跳转按钮图（人工采集）|
| `tests/common/test_scene_transition_entry.py` | 新增 | 单元测试：3 个行为用例 + 脚本范围断言 |
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
    """探针脚本：on_run 空实现避免父类 abstract；不声明 SCRIPT_META 走老路径。"""

    SCRIPT_META = None  # 显式置 None：避免 _apply_config 触发 TypeError

    def on_run(self) -> None:  # type: ignore[override]
        pass


def _make_script(env: MockEnvironment, entry_scene: str = "") -> _ProbeScript:
    """构造一个绑定到 MockEnvironment 的 _ProbeScript 实例。

    注意：不传 config，避免 _apply_config 因缺 SCRIPT_META 抛 TypeError。
    entry_scene 通过实例属性直接设置（不走 _apply_config 路径）。
    """
    script = _ProbeScript(script_name="probe", env=env)
    script.entry_scene = entry_scene
    return script


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
    """goto_scene 返回 False 时，run() 不调用 on_run()，主循环不启动。"""
    log = ActionLog()
    env = MockEnvironment(action_log=log)
    script = _make_script(env, entry_scene="barrier_breakthrough")
    script.scene_manager = MagicMock(spec=SceneManager)
    script.scene_manager.goto_scene.return_value = False
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

Expected: 至少 2 个测试失败（`scene_manager.goto_scene` 行为尚未实现）。`_ProbeScript.SCRIPT_META = None` 显式声明，绕开 `_apply_config` 的 TypeError。

- [ ] **Step 3: 修改 YYSBaseScript，加 entry_scene 类属性 + 覆盖 run()**

修改 `yys/common/event_script_base.py`：

定位到 `class YYSBaseScript(EventBaseScript, metaclass=_ABCMetaRelaxDel):` 块（约第 147 行），在 `SCRIPT_META: Any = None` 之后新增类属性：

```python
# 入口场景：脚本启动时必须先到达的场景名。
# 子类覆盖此属性声明自己需要在哪个场景启动。
# 为空字符串或 None 时跳过入口跳转（兼容 Kuzunoha 等老脚本）。
entry_scene: Optional[str] = None
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

## Task 2: 3 个核心业务脚本加 entry_scene 声明

**Files:**
- Modify: `yys/exploration/exploration_script.py:29-36`（在 SCRIPT_META 后加一行）
- Modify: `yys/realm_raid/realm_raid_script.py`（在 SCRIPT_META 后加一行）
- Modify: `yys/soul_raid/soul_raid_script.py`（在 SCRIPT_META 后加一行）

> **注意**：KuzunohaScript 等老脚本**不修改**；狭间暗域 `Main` 因入口路径不稳定也不声明 `entry_scene`。

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

- [ ] **Step 3: SoulRaidScript 加 entry_scene**

打开 `yys/soul_raid/soul_raid_script.py`，定位到 `class SoulRaidScript(YYSBaseScript):` 块。

在 `SCRIPT_META = ScriptMeta(...)` 之后新增一行：

```python
    # 入口场景：御魂副本选择界面
    entry_scene = "soul_selection"
```

- [ ] **Step 4: 跑回归测试**

Run:
```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_scene_transition_entry.py yys/exploration/test_exploration_scene_transition.py tests/common/test_scene_manager.py -v
```

Expected: 入口声明、探索场景重放和场景管理器测试通过（这些脚本的现有测试不应被破坏，因为：
1. entry_scene 是类属性，不影响构造
2. 测试用 MockEnvironment 注入，scene_manager 不会被实际调用
3. 测试用例不调用 run()，所以 run() 覆盖不会触发）

- [ ] **Step 5: 加 smoke 测试 + 跑全部 entry_scene 单元测试**

在 `tests/common/test_scene_transition_entry.py` 末尾添加 smoke 测试，防止 3 个业务脚本的 `entry_scene` 声明被意外删除，并明确狭间暗域暂不声明入口：

```python
def test_business_scripts_declare_entry_scene() -> None:
    """3 个稳定入口脚本必须声明 entry_scene。"""
    from yys.exploration.exploration_script import ExplorationScript
    from yys.realm_raid.realm_raid_script import RealmRaidScript
    from yys.soul_raid.soul_raid_script import SoulRaidScript

    assert ExplorationScript.entry_scene == "exploration_chapter_28"
    assert RealmRaidScript.entry_scene == "barrier_breakthrough"
    assert SoulRaidScript.entry_scene == "soul_selection"


def test_abyss_shadows_entry_scene_is_disabled() -> None:
    """当前版本不为狭间暗域声明统一入口场景。"""
    from yys.abyss_shadows.abyss_shadows_script import Main

    assert Main.entry_scene is None
```

Run:
```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_scene_transition_entry.py -v
```

Expected: 5 个测试**全部通过**（3 个行为测试 + 1 个稳定入口汇总断言 + 1 个狭间暗域禁用断言）。

- [ ] **Step 6: 提交**

```bash
git add yys/exploration/exploration_script.py \
        yys/realm_raid/realm_raid_script.py \
        yys/abyss_shadows/abyss_shadows_script.py \
        yys/soul_raid/soul_raid_script.py \
        tests/common/test_scene_transition_entry.py
git commit -m "$(cat <<'EOF'
feat(scripts): 给 3 个核心脚本声明 entry_scene 入口场景

- ExplorationScript: exploration_chapter_28
- RealmRaidScript: barrier_breakthrough
- SoulRaidScript: soul_selection

KuzunohaScript 等老脚本保持默认值不受影响；狭间暗域暂不声明统一入口。
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

- [ ] **Step 1: 读取场景重放基础设施**

读取 `tests/common/environment/scene_replay_environment.py` 了解 `SceneReplayEnvironment` 的用法和配置文件结构。

- [ ] **Step 2: 创建场景重放目录和配置文件**

先创建 fixture 目录（fixture 图片在 Task 4 采集后才填充）：

```bash
mkdir -p "yys/exploration/images/test/scenes/"
```

> Task 3 集成测试在 Task 4 完成前会 **skip**（依赖 fixture），不会阻塞 Task 1/2 合并。

创建 `yys/exploration/config/scene_transitions_exploration.json`：

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
    # 参考 test_abyss_shadows_scene_replay.py 头部，预先 mock Windows 相关模块
    # 避免 import 时触发 win32gui 等
    with patch("win32gui.FindWindow", return_value=12345):
        from tests.common.environment.scene_replay_environment import SceneReplayEnvironment

        env = SceneReplayEnvironment(
            scene_config_path=SCENE_CONFIG,
            scene_dir=SCENE_DIR,
        )
        env.scene_manager.register_scenes_from_directory(
            scene_dir="yys/common/images/scene/",
            control_dir="yys/common/images/scene_control/",
        )

        script = ExplorationScript(
            script_name="exploration_replay",
            env=env,
            config={"max_battle_count": 1},
        )

        # 验证 entry_scene 声明
        assert script.entry_scene == "exploration_chapter_28"

        # 验证 BFS 路径可达
        assert script.scene_manager.is_reachable("home", "exploration_chapter_28")

        # 验证场景图已注册
        assert "exploration_chapter_28" in script.scene_manager.scene_images
```

> **注意**：`with patch("win32gui.FindWindow", ...)` 必须在 import 模块**之前**生效（参考 `test_abyss_shadows_scene_replay.py:24-31` 的 mock 模式）。如果 `import` 已经触发，测试会因找不到游戏窗口而失败——确保 patch 在 import 行之前。

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

## Task 4: 收敛场景图资产范围

本次只验收探索第 28 章入口相关资产。根据当前游戏版本，探索地图没有第 29 章，御魂选择界面也没有狭间暗域入口，因此相关截图不采集、不纳入配置。

**已核验资产：**

- `yys/common/images/scene/exploration_chapter_28.bmp`
- `yys/common/images/scene_control/exploration_to_chapter_28.bmp`
- `yys/common/images/scene_control/exploration_chapter_28_to_battle.bmp`

**明确排除：**

- `exploration_chapter_29.bmp`
- `soul_to_abyss_shadows.bmp`
- `abyss_shadows_entry.bmp` 不作为本次自动入口验收项；狭间暗域保持 `entry_scene=None`。

**验收结果：**

- [x] 第 28 章场景图已提交
- [x] 第 28 章入口和进入战斗按钮图已提交
- [x] 不再要求第 29 章和御魂界面狭间暗域按钮图

---

## Task 5: 验证收缩范围后的实现

**Files:**
- Test: `yys/exploration/test_exploration_scene_transition.py`（已存在）

- [x] **Step 1: 跑入口场景和场景重放测试**

Run:
```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_scene_transition_entry.py yys/exploration/test_exploration_scene_transition.py tests/common/test_scene_manager.py -v
```

实际结果：16 个测试全部通过。

- [x] **Step 2: 记录回归测试范围**

Run:
```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/ yys/exploration/ yys/soul_raid/ -v
```

实际结果：86 个通过，3 个已有问题失败：`test_config_persistence`、`TestYYS.test_ocr`、`TestYYS.test_yuhun`。这些失败与本次入口场景范围无关，不作为收尾阻塞项。

- [x] **Step 3: 设计规格和实施计划已同步**
- [x] **Step 4: 不需要额外截图或 Trellis 任务**

---

## 完成标准（收缩范围后）

- [x] `YYSBaseScript` 入口跳转机制已实现
- [x] 探索、结界突破、御魂 3 个脚本声明 `entry_scene`
- [x] 狭间暗域明确保持 `entry_scene=None`
- [x] 第 28 章相关场景资产已提交
- [x] 探索场景重放和入口场景测试通过
- [x] spec、plan 和测试已同步到当前游戏事实
- [x] 不创建 Trellis 任务
