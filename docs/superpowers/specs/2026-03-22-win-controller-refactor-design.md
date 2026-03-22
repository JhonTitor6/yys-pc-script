# WinController 重构设计

## 目标

1. 移除 `YYSBaseScript` 中 `self.image_finder`、`self.keyboard`、`self.mouse`、`self.ocr` 的直接暴露
2. 通过 `__getattr__` 代理实现子类可直接调用（如 `self.bg_swipe()`）
3. WinController 新增便捷方法，减少子类重复逻辑

## 现有架构

```
YYSBaseScript
├── self.win_controller     # 聚合 WinController
├── self.image_finder       # ❌ 暴露了子组件
├── self.keyboard           # ❌
├── self.mouse              # ❌
├── self.ocr                # ❌
└── self.scene_manager      # 依赖 image_finder

WinController
├── self.image_finder
├── self.keyboard
├── self.mouse
└── self.ocr
```

## 重构后架构

```
YYSBaseScript
├── self.win_controller     # 唯一入口
├── self.scene_manager      # 依赖 win_controller
└── __getattr__             # 代理到 win_controller

WinController
├── 子组件（通过 __getattr__ 自动暴露）
│   ├── image_finder  → bg_find_*, crop_*, update_*
│   ├── mouse         → bg_left*, bg_right*, bg_swipe*
│   ├── keyboard      → key_*, press_*
│   └── ocr           → ocr_*, find_text*, contains_text*
│
└── 便捷方法（组合逻辑）
    ├── find_and_click(image, ...)           # 找图并点击
    ├── wait_for_image(image, timeout, ...)  # 等待图片出现
    ├── wait_for_image_disappear(...)        # 等待图片消失
    ├── wait_for_text(text, timeout, ...)    # 等待文字出现
    ├── wait_for_text_disappear(...)         # 等待文字消失
    ├── wait_for_image_and_click(...)        # 等待图片出现并点击
    └── wait_for_text_and_click(...)         # 等待文字出现并点击
```

## 实现细节

### 1. WinController `__getattr__` 自动委托

```python
class WinController:
    # 前缀 -> 组件映射（按优先级排序）
    _PREFIX_MAP = [
        ('bg_find_', 'image_finder'),
        ('crop_', 'image_finder'),
        ('update_', 'image_finder'),
        ('bg_left', 'mouse'),
        ('bg_right', 'mouse'),
        ('bg_swipe', 'mouse'),
        ('key_', 'keyboard'),
        ('press_', 'keyboard'),
        ('ocr_', 'ocr'),
        ('find_text', 'ocr'),
        ('contains_text', 'ocr'),
    ]

    def __getattr__(self, name):
        for prefix, attr_name in self._PREFIX_MAP:
            if name.startswith(prefix):
                component = getattr(self, attr_name)
                if hasattr(component, name):
                    return getattr(component, name)
        raise AttributeError(name)
```

**方法名冲突解决：** 当前各组件前缀不重叠，按 `_PREFIX_MAP` 顺序第一个匹配生效。

### 2. WinController 新增便捷方法

```python
def wait_for_image_disappear(self, image_path, timeout=10, x0=0, y0=0, x1=99999, y1=99999, similarity=0.8):
    """等待图片消失"""
    start = time.time()
    while time.time() - start < timeout:
        self.update_screenshot_cache()
        pos = self.find_image(image_path, x0, y0, x1, y1, similarity)
        if pos == (-1, -1):
            return True
        time.sleep(0.5)
    return False

def wait_for_text(self, text, timeout=10, case_sensitive=False):
    """等待文字出现"""
    start = time.time()
    while time.time() - start < timeout:
        result = self.find_text_position(self.image_finder.screenshot_cache, text,
                                         similarity_threshold=0.3, case_sensitive=case_sensitive)
        if result:
            return result
        time.sleep(0.5)
    return None

def wait_for_text_disappear(self, text, timeout=10, case_sensitive=False):
    """等待文字消失"""
    start = time.time()
    while time.time() - start < timeout:
        result = self.find_text_position(self.image_finder.screenshot_cache, text,
                                         similarity_threshold=0.3, case_sensitive=case_sensitive)
        if not result:
            return True
        time.sleep(0.5)
    return False

def wait_for_image_and_click(self, image_path, timeout=10, x0=0, y0=0, x1=99999, y1=99999,
                              similarity=0.8, x_range=20, y_range=20):
    """等待图片出现并点击"""
    pos = self.wait_for_image(image_path, timeout, x0, y0, x1, y1, similarity)
    if pos and pos != (-1, -1):
        self.mouse.bg_left_click(pos, x_range=x_range, y_range=y_range)
        return True
    return False

def wait_for_text_and_click(self, text, timeout=10, x_range=20, y_range=20, case_sensitive=False):
    """等待文字出现并点击"""
    pos = self.wait_for_text(text, timeout, case_sensitive)
    if pos:
        self.mouse.bg_left_click(pos, x_range=x_range, y_range=y_range)
        return True
    return False
```

### 3. YYSBaseScript 改动

```python
class YYSBaseScript(EventBaseScript):
    def __init__(self, script_name, env=None):
        # 初始化 WinController
        if env is not None:
            self.win_controller = WinController(env=env)
        else:
            self.win_controller = WinController(self.hwnd)

        # 移除直接暴露子组件
        # 旧: self.image_finder = self.win_controller.image_finder
        # 旧: self.keyboard = self.win_controller.keyboard
        # 旧: self.mouse = self.win_controller.mouse
        # 旧: self.ocr = self.win_controller.ocr

        # scene_manager 改为接收 win_controller
        self.scene_manager = SceneManager(self.hwnd, self.win_controller)

        # 父类仍需传入 image_finder 和 ocr（EventBaseScript 依赖）
        super().__init__(self.win_controller.image_finder, self.win_controller.ocr)

    def __getattr__(self, name):
        # 代理到 win_controller
        if name in ('win_controller', 'logger', 'hwnd', '_env', 'scene_manager'):
            raise AttributeError(name)
        if hasattr(self.win_controller, name):
            return getattr(self.win_controller, name)
        raise AttributeError(name)
```

### 4. SceneManager 改动

```python
class SceneManager:
    def __init__(self, hwnd, win_controller):  # 改接收 win_controller
        self.hwnd = hwnd
        self.win_controller = win_controller

    def _find_image(self, path, ...):
        return self.win_controller.find_image(path, ...)
```

## 改动文件清单

| 文件 | 改动内容 |
|------|---------|
| `win_util/controller.py` | 添加 `__getattr__` + 6 个便捷方法 |
| `yys/common/event_script_base.py` | 移除子组件暴露，添加 `__getattr__` |
| `yys/common/scene_manager.py` | 改 `__init__` 参数接收 `win_controller` |

**不受影响（自动兼容）：**
- `yys/exploration/exploration_script.py`
- `yys/realm_raid/realm_raid_script.py`
- `yys/abyss_shadows/abyss_shadows_script.py`
- `yys/soul_raid/soul_raid_script.py`
- 所有子类脚本

## 测试验证

```bash
pytest tests/common/ -v
pytest yys/soul_raid/test_soul_raid.py -v
```
