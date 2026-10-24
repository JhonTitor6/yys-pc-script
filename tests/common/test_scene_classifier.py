"""公共场景分类器的契约。"""

from __future__ import annotations

import numpy as np

from yys.common.scene_classifier import SceneClassifier, SceneRule
from yys.common.scenes import Scene, Template

FRAME = np.zeros((10, 10, 3), dtype=np.uint8)


def test_rules_are_evaluated_in_declaration_order() -> None:
    # 产品契约：覆盖层优先，先声明的规则先判定。
    classifier = SceneClassifier(
        lambda frame, template: template in (Template.CONFIRM, Template.FRIENDS),
        (
            SceneRule(Scene.CONFIRM, (Template.CONFIRM,)),
            SceneRule(Scene.PANEL, (Template.FRIENDS,)),
        ),
    )
    assert classifier.classify(FRAME) == Scene.CONFIRM


def test_rule_matches_any_of_its_templates() -> None:
    # 产品契约：同一场景的多个模板变体任一命中即可。
    classifier = SceneClassifier(
        lambda frame, template: template == Template.GUILD_V2,
        (SceneRule(Scene.GUILD, (Template.GUILD_LIVE, Template.GUILD_V2)),),
    )
    assert classifier.classify(FRAME) == Scene.GUILD


def test_resolver_overrides_rule_scene() -> None:
    # 产品契约：同一页面按业务事实细分成多个场景。
    classifier = SceneClassifier(
        lambda frame, template: template == Template.GROWTH,
        (
            SceneRule(
                Scene.GROWTH_OWN,
                (Template.GROWTH,),
                lambda frame: Scene.FOSTERED,
            ),
        ),
    )
    assert classifier.classify(FRAME) == Scene.FOSTERED


def test_returns_none_when_no_rule_matches() -> None:
    # 产品契约：没有任何证据时返回 None，由调用方决定等待或失败。
    classifier = SceneClassifier(
        lambda frame, template: False,
        (SceneRule(Scene.HOME, (Template.HOME,)),),
    )
    assert classifier.classify(FRAME) is None
