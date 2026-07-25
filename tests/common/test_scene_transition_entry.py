"""YYSBaseScript entry_scene 前置跳转行为的单元测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

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
    """3 个可稳定定位入口的核心脚本必须声明 entry_scene。

    防止：基类默认值被反向改、entry_scene 字面量被误改。
    """
    from yys.exploration.exploration_script import ExplorationScript
    from yys.realm_raid.realm_raid_script import RealmRaidScript
    from yys.soul_raid.soul_raid_script import SoulRaidScript

    expected_map = {
        ExplorationScript: "exploration_chapter_28",
        RealmRaidScript: "barrier_breakthrough",
        SoulRaidScript: "soul_selection",
    }
    for cls, expected in expected_map.items():
        # 字面量匹配
        assert cls.entry_scene == expected, (
            f"{cls.__name__}.entry_scene 期望 {expected!r}，实际 {cls.entry_scene!r}"
        )
        # 非空（防止空字符串/空集合等 falsy 值）
        assert cls.entry_scene, f"{cls.__name__}.entry_scene 为空"
        # 非 None（基类默认 None，覆盖后必须非 None）
        assert cls.entry_scene is not None, f"{cls.__name__}.entry_scene 为 None"


def test_abyss_shadows_entry_scene_is_disabled() -> None:
    """当前版本不为狭间暗域声明统一入口场景。"""
    from yys.abyss_shadows.abyss_shadows_script import Main

    assert Main.entry_scene is None
