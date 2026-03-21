# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 重要说明

- **回答和代码注释必须使用中文**
- **Git 提交信息必须使用中文**

## 项目概述

yys-pc-script 是一个基于事件驱动架构的阴阳师 PC 端自动化脚本。通过图像识别、OCR 和鼠标/键盘控制实现游戏任务自动化，无需游戏窗口处于前台激活状态。

## 环境配置

```bash
pip install -r requirements.txt
```

环境要求：Python 3.11+，Windows 系统

## 运行脚本

每个游戏任务（探索、御魂、结界突破等）都是 `yys/` 目录下的独立脚本：
- `python yys/exploration.py` - 章节探索
- `python yys/yuhun.py` - 御魂副本
- `python yys/jiejietupo.py` - 结界突破
- `python yys/yuling.py` - 御灵副本
- `python yys/douji.py` - 收藏/组队
- 其他脚本位于 `yys/fujiwara/`、`yys/kuzunoha/`、`yys/rifts_shadows/`

## 架构设计

### 事件驱动核心 (`win_util/`)

框架基于事件驱动架构构建：

1. **`EventBaseScript`** (`win_util/event.py`) - 所有游戏脚本的基类
   - 运行连续循环，更新截图缓存并触发已注册的事件
   - 钩子方法：`on_run()`、`before_iteration()`、`after_iteration()`
   - 支持通过线程事件实现暂停/恢复/停止控制

2. **`WinController`** (`win_util/controller.py`) - 聚合所有 Windows 控制能力
   - `image_finder`：截图捕获和模板匹配
   - `keyboard`：后台键盘输入
   - `mouse`：后台鼠标点击
   - `ocr`：基于 EasyOCR 的文字识别

3. **`SceneManager`** (`yys/scene_manager.py`) - 场景检测和导航
   - 场景图片位于 `yys/images/scene/`（如 `home.bmp`、`exploration.bmp`）
   - 场景跳转按钮位于 `yys/images/scene/scene_control/`，命名规范：`[源场景]_to_[目标场景].bmp`
   - 提供 `goto_scene(target)` 方法，通过 BFS 计算最短路径并执行点击

### 游戏脚本模式

```python
class MyScript(YYSBaseScript):  # YYSBaseScript 继承自 EventBaseScript
    def __init__(self):
        super().__init__("ScriptName")
        # 注册图像匹配事件 - 找到图像时触发回调
        self._register_image_match_event(
            ImageMatchConfig("path/to/button.bmp"),
            self._on_button_clicked
        )

    def _on_button_clicked(self, point):
        self.bg_left_click(point)  # 带随机偏移的点击

    def on_run(self):
        # 脚本启动时调用一次
        self.scene_manager.goto_scene("target_scene")
```

### 关键图片路径

- 游戏操作按钮：`yys/images/*.bmp`（tansuo_tiaozhan.bmp、yuhun_tiaozhan.bmp 等）
- 场景背景：`yys/images/scene/*.bmp`（home.bmp、battling.bmp）
- 场景跳转：`yys/images/scene/scene_control/*_to_*.bmp`
- 战斗结束检测：`battle_end.bmp`、`battle_end_success.bmp`、`battle_end_loss.bmp`

### 继承的事件处理器

`YYSBaseScript` 预注册了以下事件，子类可以覆盖：
- `_on_zhan_dou_wan_cheng_victory` - 胜利画面点击
- `_on_zhan_dou_wan_cheng` - 战斗结束（失败/奖励）点击
- `_on_wanted_quests_invited` - 悬赏封印邀请处理

### 图像匹配

- 使用 OpenCV 模板匹配，可配置相似度（默认 0.8）
- `ImageMatchConfig` 可接受单个路径或路径列表
- 截图缓存在 `ImageFinder.screenshot_cache` 中，每次迭代更新
- 路径解析：相对路径通过 `to_project_path()` 从项目根目录解析

## 测试

测试位于 `yys/test/`，使用 pytest 运行：
```bash
pytest yys/test/
```

集成测试需要打开游戏窗口。

## GUI（开发中）

基于 Electron 的 Web GUI 位于 `gui/` 目录，运行方式：
```bash
cd gui && npm install && npm start
```
