# 将共用代码移动到 yys/common 目录

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `yys/` 下的共用模块（config_manager、log_manager、scene_manager）移动到 `yys/common/` 目录，统一代码组织结构。

**Architecture:** 通过文件系统移动和导入路径更新，将共用代码集中在 `yys/common/` 下，减少根目录的耦合。保持向后兼容，确保所有导入路径正确更新。

**Tech Stack:** Python 模块系统、pytest

---

## 文件结构映射

### 需要移动的文件

| 原路径 | 新路径 |
|--------|--------|
| `yys/config_manager.py` | `yys/common/config_manager.py` |
| `yys/log_manager.py` | `yys/common/log_manager.py` |
| `yys/scene_manager.py` | `yys/common/scene_manager.py` |

### 需要更新导入的文件

| 文件 | 旧导入 | 新导入 |
|------|--------|--------|
| `yys/event_script_base.py` | `from yys.scene_manager import ...` | `from yys.common.scene_manager import ...` |
| `yys/event_script_base.py` | `from yys.log_manager import ...` | `from yys.common.log_manager import ...` |
| `yys/qilingjieqi/qilingjieqi_script.py` | `from yys.log_manager import ...` | `from yys.common.log_manager import ...` |
| `yys/juexingcailiao/juexingcailiao_script.py` | `from yys.log_manager import ...` | `from yys.common.log_manager import ...` |
| `yys/guibingyanwu/guibingyanwu_script.py` | `from yys.log_manager import ...` | `from yys.common.log_manager import ...` |
| `yys/yeyuanhuo/yeyuanhuo_script.py` | `from yys.log_manager import ...` | `from yys.common.log_manager import ...` |
| `yys/qilingtancha/qilingtancha_script.py` | `from yys.log_manager import ...` | `from yys.common.log_manager import ...` |
| `yys/exploration/exploration_script.py` | `self.scene_manager.goto_scene(...)` | 无需更改（通过 event_script_base 继承） |
| `yys/rifts_shadows/rifts_shadows_script.py` | `self.scene_manager` | 无需更改（通过 event_script_base 继承） |
| `yys/realm_raid/realm_raid_script.py` | `self.scene_manager.goto_scene(...)` | 无需更改（通过 event_script_base 继承） |
| `tests/common/test_config_system.py` | `from yys.config_manager import ...` | `from yys.common.config_manager import ...` |
| `tests/common/test_log_manager.py` | `from yys.log_manager import ...` | `from yys.common.log_manager import ...` |
| `tests/common/test_scene_manager.py` | `from yys.scene_manager import ...` | `from yys.common.scene_manager import ...` |
| `yys/rifts_shadows/test_rifts_shadows_flow.py` | `SceneManager` | 无需更改（mock 方式） |

---

## Task 1: 移动 config_manager.py

**Files:**
- Move: `yys/config_manager.py` → `yys/common/config_manager.py`
- Modify: `yys/event_script_base.py` (移除导入)
- Modify: `tests/common/test_config_system.py`

- [ ] **Step 1: 移动 config_manager.py 到 common 目录**

```bash
mv yys/config_manager.py yys/common/config_manager.py
```

- [ ] **Step 2: 更新 tests/common/test_config_system.py 导入路径**

```python
# 旧
from yys.config_manager import config_manager, runtime_context, YuHunConfig, TanSuoConfig
# 新
from yys.common.config_manager import config_manager, runtime_context, YuHunConfig, TanSuoConfig
```

- [ ] **Step 3: 验证 config_manager 测试通过**

```bash
pytest tests/common/test_config_system.py -v
```

- [ ] **Step 4: 提交**

```bash
git add yys/common/config_manager.py tests/common/test_config_system.py
git rm yys/config_manager.py
git commit -m "refactor: move config_manager to yys/common/"
```

---

## Task 2: 移动 log_manager.py

**Files:**
- Move: `yys/log_manager.py` → `yys/common/log_manager.py`
- Modify: `yys/event_script_base.py`
- Modify: `yys/qilingjieqi/qilingjieqi_script.py`
- Modify: `yys/juexingcailiao/juexingcailiao_script.py`
- Modify: `yys/guibingyanwu/guibingyanwu_script.py`
- Modify: `yys/yeyuanhuo/yeyuanhuo_script.py`
- Modify: `yys/qilingtancha/qilingtancha_script.py`
- Modify: `tests/common/test_log_manager.py`

- [ ] **Step 1: 移动 log_manager.py 到 common 目录**

```bash
mv yys/log_manager.py yys/common/log_manager.py
```

- [ ] **Step 2: 更新 yys/event_script_base.py 导入路径**

检查并更新第 40 行和第 46 行的导入路径：
```python
# 旧
from yys.log_manager import get_logger
# 新
from yys.common.log_manager import get_logger
```

- [ ] **Step 3: 更新业务脚本导入路径**

```bash
# 需要更新的文件：
# yys/qilingjieqi/qilingjieqi_script.py
# yys/juexingcailiao/juexingcailiao_script.py
# yys/guibingyanwu/guibingyanwu_script.py
# yys/yeyuanhuo/yeyuanhuo_script.py
# yys/qilingtancha/qilingtancha_script.py
```

每个文件将 `from yys.log_manager import get_logger` 改为 `from yys.common.log_manager import get_logger`

- [ ] **Step 4: 更新 tests/common/test_log_manager.py 导入路径**

```python
# 旧
from yys.log_manager import get_logger, LoggerManager, electron_log_sink
# 新
from yys.common.log_manager import get_logger, LoggerManager, electron_log_sink
```

- [ ] **Step 5: 验证 log_manager 测试通过**

```bash
pytest tests/common/test_log_manager.py -v
```

- [ ] **Step 6: 提交**

```bash
git add yys/common/log_manager.py tests/common/test_log_manager.py
git add yys/event_script_base.py
git add yys/qilingjieqi/qilingjieqi_script.py
git add yys/juexingcailiao/juexingcailiao_script.py
git add yys/guibingyanwu/guibingyanwu_script.py
git add yys/yeyuanhuo/yeyuanhuo_script.py
git add yys/qilingtancha/qilingtancha_script.py
git rm yys/log_manager.py
git commit -m "refactor: move log_manager to yys/common/"
```

---

## Task 3: 移动 scene_manager.py

**Files:**
- Move: `yys/scene_manager.py` → `yys/common/scene_manager.py`
- Modify: `yys/event_script_base.py`
- Modify: `tests/common/test_scene_manager.py`
- 注意：`scene_manager.py` 中使用了 `to_project_path`，需要检查导入

- [ ] **Step 1: 移动 scene_manager.py 到 common 目录**

```bash
mv yys/scene_manager.py yys/common/scene_manager.py
```

- [ ] **Step 2: 更新 yys/event_script_base.py 导入路径**

```python
# 旧
from yys.scene_manager import SceneManager, SceneDetectionResult
# 新
from yys.common.scene_manager import SceneManager, SceneDetectionResult
```

- [ ] **Step 3: 更新 tests/common/test_scene_manager.py 导入路径**

```python
# 旧
from yys.scene_manager import SceneManager, SceneDetectionResult
# 新
from yys.common.scene_manager import SceneManager, SceneDetectionResult
```

同时需要更新 patch 路径：
```python
# 旧
@patch('yys.scene_manager.ImageFinder')
# 新
@patch('yys.common.scene_manager.ImageFinder')
```

- [ ] **Step 4: 验证 scene_manager 测试通过**

```bash
pytest tests/common/test_scene_manager.py -v
```

- [ ] **Step 5: 提交**

```bash
git add yys/common/scene_manager.py tests/common/test_scene_manager.py
git add yys/event_script_base.py
git rm yys/scene_manager.py
git commit -m "refactor: move scene_manager to yys/common/"
```

---

## Task 4: 验证所有测试通过

**Files:**
- Run: `pytest tests/ -v`

- [ ] **Step 1: 运行所有公共模块测试**

```bash
pytest tests/common/ -v
```

- [ ] **Step 2: 运行御魂模块测试**

```bash
pytest yys/soul_raid/test_soul_raid.py -v
```

- [ ] **Step 3: 验证整体功能**

```bash
pytest tests/ yys/*/test_*.py -v
```

- [ ] **Step 4: 提交最终状态**

```bash
git commit -m "chore: 完成共用代码迁移到 yys/common/"
```

---

## 验收标准

1. ✅ 所有共用模块移动到 `yys/common/` 目录
2. ✅ 所有导入路径正确更新
3. ✅ `pytest tests/common/` 测试通过
4. ✅ 御魂模块测试通过：`pytest yys/soul_raid/test_soul_raid.py -v`
5. ✅ 无遗留的旧路径导入

---

## 后续计划

此次重构完成后，可以继续：
1. 更新 `yys/common/__init__.py` 统一导出共用模块
2. 考虑为 `scene_manager` 中的图片路径也统一管理
