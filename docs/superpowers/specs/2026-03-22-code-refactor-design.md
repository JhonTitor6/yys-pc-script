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
| `battle/base.py` | 战斗流程基类，定义标准流程框架 |
| `battle/flow.py` | 战斗状态机实现，处理战斗各阶段的流转逻辑 |
| `battle/hooks.py` | 战斗钩子接口定义 |
| `images/manager.py` | 图片路径统一管理，提供路径查找服务 |

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
# 方式1：直接导入具体常量值（推荐）
from yys.common.constants import (
    BATTLE_SLEEP_SHORT,
    BATTLE_SLEEP_MEDIUM,
    BATTLE_SLEEP_LONG,
    BATTLE_VICTORY_SLEEP,
    BATTLE_END_SLEEP,
    BATTLE_END_CLICK_SLEEP,
    DEFAULT_CLICK_RANGE,
    BATTLE_END_CLICK_RANGE_X,
    BATTLE_END_CLICK_RANGE_Y,
    OCR_CLICK_RANGE,
)

# constants.py 中同时定义具体常量值和类
BATTLE_SLEEP_SHORT = 0.5
BATTLE_SLEEP_MEDIUM = 1.0
# ...
```

### 3.2 公共操作方法 (`yys/common/operations.py`)

#### 3.2.1 操作封装类

```python
from typing import Optional, Tuple, List, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from win_util.controller import WinController

@dataclass
class OperationResult:
    """操作结果"""
    success: bool
    position: Optional[Tuple[int, int]] = None
    message: str = ""

class ImageOperations:
    """图像相关操作封装

    封装基于 WinController 的可复用操作方法。
    构造函数接受 WinController 实例，内部代理其功能。
    """

    def __init__(self, controller: 'WinController'):
        """
        Args:
            controller: WinController 实例（来自 win_util.controller）
        """
        self._controller = controller

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
            point = self._controller.find_image_with_timeout(
                image_path, timeout=timeout, similarity=similarity
            )
        else:
            point = self._controller.find_image(
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
            self._controller.mouse.bg_left_click(
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
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Callable
from enum import Enum
import time

from yys.common.constants import BattleSleep, ClickRange, ImageSimilarity
from yys.common.operations import ImageOperations, OperationResult
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

    注意：本类采用轮询模式，直接在子线程中执行战斗流程。
    如需与现有 EventBaseScript 事件驱动模型整合，
    可将 BattleFlow 作为独立组件使用，或通过钩子与事件系统交互。
    """

    # 战斗结束检测图片配置
    BATTLE_END_CONFIGS: List[Dict] = []

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
        """等待战斗开始

        默认实现：等待固定时间让战斗画面加载。
        子类可覆盖实现特定逻辑，如检测战斗开始特征。
        """
        time.sleep(BattleSleep.MEDIUM)

    def _wait_battle_end(self) -> 'BattleEndType':
        """等待战斗结束

        轮询检测战斗结束图片，返回战斗结果类型。
        子类可覆盖此方法以自定义检测逻辑。
        """
        from yys.common.constants import BattleEndType

        # 如果子类定义了结束检测配置，使用它
        if self.BATTLE_END_CONFIGS:
            return self._poll_battle_end()

        # 默认：无限等待直到检测到结束（由外部停止）
        while self.hooks.should_continue():
            time.sleep(BattleSleep.SHORT)
        return BattleEndType.OTHER

    def _poll_battle_end(self) -> 'BattleEndType':
        """轮询检测战斗结束"""
        from yys.common.constants import BattleEndType

        victory_images = [c['image'] for c in self.BATTLE_END_CONFIGS if c.get('type') == 'victory']
        defeat_images = [c['image'] for c in self.BATTLE_END_CONFIGS if c.get('type') == 'defeat']

        while self.hooks.should_continue():
            # 检测胜利
            for img in victory_images:
                result = self.operations.find_image(img)
                if result.success:
                    return BattleEndType.VICTORY

            # 检测失败
            for img in defeat_images:
                result = self.operations.find_image(img)
                if result.success:
                    return BattleEndType.DEFEAT

            time.sleep(BattleSleep.SHORT)

        return BattleEndType.OTHER

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

#### 架构整合说明

**重要设计决策：**

`BattleFlow` 采用轮询模式，而 `EventBaseScript` 采用事件驱动模式。

**两种整合方式：**

1. **独立使用（推荐）**：`BattleFlow` 直接在子线程运行战斗循环，适用于独立的挂机脚本
2. **作为组件**：业务脚本继承 `BattleFlow` 并整合到事件驱动框架中

**本设计采用第一种方式**，`BattleFlow` 作为独立组件使用，
与现有的 `EventBaseScript` 事件驱动系统并行存在。

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
import time
from yys.common.battle.base import BattleFlow
from yys.common.battle.hooks import BattleHooks
from yys.common.constants import BattleEndType, BattleSleep, ClickRange, ImageSimilarity
from yys.common.operations import ImageOperations
from yys.event_script_base import YYSBaseScript
from win_util.image import ImageMatchConfig

class SoulRaidHooks(BattleHooks):
    """御魂战斗钩子实现

    御魂战斗流程：
    1. 检测挑战按钮 -> 点击挑战
    2. 弹出锁定邀请对话框 -> 点击接受/锁定
    3. 进入战斗 -> 等待战斗结束
    """

    # 战斗结束检测配置
    BATTLE_END_CONFIGS = [
        {'image': 'yys/images/battle_end_success.bmp', 'type': 'victory'},
        {'image': 'yys/images/battle_end_loss.bmp', 'type': 'defeat'},
    ]

    def __init__(self, script: YYSBaseScript):
        self.script = script
        self.lock_invitation_image = "yys/soul_raid/images/lock_accept_invitation.bmp"

    def on_challenge_found(self, position: tuple) -> None:
        """挑战按钮被发现时调用"""
        pass

    def on_challenge_clicked(self) -> None:
        """挑战按钮被点击后调用

        御魂特有：点击挑战后，会弹出"锁定邀请"对话框，
        需要等待并点击接受/锁定按钮。
        """
        # 等待对话框出现
        time.sleep(BattleSleep.SHORT)
        # 查找并点击锁定邀请按钮
        self.script.win_controller.find_and_click(
            self.lock_invitation_image,
            x_range=15,
            y_range=15,
            similarity=ImageSimilarity.DEFAULT
        )

    def on_battle_start(self) -> None:
        """战斗开始时调用"""
        pass

    def on_battle_end(self, end_type: BattleEndType) -> None:
        """战斗结束时调用"""
        pass

    def on_victory(self) -> None:
        """战斗胜利时调用"""
        self.script.logger.success(
            f"战斗胜利 {self.script._cur_battle_victory_count}/{self.script._max_battle_count}"
        )

    def on_defeat(self) -> None:
        """战斗失败时调用"""
        pass

    def should_continue(self) -> bool:
        """检查是否继续战斗"""
        return self.script._cur_battle_count < self.script._max_battle_count


class SoulRaidScript(YYSBaseScript):
    """御魂挂机脚本"""

    def __init__(self):
        super().__init__("soul_raid")

        # 创建操作封装
        operations = ImageOperations(self.win_controller)

        # 创建钩子
        hooks = SoulRaidHooks(self)

        # 创建战斗流程
        self.battle_flow = BattleFlow(
            script_name="soul_raid",
            challenge_image="yys/soul_raid/images/yuhun_tiaozhan.bmp",
            operations=operations,
            hooks=hooks,
            max_battle_count=307
        )

        # 设置战斗结束检测配置
        self.battle_flow.BATTLE_END_CONFIGS = SoulRaidHooks.BATTLE_END_CONFIGS

    def run(self):
        """启动御魂挂机"""
        self.logger.info("启动御魂挂机脚本")
        self.battle_flow.execute_battle_loop()
```

---

## 4. 重构步骤

### Step 1: 创建公共模块结构
```
yys/common/
├── __init__.py
├── constants.py          # 常量定义（同时包含具体值和类）
├── operations.py          # 操作封装类
└── battle/
    ├── __init__.py
    ├── base.py           # 战斗流程基类
    ├── flow.py           # 战斗状态机（处理阶段流转）
    └── hooks.py          # 战斗钩子接口
```

**说明：**
- `base.py`：定义 `BattleFlow` 基类，包含完整战斗流程框架
- `flow.py`：独立的状态机实现，处理战斗各阶段的精确流转逻辑，
  可被 `BattleFlow` 组合使用

### Step 2: 实现常量模块 (`constants.py`)
- 定义所有常量类
- 确保向后兼容

### Step 3: 实现操作模块 (`operations.py`)
- 封装 `ImageOperations` 类
- 使用 `TYPE_CHECKING` 避免循环导入
- 提供 `OperationResult` 数据类

### Step 4: 实现战斗流程模块 (`battle/`)
- 实现 `BattleHooks` 抽象接口
- 实现 `BattleFlow` 基类（包含标准流程框架）
- 实现 `flow.py` 状态机（阶段流转逻辑）
- 支持 `BATTLE_END_CONFIGS` 配置化检测

### Step 5: 重构 YYSBaseScript
- 使用新的 common 模块
- 保持向后兼容

### Step 6: 重构业务脚本
- 以 SoulRaidScript 为试点
- 逐步重构其他业务脚本

---

## 5. 向后兼容

### 5.1 常量兼容

`constants.py` 同时导出具体常量值和类常量：

```python
# constants.py

# ============ 具体常量值（向后兼容） ============
BATTLE_SLEEP_SHORT = 0.5
BATTLE_SLEEP_MEDIUM = 1.0
BATTLE_SLEEP_LONG = 2.0
BATTLE_VICTORY_SLEEP = 1.0
BATTLE_END_SLEEP = 2.0
BATTLE_END_CLICK_SLEEP = 0.5

DEFAULT_CLICK_RANGE = 20
BATTLE_END_CLICK_RANGE_X = 30
BATTLE_END_CLICK_RANGE_Y = 50
OCR_CLICK_RANGE = 10

# ============ 类常量（推荐使用） ============
class BattleSleep:
    SHORT = 0.5
    MEDIUM = 1.0
    LONG = 2.0
    VICTORY = 1.0
    END = 2.0
    CLICK_AFTER = 0.5
```

### 5.2 操作方法兼容

在 `YYSBaseScript` 中保留原有方法，内部调用 `ImageOperations`：

```python
# event_script_base.py

# 原有方法保持不变
def bg_left_click(self, point, x_range=20, y_range=20):
    """后台左键点击（带随机偏移）- 向后兼容方法"""
    self.mouse.bg_left_click_with_range(point, x_range=x_range, y_range=y_range)
```

新的 `ImageOperations` 类作为独立组件，不强制要求 `YYSBaseScript` 使用，
但现有方法可无缝配合使用。

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
