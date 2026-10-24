"""按模板命中把画面分类到公共场景，业务差异用 resolver 回调表达。

各脚本共享同一套规则结构，只提供自己的模板与 resolver，不再各自维护
相似的分类函数。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

from yys.common.scenes import Scene, Template

#: 模板匹配回调：命中返回 True，具体坐标由业务脚本自己的匹配器决定。
Matcher = Callable[[np.ndarray, Template], bool]
#: 业务细分回调：同一页面需要按业务事实拆成多个场景时使用。
Resolver = Callable[[np.ndarray], Scene]


@dataclass(frozen=True)
class SceneRule:
    """一条分类规则：任一模板命中即采用该场景，resolver 可覆盖为细分场景。"""

    scene: Scene
    templates: tuple[Template, ...]
    resolve: Resolver | None = None


class SceneClassifier:
    """按声明顺序分类画面；所有规则都不命中时返回 None。"""

    def __init__(self, match: Matcher, rules: Sequence[SceneRule]) -> None:
        """保存匹配回调与按优先级排列的规则。"""
        self._match = match
        self._rules = tuple(rules)

    def classify(self, frame: np.ndarray) -> Scene | None:
        """返回首个命中规则的场景；resolver 存在时以它的结果为准。"""
        for rule in self._rules:
            if not any(self._match(frame, template) for template in rule.templates):
                continue
            return rule.resolve(frame) if rule.resolve is not None else rule.scene
        return None
