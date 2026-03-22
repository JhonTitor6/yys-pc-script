# SceneManager 优化：场景图片分散到各模块目录

## 背景

当前所有场景图片和跳转按钮图片都集中在 `yys/images/scene/` 和 `yys/images/scene/scene_control/` 下，SceneManager 通过硬编码路径自动扫描加载。这导致：
- 模块和其场景图片分离，不便于维护
- 添加新模块时需要在根目录下放图片，而不是在模块自己的目录中

## 目标

1. 全局共享场景图片迁移到 `yys/common/images/scene/`
2. 模块专属场景图片迁移到各模块的 `images/scene/` 目录
3. SceneManager 改为模块自行注册，不再自动扫描文件系统
4. 各模块脚本中直接引用的场景图片路径也需同步更新

## 当前场景图片分类

### 全局共享（→ `yys/common/images/scene/` + `scene_control/`）

**场景图片（在 `yys/images/scene/` 下）：**
- `home.bmp` — 庭院
- `battling.bmp` — 战斗中
- `exploration.bmp` — 探索页面
- `soul_selection.bmp` — 御魂选择
- `soul_level_selection.bmp` — 御魂关卡选择
- `barrier_breakthrough.bmp` — 结界突破

**跳转按钮（在 `yys/images/scene/scene_control/` 下）：**
- `home_to_exploration.bmp` — 庭院→探索
- `exploration_to_barrier_breakthrough.bmp` — 探索→结界突破
- `exploration_to_soul.bmp` — 探索→御魂
- `exploration_to_awakening_materials.bmp` — 探索→觉醒材料
- `exploration_to_regional_demon_boss.bmp` — 探索→地域鬼王
- `exploration_to_spirit_guardian.bmp` — 探索→式神守护
- `to_home.bmp` — 通用回庭院
- `return.bmp` — 返回按钮

### rifts_shadows 模块专属（→ `yys/rifts_shadows/images/scene/` + `scene_control/`）

**场景图片：**
- `rifts_shadows_selection.bmp`
- `rifts_shadows_dragon.bmp`
- `rifts_shadows_hakuzosu.bmp`
- `rifts_shadows_panther.bmp`
- `rifts_shadows_peacock.bmp`
- `rifts_shadows_enemy_selection.bmp`

**跳转按钮：**
- `rifts_shadows_selection_to_rifts_shadows_dragon.bmp`
- `rifts_shadows_selection_to_rifts_shadows_hakuzosu.bmp`
- `rifts_shadows_selection_to_rifts_shadows_panther.bmp`
- `rifts_shadows_selection_to_rifts_shadows_peacock.bmp`

### 发现的问题：battle_end 路径错误

`rifts_shadows_script.py` 引用了 `yys/images/scene/battle_end*.bmp`，但这些文件**不在** `yys/images/scene/` 下，实际在 `yys/images/` 根目录。这是一个已存在的路径错误，本次一并修复（改为 `yys/images/battle_end*.bmp`）。

> 注意：`yys/images/` 根目录下的 `battle_end*.bmp`、`ready.bmp`、`jia_cheng*.bmp`、`invite_jieshou.bmp`、`xuanshangfengyin_*.bmp` 等是全局事件图片，**不属于场景管理范畴**，本次不动它们的位置，只修正引用路径。

## 实施步骤

### 步骤 1：创建目录并迁移图片文件

创建目录结构：
```
yys/common/images/scene/           ← 全局场景图片
yys/common/images/scene_control/   ← 全局跳转按钮
yys/rifts_shadows/images/scene/    ← rifts_shadows 场景图片
yys/rifts_shadows/images/scene_control/  ← rifts_shadows 跳转按钮
```

迁移文件：
- `yys/images/scene/{home,battling,exploration,soul_selection,soul_level_selection,barrier_breakthrough}.bmp` → `yys/common/images/scene/`
- `yys/images/scene/scene_control/*.bmp` → `yys/common/images/scene_control/`
- `yys/images/scene/rifts_shadows_*.bmp` → `yys/rifts_shadows/images/scene/`
- `yys/images/scene/scene_control/rifts_shadows_*.bmp` → `yys/rifts_shadows/images/scene_control/`

### 步骤 2：修改 SceneManager — 移除自动扫描，提供加载目录的 API

在 `scene_manager.py` 中：

1. **移除** `_load_scenes_from_filesystem()` 方法（第121-167行）
2. **移除** `__init__` 中的 `auto_load_from_filesystem` 参数和相关逻辑（第47行参数、第73-78行）
3. **新增** `register_scenes_from_directory(scene_dir: str, control_dir: str)` 方法：
   - 接收一个模块的 `images/scene/` 和 `images/scene_control/` 路径
   - 复用现有的文件扫描和命名解析逻辑（提取场景名、解析 `_to_` 跳转命名）
   - 将发现的场景和跳转注册到 SceneManager
4. `click_return()` 中的硬编码路径 `yys/images/scene/scene_control/return.bmp` 改为 `yys/common/images/scene_control/return.bmp`（通过 `to_project_path`）
5. 更新类文档字符串

### 步骤 3：在各模块脚本中注册场景

在 `event_script_base.py`（`YYSBaseScript.__init__`）中：
- 创建 SceneManager 时设置 `auto_load_from_filesystem=False`
- 调用 `register_scenes_from_directory()` 注册全局场景：
  ```python
  self.scene_manager = SceneManager(self.hwnd, self.image_finder, auto_load_from_filesystem=False)
  self.scene_manager.register_scenes_from_directory(
      to_project_path("yys/common/images/scene/"),
      to_project_path("yys/common/images/scene_control/")
  )
  ```

在 `rifts_shadows_script.py` 的 `__init__` 中，注册自己的场景：
```python
self.scene_manager.register_scenes_from_directory(
    to_project_path("yys/rifts_shadows/images/scene/"),
    to_project_path("yys/rifts_shadows/images/scene_control/")
)
```

### 步骤 4：更新各模块中硬编码的场景图片路径

| 文件 | 当前路径 | 新路径 |
|------|----------|--------|
| `rifts_shadows_script.py:145` | `yys/images/scene/rifts_shadows_selection.bmp` | `yys/rifts_shadows/images/scene/rifts_shadows_selection.bmp` |
| `rifts_shadows_script.py:150` | `yys/images/scene/rifts_shadows_enemy_selection.bmp` | `yys/rifts_shadows/images/scene/rifts_shadows_enemy_selection.bmp` |
| `rifts_shadows_script.py:175` | `yys/images/scene/battling.bmp` | `yys/common/images/scene/battling.bmp` |
| `rifts_shadows_script.py:180` | `yys/images/scene/battle_end_success.bmp` | `yys/images/battle_end_success.bmp` ← 修正路径 |
| `rifts_shadows_script.py:184` | `yys/images/scene/battle_end_loss.bmp` | `yys/images/battle_end_loss.bmp` ← 修正路径 |
| `rifts_shadows_script.py:188` | `yys/images/scene/battle_end.bmp` | `yys/images/battle_end.bmp` ← 修正路径 |
| `realm_raid_script.py:29` | `yys/images/scene/barrier_breakthrough.bmp` | `yys/common/images/scene/barrier_breakthrough.bmp` |
| `scene_manager.py:367` | `yys/images/scene/scene_control/return.bmp` | `yys/common/images/scene_control/return.bmp` |

### 步骤 5：更新测试

- 更新 `tests/common/test_scene_manager.py`：
  - 移除文件系统自动加载相关的 mock 测试（`test_scene_manager_initialization`、`test_programmatic_then_filesystem`）
  - 添加 `register_scenes_from_directory()` 的测试
- 检查 `yys/rifts_shadows/test_rifts_shadows_flow.py`（当前使用 Mock SceneManager，路径不变的话不需改）

### 步骤 6：清理旧目录

确认所有引用已迁移后：
- 删除 `yys/images/scene/` 目录（包括 `scene_control/`）

## 验证

1. ✅ 运行所有单元测试：SceneManager 10/10 通过，全量 43 通过（7 失败为预存问题）
2. ✅ grep 确认没有代码再引用旧的 `yys/images/scene/` 路径
3. ✅ 场景图构建正确（通过测试验证）

## 进度

- [x] 步骤 1：创建目录并迁移图片文件 ✅
- [x] 步骤 2：修改 SceneManager — 移除自动扫描，提供加载目录的 API ✅
- [x] 步骤 3：在各模块脚本中注册场景 ✅
- [x] 步骤 4：更新各模块中硬编码的场景图片路径 ✅
- [x] 步骤 5：更新测试 ✅
- [x] 步骤 6：清理旧目录 ✅

**完成时间：** 2026-03-22
