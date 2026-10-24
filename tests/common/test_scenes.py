"""公共场景与模板枚举的契约。"""

from __future__ import annotations

from pathlib import Path

from yys.common.scenes import Scene, Template

ROOT = Path(__file__).resolve().parents[2]
SCENE_DIR = ROOT / "yys/common/images/scene"
CONTROL_DIR = ROOT / "yys/common/images/scene_control"


def test_scene_directory_names_are_covered_by_shared_enum() -> None:
    # 产品契约：SceneManager 按目录注册场景，公共枚举必须覆盖这些场景名，
    # 否则脚本改用枚举后会出现名字漂移。
    names = {path.stem for path in SCENE_DIR.glob("*.bmp")}
    names |= {path.name for path in SCENE_DIR.iterdir() if path.is_dir()}
    assert names <= {scene.value for scene in Scene}


def test_shared_control_templates_exist_in_common_directory() -> None:
    # 产品契约：公共模板名必须能在公共控件目录找到对应文件。
    for template in (Template.RETURN, Template.TO_HOME):
        assert (CONTROL_DIR / f"{template}.bmp").is_file(), template


def test_realm_foster_uses_shared_scene_and_template_enums() -> None:
    # 产品契约：业务脚本复用公共枚举，不复制本地定义。
    from yys.realm_foster import realm_foster_script

    assert realm_foster_script.Scene is Scene
    assert realm_foster_script.Template is Template


def test_abyss_script_uses_shared_scene_enum() -> None:
    # 产品契约：狭间暗域的场景判断同样引用公共枚举。
    from yys.abyss_shadows import abyss_shadows_script

    assert abyss_shadows_script.Scene is Scene
