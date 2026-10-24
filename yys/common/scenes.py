"""跨脚本共享的游戏场景与识别模板标识。

集中维护后，各脚本的条件判断只保留业务差异，不再散落字符串字面量；
模板图片路径仍由各脚本自己的图片目录解析。
"""

from __future__ import annotations

from enum import StrEnum


class Scene(StrEnum):
    """游戏场景名，与 SceneManager 注册名和脚本分类结果保持一致。"""

    # 通用场景
    HOME = "home"
    EXPLORATION = "exploration"
    EXPLORATION_CHAPTER_28 = "exploration_chapter_28"
    AWAKENING_MATERIALS = "awakening_materials"
    BARRIER_BREAKTHROUGH = "barrier_breakthrough"
    BATTLING = "battling"
    SOUL_SELECTION = "soul_selection"
    SOUL_LEVEL_SELECTION = "soul_level_selection"
    SOUL_TEAM = "soul_team"
    REGIONAL_DEMON_BOSS = "regional_demon_boss"
    SPIRIT_GUARDIAN = "spirit_guardian"
    GUILD = "guild"
    CONFIRM = "confirm"
    PANEL = "panel"
    # 结界寄养
    REALM_OWN = "realm_own"
    GROWTH_OWN = "growth_own"
    GROWTH_FRIEND = "growth_friend"
    FOSTERED = "fostered"
    # 狭间暗域
    ABYSS_SELECTION = "abyss_selection"
    ABYSS_ENEMY_SELECTION = "abyss_enemy_selection"


class Template(StrEnum):
    """识别模板名；同名模板的路径由各脚本的图片目录决定。"""

    # 通用模板
    HOME = "home"
    HOME_MENU = "home_menu"
    HOME_SAKURA_LANTERN = "home_sakura_lantern"
    RETURN = "return"
    TO_HOME = "to_home"
    POPUP_CLOSE = "popup_close"
    CONFIRM = "confirm"
    CONFIRM_BUTTON = "confirm_button"
    # 阴阳寮
    GUILD = "guild"
    GUILD_LIVE = "guild_live"
    GUILD_V2 = "guild_v2"
    GUILD_TREE_NOTICE = "guild_tree_notice"
    GUILD_TREE_CLOSE = "guild_tree_close"
    # 结界寄养
    GROWTH = "growth"
    GROWTH_ENTRY = "growth_entry"
    GROWTH_RETURN = "growth_return"
    FOSTER_OPEN = "foster_open"
    FRIENDS = "friends"
    ENTER = "enter"
    CANCEL_BUTTON = "cancel_button"
