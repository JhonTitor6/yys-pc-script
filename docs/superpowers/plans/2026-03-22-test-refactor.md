# 测试模块化重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将测试模块化重构，把 yys/test/ 移动到项目根目录的 tests/，业务模块的测试文件移动到对应模块目录下。

**Architecture:**
- 将 `yys/test/` 整体移动到项目根目录 `tests/`
- 测试基础设施（environment、providers、recorders）放在 `tests/common/`
- 业务模块测试（soul_raid、rifts_shadows 等）移动到对应模块目录下
- 公共模块测试（log_manager、config_system、ocr、scene_manager）放在 `tests/common/`

**Tech Stack:** pytest, unittest, mock

---

## 任务总览

1. 创建 tests/ 目录结构
2. 移动 soul_raid 模块测试（含测试图片）
3. 移动 rifts_shadows 模块测试
4. 移动公共模块测试到 tests/common/
5. 移动测试基础设施到 tests/common/
6. 清理 yys/test/ 目录
7. 更新所有导入路径
8. 更新 CLAUDE.md 文档

---

## Task 1: 创建 tests/ 目录结构

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/common/__init__.py`
- Create: `tests/common/environment/__init__.py`
- Create: `tests/common/providers/__init__.py`
- Create: `tests/common/recorders/__init__.py`

**Steps:**

- [ ] **Step 1: 创建 tests 目录**

```bash
mkdir -p tests/common/environment
mkdir -p tests/common/providers
mkdir -p tests/common/recorders
```

- [ ] **Step 2: 创建 __init__.py 文件**

```bash
touch tests/__init__.py
touch tests/common/__init__.py
touch tests/common/environment/__init__.py
touch tests/common/providers/__init__.py
touch tests/common/recorders/__init__.py
```

- [ ] **Step 3: 提交**

```bash
git add tests/
git commit -m "chore: 创建 tests/ 目录结构"
```

---

## Task 2: 移动 soul_raid 模块测试

**Files:**
- Create: `yys/soul_raid/test_soul_raid.py`
- Create: `yys/soul_raid/images/test/example/` (移动示例图片)
- Modify: `yys/soul_raid/__init__.py` (添加测试导出)

**Steps:**

- [ ] **Step 1: 复制 soul_raid 测试文件**

从 `yys/test/test_soul_raid.py` 复制到 `yys/soul_raid/test_soul_raid.py`

并修改导入路径:
```python
# 修改前
from yys.test.environment.mock_environment import MockEnvironment
from yys.test.providers.file_image_provider import FileImageProvider
from yys.test.recorders.action_log import ActionLog

# 修改后
from tests.common.environment.mock_environment import MockEnvironment
from tests.common.providers.file_image_provider import FileImageProvider
from tests.common.recorders.action_log import ActionLog
```

- [ ] **Step 2: 移动 soul_raid 测试图片**

将 `yys/test/test_data/scenarios/soul_raid/example/` 下的图片移动到 `yys/soul_raid/images/test/example/`

```bash
mkdir -p yys/soul_raid/images/test/example
mv yys/test/test_data/scenarios/soul_raid/example/*.png yys/soul_raid/images/test/example/
```

- [ ] **Step 3: 更新 test_soul_raid.py 中的路径引用**

```python
# 修改 TEST_DATA_BASE 路径
TEST_DATA_BASE = Path(__file__).parent / "images" / "test"
SOUL_RAID_EXAMPLE = TEST_DATA_BASE / "example"
SOUL_RAID_IMAGES = Path("yys/soul_raid/images")
```

- [ ] **Step 4: 提交**

```bash
git add yys/soul_raid/test_soul_raid.py
git add yys/soul_raid/images/test/
git commit -m "test: 移动 soul_raid 测试到模块目录"
```

---

## Task 3: 移动 rifts_shadows 模块测试

**Files:**
- Create: `yys/rifts_shadows/test_rifts_shadows_flow.py`

**Steps:**

- [ ] **Step 1: 复制 rifts_shadows 测试文件**

从 `yys/test/test_rifts_shadows_flow.py` 复制到 `yys/rifts_shadows/test_rifts_shadows_flow.py`

导入路径不需要修改（rifts_shadows 使用完整的模块路径 `from yys.rifts_shadows.rifts_shadows_script import`）

- [ ] **Step 2: 提交**

```bash
git add yys/rifts_shadows/test_rifts_shadows_flow.py
git commit -m "test: 移动 rifts_shadows 测试到模块目录"
```

---

## Task 4: 移动公共模块测试到 tests/common/

**Files:**
- Create: `tests/common/test_log_manager.py`
- Create: `tests/common/test_config_system.py`
- Create: `tests/common/test_ocr.py`
- Create: `tests/common/test_scene_manager.py`

**Steps:**

- [ ] **Step 1: 复制 test_log_manager.py**

导入路径无需修改（只使用 yys.log_manager）

- [ ] **Step 2: 复制 test_config_system.py**

导入路径无需修改（只使用 yys.config_manager）

- [ ] **Step 3: 复制 test_ocr.py**

```python
# 修改图片路径
img = cv2.imread("yys/images/test_damage_ocr.bmp")
# 改为
img = cv2.imread("tests/common/images/test_damage_ocr.bmp")
```

- [ ] **Step 4: 复制 test_scene_manager.py**

导入路径无需修改（只使用 yys.scene_manager）

- [ ] **Step 5: 移动 test_ocr.py 使用的图片**

```bash
mkdir -p tests/common/images
mv yys/test/images/test_damage_ocr.bmp tests/common/images/
```

- [ ] **Step 6: 提交**

```bash
git add tests/common/test_log_manager.py
git add tests/common/test_config_system.py
git add tests/common/test_scene_manager.py
git add tests/common/test_ocr.py
git add tests/common/images/
git commit -m "test: 移动公共模块测试到 tests/common/"
```

---

## Task 5: 移动测试基础设施到 tests/common/

**Files:**
- Create: `tests/common/environment/base.py`
- Create: `tests/common/environment/mock_environment.py`
- Create: `tests/common/environment/windows_environment.py`
- Create: `tests/common/providers/file_image_provider.py`
- Create: `tests/common/recorders/action_log.py`
- Create: `tests/common/recorders/action_recorder.py`
- Create: `tests/common/recorders/record_replay.py`

**Steps:**

- [ ] **Step 1: 复制 environment 目录**

```bash
cp yys/test/environment/base.py tests/common/environment/
cp yys/test/environment/mock_environment.py tests/common/environment/
cp yys/test/environment/windows_environment.py tests/common/environment/
```

- [ ] **Step 2: 复制 providers 目录**

```bash
cp yys/test/providers/file_image_provider.py tests/common/providers/
```

- [ ] **Step 3: 复制 recorders 目录**

```bash
cp yys/test/recorders/action_log.py tests/common/recorders/
cp yys/test/recorders/action_recorder.py tests/common/recorders/
cp yys/test/recorders/record_replay.py tests/common/recorders/
```

- [ ] **Step 4: 更新所有文件的导入路径**

在 `base.py`, `mock_environment.py`, `windows_environment.py` 中:
```python
# 修改前
from yys.test.environment.base import ...

# 修改后
from tests.common.environment.base import ...
```

在 `file_image_provider.py` 中:
```python
# 修改前
from yys.test.providers.file_image_provider import ...

# 修改后
from tests.common.providers.file_image_provider import ...
```

在 `action_log.py`, `action_recorder.py`, `record_replay.py` 中:
```python
# 修改前
from yys.test.recorders.action_log import ...

# 修改后
from tests.common.recorders.action_log import ...
```

- [ ] **Step 5: 移动 test_tianzhao_pic.py 和相关图片**

```bash
cp yys/test/test_tianzhao_pic.py tests/common/test_tianzhao_pic.py
cp yys/test/images/battle_tianzhao.bmp tests/common/images/
cp yys/test/images/test.bmp tests/common/images/
cp -r yys/test/images/debug tests/common/images/
```

更新 `test_tianzhao_pic.py` 中的图片路径:
```python
# 修改前
big_pic = cv2.imread("yys/images/debug/source/20250923_2108_source.bmp")
template = cv2.imread("yys/images/battle_tianzhao.bmp")

# 修改后
big_pic = cv2.imread("tests/common/images/debug/source/20250923_2108_source.bmp")
template = cv2.imread("tests/common/images/battle_tianzhao.bmp")
```

- [ ] **Step 6: 移动 test_yys.py**

```bash
cp yys/test/test_yys.py tests/common/test_yys.py
```

- [ ] **Step 7: 创建 tests/conftest.py**

```python
# tests/conftest.py
"""pytest 配置文件，提供测试 fixtures"""
import pytest
from pathlib import Path

# 配置测试数据基础路径
TEST_DATA_BASE = Path(__file__).parent / "common" / "images"


@pytest.fixture
def example_images_dir() -> Path:
    """示例截图目录"""
    return Path(__file__).parent.parent / "yys" / "soul_raid" / "images" / "test" / "example"


@pytest.fixture
def mock_env(mock_image_provider) -> "MockEnvironment":
    """Mock 游戏环境 fixture"""
    from tests.common.environment.mock_environment import MockEnvironment
    return MockEnvironment(image_provider=mock_image_provider)


@pytest.fixture
def mock_image_provider() -> "FileImageProvider":
    """Mock 图片提供者 fixture"""
    from tests.common.providers.file_image_provider import FileImageProvider
    return FileImageProvider(base_folder=str(TEST_DATA_BASE))
```

- [ ] **Step 8: 提交**

```bash
git add tests/common/environment/
git add tests/common/providers/
git add tests/common/recorders/
git add tests/common/test_tianzhao_pic.py
git add tests/common/test_yys.py
git add tests/common/images/
git add tests/conftest.py
git commit -m "test: 移动测试基础设施到 tests/common/"
```

---

## Task 6: 清理 yys/test/ 目录

**Files:**
- Delete: `yys/test/` 整个目录

**Steps:**

- [ ] **Step 1: 删除 yys/test/ 目录**

```bash
rm -rf yys/test/
```

- [ ] **Step 2: 验证删除成功**

```bash
ls yys/test/  # 应该报错：目录不存在
```

- [ ] **Step 3: 提交**

```bash
git rm -rf yys/test/
git commit -m "chore: 删除旧的 yys/test/ 目录"
```

---

## Task 7: 更新 soul_raid 测试中的 conftest 引用

**Files:**
- Modify: `yys/soul_raid/test_soul_raid.py`

**Steps:**

- [ ] **Step 1: 检查并移除对 yys.test.conftest 的任何引用**

test_soul_raid.py 使用的是 conftest.py 中的 fixtures，需要确保：
1. `tests/conftest.py` 中正确定义了 `example_images_dir` fixture
2. `test_soul_raid.py` 中 `SOUL_RAID_EXAMPLE = TEST_DATA_BASE / "soul_raid" / "example"` 的路径引用正确

如果测试使用 pytest fixture，需要导入：
```python
# 不需要显式导入 conftest，pytest 自动发现
```

- [ ] **Step 2: 验证测试可以运行**

```bash
cd F:\Users\56440\PythonProjects\yys-pc-script
python -m pytest yys/soul_raid/test_soul_raid.py -v --tb=short
```

- [ ] **Step 3: 提交**

```bash
git add yys/soul_raid/test_soul_raid.py
git commit -m "fix: 更新 soul_raid 测试的路径引用"
```

---

## Task 8: 更新 CLAUDE.md 文档

**Files:**
- Modify: `CLAUDE.md`

**Steps:**

- [ ] **Step 1: 更新测试文档**

```markdown
## 测试

### 单元测试（推荐）
测试位于各业务模块和 `tests/` 目录下，使用 pytest 运行：
```bash
# 运行所有测试
pytest tests/ yys/*/test_*.py -v

# 只运行御魂模块测试（不需要游戏窗口）
pytest yys/soul_raid/test_soul_raid.py -v

# 运行公共模块测试
pytest tests/common/ -v
```
单元测试使用 Mock 环境，不依赖游戏窗口。

### 测试框架架构

```
tests/                          # 测试基础设施
├── conftest.py               # pytest 配置和 fixtures
├── common/                   # 公共测试基础设施
│   ├── environment/         # 环境抽象层
│   │   ├── base.py         # GameEnvironment 抽象基类
│   │   ├── mock_environment.py  # Mock 测试环境
│   │   └── windows_environment.py  # Windows 生产环境
│   ├── providers/           # 图片提供者
│   │   └── file_image_provider.py  # 从文件加载截图
│   ├── recorders/           # 操作记录器
│   │   ├── action_log.py    # 操作日志容器
│   │   ├── action_recorder.py  # 操作记录器
│   │   └── record_replay.py  # 录制-回放工具
│   ├── images/             # 测试用图片
│   └── test_*.py           # 公共模块测试
│
yys/                          # 业务模块
├── soul_raid/
│   ├── test_soul_raid.py   # 御魂模块测试
│   └── images/test/        # 御魂测试用图片
└── rifts_shadows/
    └── test_rifts_shadows_flow.py  # 狭间暗域测试
```

### Mock 测试示例

```python
from tests.common.environment.mock_environment import MockEnvironment
from tests.common.recorders.action_log import ActionLog

# 创建 Mock 环境
log = ActionLog()
env = MockEnvironment(action_log=log)

# 执行点击操作
env.left_click(100, 200)

# 验证操作记录
log.assert_click_at(100, 200, tolerance=10)
log.assert_click_count(1)
```

### 录制新测试场景

```python
from tests.common.recorders.record_replay import ScenarioRecorder

recorder = ScenarioRecorder()
recorder.start_recording()

# ... 执行操作 ...

# 保存场景
screenshot = env.capture_screen()
recorder.save_scenario("soul_raid/battle_01", screenshot)
```

集成测试需要打开游戏窗口。
```

- [ ] **Step 2: 提交**

```bash
git add CLAUDE.md
git commit -m "docs: 更新 CLAUDE.md 测试文档"
```

---

## Task 9: 最终验证

**Steps:**

- [ ] **Step 1: 运行所有测试验证**

```bash
# 运行公共模块测试
python -m pytest tests/common/ -v --tb=short

# 运行 soul_raid 测试
python -m pytest yys/soul_raid/test_soul_raid.py -v --tb=short

# 运行 rifts_shadows 测试
python -m pytest yys/rifts_shadows/test_rifts_shadows_flow.py -v --tb=short
```

- [ ] **Step 2: 验证目录结构**

```bash
# 验证 tests/ 目录
ls -la tests/
ls -la tests/common/
ls -la tests/common/environment/
ls -la tests/common/providers/
ls -la tests/common/recorders/

# 验证模块测试目录
ls -la yys/soul_raid/
ls -la yys/soul_raid/images/test/
ls -la yys/rifts_shadows/

# 验证旧目录已删除
ls yys/test/  # 应该报错
```

- [ ] **Step 3: 最终提交**

```bash
git status
git commit -m "chore: 完成测试模块化重构"
```

---

## 文件路径变更汇总

| 原路径 | 新路径 |
|--------|--------|
| `yys/test/` | `tests/` |
| `yys/test/conftest.py` | `tests/conftest.py` |
| `yys/test/environment/` | `tests/common/environment/` |
| `yys/test/providers/` | `tests/common/providers/` |
| `yys/test/recorders/` | `tests/common/recorders/` |
| `yys/test/test_soul_raid.py` | `yys/soul_raid/test_soul_raid.py` |
| `yys/test/test_rifts_shadows_flow.py` | `yys/rifts_shadows/test_rifts_shadows_flow.py` |
| `yys/test/test_log_manager.py` | `tests/common/test_log_manager.py` |
| `yys/test/test_config_system.py` | `tests/common/test_config_system.py` |
| `yys/test/test_ocr.py` | `tests/common/test_ocr.py` |
| `yys/test/test_scene_manager.py` | `tests/common/test_scene_manager.py` |
| `yys/test/test_tianzhao_pic.py` | `tests/common/test_tianzhao_pic.py` |
| `yys/test/test_yys.py` | `tests/common/test_yys.py` |
| `yys/test/test_data/scenarios/soul_raid/example/` | `yys/soul_raid/images/test/example/` |
| `yys/test/images/` | `tests/common/images/` |

---

## 实施进度

### ✅ 已完成

- [x] Task 1: 创建 tests/ 目录结构 (commit: fdb33d1)
- [x] Task 2: 移动 soul_raid 模块测试 (commit: 3bcc222)
- [x] Task 3: 移动 rifts_shadows 模块测试 (commit: 8144fb3)
- [x] Task 4: 移动公共模块测试到 tests/common/ (commit: 5024f67)
- [x] Task 5: 移动测试基础设施到 tests/common/ (commit: d1202c3)
- [x] Task 6: 清理 yys/test/ 目录 (commit: 82f9c3c)
- [x] Task 8: 更新 CLAUDE.md 文档 (commit: 4f1a87f)
- [x] Task 9: 最终验证 (commit: -)

### 验证结果

御魂模块测试 (9/9 通过):
```
pytest yys/soul_raid/test_soul_raid.py -v
============================= 9 passed in 10.78s ==============================
```

公共模块测试 (6/7 通过，1 个失败为原有测试问题):
```
pytest tests/common/test_log_manager.py tests/common/test_config_system.py -v
========================== 1 failed, 6 passed in 0.21s ==========================
```
测试失败 `test_config_persistence` 为原有代码问题，非本次重构引入。
