# 代码重构设计文档

**项目：** yys-pc-script 阴阳师自动化脚本
**日期：** 2026-03-22
**类型：** 渐进式代码重构
**目标：** 消除重复代码、统一配置管理、解耦模块依赖

---

## 1. 背景与目标

### 1.1 问题现状

项目中存在严重的代码重复问题：

1. **常量分散** - `event_script_base.py` 中定义了战斗相关的等待时间、点击偏移等常量，各业务脚本也可能有重复定义
2. **公共操作重复** - `bg_left_click`、`find_image` 等操作在多个模块中重复实现
3. **战斗逻辑耦合** - 各业务脚本的战斗流程逻辑紧耦合在各自脚本中，难以复用
4. **图片路径不统一** - 图片资源散落在 `yys/images/` 和各模块 `images/` 目录中

### 1.2 重构目标

- 建立 `yys/common/` 公共模块，集中管理常量、操作、战斗流程
- 将重复的代码提取为可复用组件
- 保持向后兼容，不破坏现有功能
- 为后续测试体系建设和性能优化奠定基础

---

## 2. 架构设计

### 2.1 目标目录结构

```
yys/
├── __init__.py
├── common/                          # 新增：公共模块
│   ├── __init__.py
│   ├── constants.py                 # 统一常量管理
│   ├── operations.py                 # 公共操作方法
│   ├── battle/                      # 战斗流程标准化
│   │   ├── __init__.py
│   │   ├── base.py                  # 战斗流程基类
│   │   ├── flow.py                  # 战斗状态机
│   │   └── hooks.py                 # 战斗钩子接口
│   └── images/                       # 图片资源管理
│       ├── __init__.py
│       └── manager.py               # 图片路径管理
├── soul_raid/
│   └── soul_raid_script.py          # 重构后
├── rifts_shadows/
├── event_script_base.py             # 重构后使用 common
└── ...
```

### 2.2 模块职责

| 模块 | 职责 |
|------|------|
| `constants.py` | 统一管理所有常量（等待时间、点击范围、相似度阈值等） |
| `operations.py` | 封装可复用的操作方法（点击、找图、等待） |
| `battle/base.py` | 战斗流程基类，定义标准流程 |
| `battle/flow.py` | 战斗状态机实现 |
| `battle/hooks.py` | 战斗钩子接口定义 |
| `images/manager.py` | 图片路径统一管理 |

---

## 3. 详细设计

### 3.1 常量枚举统一 (`yys/common/constants.py`)

#### 3.1.1 常量分类

```python
from enum import Enum
from dataclasses import dataclass

class BattleSleep:
    """战斗等待时间常量（秒）"""
    SHORT = 0.5       # 短等待
    MEDIUM = 1.0      # 中等等待
    LONG = 2.0        # 长等待
    VICTORY = 1.0     # 胜利后等待
    END = 2.0         # 战斗结束等待
    CLICK_AFTER = 0.5 # 点击后等待

class ClickRange:
    """点击偏移范围常量"""
    DEFAULT = 20      # 默认点击偏移
    BATTLE_END_X = 30 # 战斗结束点击X偏移
    BATTLE_END_Y = 50 # 战斗结束点击Y偏移
    OCR = 10          # OCR点击偏移

class ImageSimilarity:
    """图像识别相似度阈值"""
    DEFAULT = 0.8     # 默认相似度
    HIGH = 0.9        # 高相似度
    LOW = 0.7         # 低相似度

class BattleEndType(Enum):
    """战斗结束类型"""
    VICTORY = "victory"
    DEFEAT = "defeat"
    OTHER = "other"
```

#### 3.1.2 向后兼容

在 `event_script_base.py` 中保留旧常量引用，指向新的 common 模块：

```python
# 向后兼容别名
from yys.common.constants import BattleSleep as BATTLE_SLEEP_SHORT
# 或者直接导入
from yys.common.constants import (
    BATTLE_SLEEP_SHORT,
    BATTLE_SLEEP_MEDIUM,
    # ... 其他
)
```

### 3.2 公共操作方法 (`yys/common/operations.py`)

#### 3.2.1 操作封装类

```python
from typing import Optional, Tuple, List
from dataclasses import dataclass

@dataclass
class OperationResult:
    """操作结果"""
    success: bool
    position: Optional[Tuple[int, int]] = None
    message: str = ""

class ImageOperations:
    """图像相关操作封装"""

    def __init__(self, controller: 'WinController'):
        self.controller = controller

    def find_image(self, image_path: str, timeout: int = 0,
                   similarity: float = 0.8) -> OperationResult:
        """
        查找图片

        Args:
            image_path: 图片路径
            timeout: 超时时间（秒），0 表示不等待
            similarity: 相似度阈值

        Returns:
            OperationResult
        """
        if timeout > 0:
            point = self.controller.find_image_with_timeout(
                image_path, timeout=timeout, similarity=similarity
            )
        else:
            point = self.controller.find_image(
                image_path, similarity=similarity
            )

        if point and point != (-1, -1):
            return OperationResult(success=True, position=point)
        return OperationResult(success=False, message="未找到目标")

    def find_and_click(self, image_path: str, timeout: int = 0,
                       x_range: int = 20, y_range: int = 20,
                       similarity: float = 0.8) -> OperationResult:
        """查找并点击"""
        result = self.find_image(image_path, timeout, similarity)
        if result.success:
            self.controller.mouse.bg_left_click(
                result.position, x_range=x_range, y_range=y_range
            )
        return result

    def wait_for_image(self, image_path: str, timeout: int = 10,
                        similarity: float = 0.8) -> OperationResult:
        """等待图片出现"""
        return self.find_image(image_path, timeout, similarity)
```

### 3.3 战斗流程标准化 (`yys/common/battle/`)

#### 3.3.1 钩子接口 (`hooks.py`)

```python
from abc import ABC, abstractmethod
from typing import Optional

class BattleHooks(ABC):
    """战斗钩子接口"""

    @abstractmethod
    def on_challenge_found(self, position: tuple) -> None:
        """挑战按钮被发现时调用"""
        pass

    @abstractmethod
    def on_challenge_clicked(self) -> None:
        """挑战按钮被点击后调用"""
        pass

    @abstractmethod
    def on_battle_start(self) -> None:
        """战斗开始时调用"""
        pass

    @abstractmethod
    def on_battle_end(self, end_type: 'BattleEndType') -> None:
        """战斗结束时调用"""
        pass

    @abstractmethod
    def on_victory(self) -> None:
        """战斗胜利时调用"""
        pass

    @abstractmethod
    def on_defeat(self) -> None:
        """战斗失败时调用"""
        pass

    @abstractmethod
    def should_continue(self) -> bool:
        """检查是否继续战斗（用于判断是否达到预设次数）"""
        pass
```

#### 3.3.2 战斗流程基类 (`base.py`)

```python
from abc import ABC
from typing import Optional, List
from enum import Enum

from yys.common.constants import BattleSleep, ClickRange, ImageSimilarity
from yys.common.operations import ImageOperations
from yys.common.battle.hooks import BattleHooks

class BattleFlow(ABC):
    """
    战斗流程基类

    定义标准战斗流程：
    1. 等待挑战按钮出现
    2. 点击挑战按钮
    3. 等待战斗开始
    4. 等待战斗结束
    5. 处理战斗结果
    6. 循环或结束
    """

    def __init__(
        self,
        script_name: str,
        challenge_image: str,
        operations: ImageOperations,
        hooks: BattleHooks,
        max_battle_count: int = 100
    ):
        self.script_name = script_name
        self.challenge_image = challenge_image
        self.operations = operations
        self.hooks = hooks
        self.max_battle_count = max_battle_count
        self.current_battle_count = 0
        self.current_victory_count = 0

    def execute_battle_loop(self) -> None:
        """执行战斗循环"""
        while self.hooks.should_continue():
            self._wait_challenge()
            self._click_challenge()
            self._wait_battle_start()
            end_type = self._wait_battle_end()
            self._handle_battle_end(end_type)

    def _wait_challenge(self) -> None:
        """等待挑战按钮"""
        result = self.operations.wait_for_image(
            self.challenge_image,
            timeout=30,
            similarity=ImageSimilarity.DEFAULT
        )
        if result.success and result.position:
            self.hooks.on_challenge_found(result.position)

    def _click_challenge(self) -> None:
        """点击挑战按钮"""
        result = self.operations.find_and_click(
            self.challenge_image,
            x_range=ClickRange.DEFAULT,
            y_range=ClickRange.DEFAULT
        )
        if result.success:
            self.hooks.on_challenge_clicked()

    def _wait_battle_start(self) -> None:
        """等待战斗开始"""
        # 子类可覆盖实现特定逻辑
        pass

    def _wait_battle_end(self) -> 'BattleEndType':
        """等待战斗结束"""
        # 使用状态机或轮询检测战斗结束
        from yys.common.constants import BattleEndType
        # ... 实现检测逻辑
        return BattleEndType.VICTORY

    def _handle_battle_end(self, end_type: 'BattleEndType') -> None:
        """处理战斗结束"""
        self.hooks.on_battle_end(end_type)

        if end_type == BattleEndType.VICTORY:
            self.current_victory_count += 1
            self.hooks.on_victory()
        else:
            self.hooks.on_defeat()

        self.current_battle_count += 1
```

### 3.4 业务脚本简化示例

#### 重构前 (`soul_raid_script.py`)

```python
class SoulRaidScript(YYSBaseScript):
    def __init__(self):
        super().__init__("soul_raid")
        self._register_image_match_event(
            ImageMatchConfig("yys/soul_raid/images/yuhun_tiaozhan.bmp"),
            self._on_yuhun_tiaozhan
        )
        self._register_image_match_event(
            ImageMatchConfig("yys/soul_raid/images/lock_accept_invitation.bmp"),
            self._on_lock_accept_invitation
        )

    def _on_yuhun_tiaozhan(self, point):
        self.bg_left_click(point, x_range=20, y_range=20)

    def _on_lock_accept_invitation(self, point):
        self.bg_left_click(point, x_range=15, y_range=15)
```

#### 重构后 (`soul_raid_script.py`)

```python
from yys.common.battle.base import BattleFlow
from yys.common.battle.hooks import BattleHooks
from yys.common.constants import BattleEndType
from yys.event_script_base import YYSBaseScript

class SoulRaidHooks(BattleHooks):
    """御魂战斗钩子实现"""

    def __init__(self, script: YYSBaseScript):
        self.script = script

    def on_challenge_found(self, position: tuple) -> None:
        pass

    def on_challenge_clicked(self) -> None:
        # 御魂特有：锁定邀请
        self.script.wait_and_click("yys/soul_raid/images/lock_accept_invitation.bmp")

    def on_battle_start(self) -> None:
        pass

    def on_battle_end(self, end_type: BattleEndType) -> None:
        pass

    def on_victory(self) -> None:
        self.script.log_victory()

    def on_defeat(self) -> None:
        pass

    def should_continue(self) -> bool:
        return self.script.current_battle_count < self.script.max_battle_count

class SoulRaidScript(YYSBaseScript):
    """御魂挂机脚本"""

    def __init__(self):
        super().__init__("soul_raid")

        hooks = SoulRaidHooks(self)
        self.battle_flow = BattleFlow(
            script_name="soul_raid",
            challenge_image="yys/soul_raid/images/yuhun_tiaozhan.bmp",
            operations=self.operations,
            hooks=hooks,
            max_battle_count=307
        )

    def run(self):
        self.battle_flow.execute_battle_loop()
```

---

## 4. 重构步骤

### Step 1: 创建公共模块结构
```
yys/common/
├── __init__.py
├── constants.py
├── operations.py
└── battle/
    ├── __init__.py
    ├── base.py
    ├── flow.py
    └── hooks.py
```

### Step 2: 实现常量模块 (`constants.py`)
- 定义所有常量类
- 确保向后兼容

### Step 3: 实现操作模块 (`operations.py`)
- 封装 ImageOperations 类
- 保持与 WinController 的接口兼容

### Step 4: 实现战斗流程模块 (`battle/`)
- 实现 BattleHooks 接口
- 实现 BattleFlow 基类

### Step 5: 重构 YYSBaseScript
- 使用新的 common 模块
- 保持向后兼容

### Step 6: 重构业务脚本
- 以 SoulRaidScript 为试点
- 逐步重构其他业务脚本

---

## 5. 向后兼容

### 5.1 常量兼容
```python
# event_script_base.py
# 保留旧的常量定义，指向新模块
from yys.common.constants import (
    BattleSleep as BATTLE_SLEEP_SHORT,
    BattleSleep as BATTLE_SLEEP_MEDIUM,
    # ...
)
```

### 5.2 操作方法兼容
```python
# 在 YYSBaseScript 中保留原有方法
def bg_left_click(self, point, x_range=20, y_range=20):
    # 调用新的 operations
    self.operations.click_with_random_offset(point, x_range, y_range)
```

---

## 6. 验收标准

1. **编译通过** - 所有 Python 文件无语法错误
2. **导入正常** - 所有模块可正常导入
3. **功能不变** - 御魂脚本实际运行结果与重构前一致
4. **向后兼容** - 现有代码无需修改即可运行
5. **代码重复减少** - 业务脚本代码量减少 50%+

---

## 7. 后续计划

本次重构完成后，可继续：
1. 测试体系建设 - 基于重构后的模块化结构建立 Mock 测试
2. 性能优化 - 在公共模块层面优化图像识别性能
3. 配置管理 - 建立统一的配置抽象层
