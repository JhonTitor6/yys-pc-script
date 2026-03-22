# WinController 重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 WinController 和 YYSBaseScript，移除子组件直接暴露，通过 `__getattr__` 实现自动委托，新增便捷方法。

**Architecture:** WinController 通过 `__getattr__` 前缀映射自动委托方法到子组件；YYSBaseScript 通过 `__getattr__` 代理到 win_controller；SceneManager 改为接收 win_controller 而非 image_finder。

**Tech Stack:** Python, win32gui, win_util

---

## 改动文件清单

| 文件 | 改动 |
|------|------|
| `win_util/controller.py` | 添加 `__getattr__` + 5 个新便捷方法 |
| `yys/common/scene_manager.py` | `__init__` 参数改为 `win_controller`，内部改用 `win_controller` 调用 |
| `yys/common/event_script_base.py` | 移除 `self.image_finder/keyboard/mouse/ocr`，添加 `__getattr__` 代理 |

---

## Task 1: WinController 添加 `__getattr__` 自动委托

**Files:**
- Modify: `win_util/controller.py`

- [ ] **Step 1: 添加 `_PREFIX_MAP` 常量和 `__getattr__` 方法**

在 `WinController` 类中添加以下内容（在 `__init__` 之后）：

```python
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

- [ ] **Step 2: 运行测试验证**

```bash
cd F:/Users/56440/PythonProjects/yys-pc-script && python -c "from win_util.controller import WinController; print('import ok')"
```

Expected: 无错误

- [ ] **Step 3: 提交**

```bash
git add win_util/controller.py
git commit -m "refactor(win_util): 添加 __getattr__ 自动委托到子组件

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: WinController 添加 5 个便捷方法

**注意:** `find_and_click`（line 169）和 `wait_for_image`（line 195）**已存在**，无需重复添加。

**Files:**
- Modify: `win_util/controller.py`

- [ ] **Step 1: 在 `WinController` 类末尾添加 5 个新方法**

在现有 `find_multiple_and_click_first` 方法之后添加：

```python
    def wait_for_image_disappear(self, image_path: str, timeout: float = 10,
                                   x0: int = 0, y0: int = 0, x1: int = 99999, y1: int = 99999,
                                   similarity: float = 0.8) -> bool:
        """等待图片消失"""
        start = time.time()
        while time.time() - start < timeout:
            self.update_screenshot_cache()
            pos = self.find_image(image_path, x0, y0, x1, y1, similarity)
            if pos == (-1, -1):
                return True
            time.sleep(0.5)
        return False

    def wait_for_text(self, text: str, timeout: float = 10,
                      case_sensitive: bool = False):
        """等待文字出现"""
        start = time.time()
        while time.time() - start < timeout:
            result = self.find_text_position(self.image_finder.screenshot_cache, text,
                                             similarity_threshold=0.3,
                                             case_sensitive=case_sensitive)
            if result:
                return result
            time.sleep(0.5)
        return None

    def wait_for_text_disappear(self, text: str, timeout: float = 10,
                                 case_sensitive: bool = False) -> bool:
        """等待文字消失"""
        start = time.time()
        while time.time() - start < timeout:
            result = self.find_text_position(self.image_finder.screenshot_cache, text,
                                             similarity_threshold=0.3,
                                             case_sensitive=case_sensitive)
            if not result:
                return True
            time.sleep(0.5)
        return False

    def wait_for_image_and_click(self, image_path: str, timeout: float = 10,
                                  x0: int = 0, y0: int = 0, x1: int = 99999, y1: int = 99999,
                                  similarity: float = 0.8,
                                  x_range: int = 20, y_range: int = 20) -> bool:
        """等待图片出现并点击"""
        pos = self.wait_for_image(image_path, timeout, x0, y0, x1, y1, similarity)
        if pos and pos != (-1, -1):
            self.mouse.bg_left_click(pos, x_range=x_range, y_range=y_range)
            return True
        return False

    def wait_for_text_and_click(self, text: str, timeout: float = 10,
                                 x_range: int = 20, y_range: int = 20,
                                 case_sensitive: bool = False) -> bool:
        """等待文字出现并点击"""
        pos = self.wait_for_text(text, timeout, case_sensitive)
        if pos:
            self.mouse.bg_left_click(pos, x_range=x_range, y_range=y_range)
            return True
        return False
```

- [ ] **Step 2: 运行测试验证**

```bash
cd F:/Users/56440/PythonProjects/yys-pc-script && python -c "
from win_util.controller import WinController
methods = ['wait_for_image_disappear', 'wait_for_text', 'wait_for_text_disappear',
           'wait_for_image_and_click', 'wait_for_text_and_click']
for m in methods:
    assert hasattr(WinController, m), f'{m} not found'
print('All 5 new methods present')
"
```

Expected: `All 5 new methods present`

- [ ] **Step 3: 提交**

```bash
git add win_util/controller.py
git commit -m "feat(win_util): 添加 5 个便捷等待方法

- wait_for_image_disappear: 等待图片消失
- wait_for_text: 等待文字出现
- wait_for_text_disappear: 等待文字消失
- wait_for_image_and_click: 等待图片出现并点击
- wait_for_text_and_click: 等待文字出现并点击

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: SceneManager 改为接收 win_controller

**Files:**
- Modify: `yys/common/scene_manager.py`（`__init__` 方法和内部调用处）

- [ ] **Step 1: 修改 `__init__` 签名和内部存储**

找到 `SceneManager.__init__` 方法，将：
```python
def __init__(self, hwnd: int, image_finder: ImageFinder):
    self.hwnd = hwnd
    self.image_finder = image_finder
```

改为：
```python
def __init__(self, hwnd: int, win_controller: 'WinController'):
    self.hwnd = hwnd
    self.win_controller = win_controller
```

同时移除 `ImageFinder` 的 import（如果不再需要）。

- [ ] **Step 2: 修内部引用（5处）**

搜索文件中所有 `self.image_finder.` 的调用，改为 `self.win_controller.`：

| 位置 | 旧 | 新 |
|------|----|----|
| `detect_current_scene` 方法 | `self.image_finder.screenshot_cache` | `self.win_controller.image_finder.screenshot_cache` |
| `detect_current_scene` 方法 | `self.image_finder.bg_find_pic(...)` | `self.win_controller.bg_find_pic(...)` |
| `goto_scene` 方法 | `self.image_finder.bg_find_pic_by_cache(...)` | `self.win_controller.bg_find_pic_by_cache(...)` |
| `goto_scene` 方法 | `self.image_finder.update_screenshot_cache()` | `self.win_controller.update_screenshot_cache()` |
| `click_return` 方法 | `self.image_finder.bg_find_pic_by_cache(...)` | `self.win_controller.bg_find_pic_by_cache(...)` |

注意：`bg_find_pic_by_cache` 以 `bg_` 开头，通过 `WinController.__getattr__` 委托到 `image_finder`。

- [ ] **Step 3: 验证 SceneManager 可以导入**

```bash
cd F:/Users/56440/PythonProjects/yys-pc-script && python -c "from yys.common.scene_manager import SceneManager; print('import ok')"
```

Expected: 无错误

- [ ] **Step 4: 提交**

```bash
git add yys/common/scene_manager.py
git commit -m "refactor(scene_manager): 改接收 win_controller 而非 image_finder

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: YYSBaseScript 移除子组件暴露，添加 `__getattr__`

**Files:**
- Modify: `yys/common/event_script_base.py`（移除子组件赋值，添加 `__getattr__`）

- [ ] **Step 1: 移除子组件直接暴露**

在 `__init__` 方法中，删除以下 4 行赋值语句：
```python
self.image_finder: ImageFinder = self.win_controller.image_finder
self.keyboard = self.win_controller.keyboard
self.mouse = self.win_controller.mouse
self.ocr: CommonOcr = self.win_controller.ocr
```

- [ ] **Step 2: 在 `__init__` 末尾（`super().__init__` 之后）添加 `__getattr__`**

```python
    def __getattr__(self, name):
        """代理到 win_controller，实现子组件方法的直接访问"""
        if name in ('win_controller', 'logger', 'hwnd', '_env', 'scene_manager'):
            raise AttributeError(name)
        if hasattr(self.win_controller, name):
            return getattr(self.win_controller, name)
        raise AttributeError(name)
```

- [ ] **Step 3: 验证导入**

```bash
cd F:/Users/56440/PythonProjects/yys-pc-script && python -c "from yys.common.event_script_base import YYSBaseScript; print('import ok')"
```

Expected: 无错误

- [ ] **Step 4: 提交**

```bash
git add yys/common/event_script_base.py
git commit -m "refactor(event_script_base): 移除子组件暴露，添加 __getattr__ 代理

YYSBaseScript 不再直接暴露 image_finder/keyboard/mouse/ocr，
通过 __getattr__ 代理到 win_controller，子类可直接调用如 self.bg_swipe()。

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: 集成测试验证

**Files:**
- Test: `tests/common/`, `yys/soul_raid/test_soul_raid.py`

- [ ] **Step 1: 运行公共模块测试**

```bash
cd F:/Users/56440/PythonProjects/yys-pc-script && pytest tests/common/ -v --tb=short
```

Expected: 全部 PASS

- [ ] **Step 2: 运行御魂模块测试**

```bash
cd F:/Users/56440/PythonProjects/yys-pc-script && pytest yys/soul_raid/test_soul_raid.py -v --tb=short
```

Expected: 全部 PASS

- [ ] **Step 3: 提交测试结果**

```bash
git add -A
git commit -m "test: 验证 WinController 重构后测试通过

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## 注意事项

1. **`bg_left_click_with_range`**: `SceneManager.goto_scene` 调用的是 `win_util.mouse.bg_left_click_with_range(hwnd, point, ...)` 独立函数，不是 MouseController 方法。此函数签名不同于 `mouse.bg_left_click_with_range(point, ...)`，不能通过 `__getattr__` 委托。

2. **SceneManager 使用 `bg_find_pic_by_cache`**: 此方法以 `bg_` 开头，通过 `__getattr__` 正确委托到 `image_finder`。

3. **方法名冲突解决**: 当前各子组件前缀不重叠（`bg_find_*` → image_finder，`bg_left*` → mouse，`key_*` → keyboard，`ocr_*` → ocr），按 `_PREFIX_MAP` 顺序第一个匹配生效。
