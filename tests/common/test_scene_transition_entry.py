"""YYSBaseScript entry_scene 前置跳转行为的单元测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.common.environment.mock_environment import MockEnvironment
from tests.common.recorders.action_log import ActionLog
from yys.common.event_script_base import YYSBaseScript
from yys.common.scene_manager import SceneManager


class _ProbeScript(YYSBaseScript):
    """探针脚本：on_run 内调 stop() 让主循环确定性退出。"""

    SCRIPT_META = None

    def on_run(self) -> None:  # type: ignore[override]
        # 调 stop() 让 EventBaseScript.run() 的 while 循环下一次迭代时退出
        self.stop()


def _make_script(env: MockEnvironment, entry_scene: str = "") -> _ProbeScript:
    """构造一个绑定到 MockEnvironment 的 _ProbeScript 实例。"""
    script = _ProbeScript(script_name="probe", env=env)
    script.entry_scene = entry_scene
    return script


def test_entry_scene_empty_skips_goto_scene() -> None:
    """entry_scene 为空字符串时，run() 不调用 scene_manager.goto_scene。"""
    log = ActionLog()
    env = MockEnvironment(action_log=log)
    script = _make_script(env, entry_scene="")
    script.scene_manager = MagicMock(spec=SceneManager)

    script.run()  # on_run 调 stop()，主循环确定性退出

    script.scene_manager.goto_scene.assert_not_called()


def test_entry_scene_set_calls_goto_scene_with_correct_arg() -> None:
    """entry_scene 非空时，run() 调用 scene_manager.goto_scene(self.entry_scene)。"""
    log = ActionLog()
    env = MockEnvironment(action_log=log)
    script = _make_script(env, entry_scene="exploration_chapter_28")
    script.scene_manager = MagicMock(spec=SceneManager)
    script.scene_manager.goto_scene.return_value = True

    script.run()  # on_run 调 stop()，主循环确定性退出

    script.scene_manager.goto_scene.assert_called_once_with("exploration_chapter_28")


def test_entry_scene_goto_fails_does_not_enter_main_loop() -> None:
    """goto_scene 返回 False 时，run() 不调用 on_run()，主循环不启动。"""
    log = ActionLog()
    env = MockEnvironment(action_log=log)
    script = _make_script(env, entry_scene="barrier_breakthrough")
    script.scene_manager = MagicMock(spec=SceneManager)
    script.scene_manager.goto_scene.return_value = False
    script.on_run = MagicMock()  # type: ignore[method-assign]

    # 跳转失败时 run() 会立即 return，不会进入主循环，不需要后台线程
    script.run()

    script.scene_manager.goto_scene.assert_called_once_with("barrier_breakthrough")
    script.on_run.assert_not_called()


def test_business_scripts_declare_entry_scene() -> None:
    """2 个可稳定定位入口的核心脚本必须声明 entry_scene；御魂改用 entry_spec。

    产品契约：PRD AC10——现有探索、结界突破入口不得退化；
    AC2——御魂通过 TaskEntrySpec 声明新入口契约（任务 08-08）。
    """
    from yys.exploration.exploration_script import ExplorationScript
    from yys.realm_raid.realm_raid_script import RealmRaidScript

    legacy_map = {
        ExplorationScript: "exploration_chapter_28",
        RealmRaidScript: "barrier_breakthrough",
    }
    for cls, expected in legacy_map.items():
        # 字面量匹配
        assert cls.entry_scene == expected, (
            f"{cls.__name__}.entry_scene 期望 {expected!r}，实际 {cls.entry_scene!r}"
        )
        # 非空（防止空字符串/空集合等 falsy 值）
        assert cls.entry_scene, f"{cls.__name__}.entry_scene 为空"
        # 非 None（基类默认 None，覆盖后必须非 None）
        assert cls.entry_scene is not None, f"{cls.__name__}.entry_scene 为 None"


def test_soul_raid_declares_entry_spec() -> None:
    """御魂作为首个试点声明 TaskEntrySpec(target_scene="soul_selection")。"""
    from yys.soul_raid.soul_raid_script import SoulRaidScript

    spec = SoulRaidScript.entry_spec
    assert spec is not None
    assert spec.target_scene == "soul_selection"
    # 新契约下御魂不再使用旧 entry_scene 跳转
    assert SoulRaidScript.entry_scene is None or SoulRaidScript.entry_scene == ""


def test_entry_spec_prepare_ready_then_business() -> None:
    """声明 entry_spec 的脚本：run() 先 prepare，READY 后才进入业务主循环。"""
    log = ActionLog()
    env = MockEnvironment(action_log=log)
    script = _ProbeScript(script_name="probe", env=env)
    from yys.common.entry_runtime import (
        EntryOutcome,
        EntryPreparationResult,
        TaskEntrySpec,
    )

    script.entry_spec = TaskEntrySpec(target_scene="soul_selection")
    ready = EntryPreparationResult(outcome=EntryOutcome.READY, stage="ready")
    script.prepare_entry = MagicMock(return_value=ready)  # type: ignore[method-assign]
    script.run_business = MagicMock()  # type: ignore[method-assign]

    script.run()

    script.prepare_entry.assert_called_once()
    script.run_business.assert_called_once()


def test_entry_spec_prepare_failure_raises_structured_error() -> None:
    """入口准备失败抛出 EntryPreparationError，禁止正常 return 后误报业务成功。"""
    log = ActionLog()
    env = MockEnvironment(action_log=log)
    script = _ProbeScript(script_name="probe", env=env)
    from yys.common.entry_runtime import (
        EntryOutcome,
        EntryPreparationError,
        EntryPreparationResult,
        TaskEntrySpec,
    )

    script.entry_spec = TaskEntrySpec(target_scene="soul_selection")
    failed = EntryPreparationResult(
        outcome=EntryOutcome.ERROR,
        stage="entry_failed",
        error_code="ENTRY_SCENE_UNKNOWN",
        reason="无法识别当前画面",
    )
    script.prepare_entry = MagicMock(return_value=failed)  # type: ignore[method-assign]
    script.run_business = MagicMock()  # type: ignore[method-assign]

    with pytest.raises(EntryPreparationError) as ctx:
        script.run()

    assert ctx.value.result.error_code == "ENTRY_SCENE_UNKNOWN"
    script.run_business.assert_not_called()

def test_abyss_shadows_entry_scene_is_disabled() -> None:
    """当前版本不为狭间暗域声明统一入口场景。"""
    from yys.abyss_shadows.abyss_shadows_script import Main

    assert Main.entry_scene is None
