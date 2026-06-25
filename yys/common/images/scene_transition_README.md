# 场景跳转资产采集说明

## 背景

`YYSBaseScript` 在 Task 1 加了 `entry_scene` 类属性，子类（如 `ExplorationScript`）通过声明该属性要求脚本启动时先跳转到指定场景。本文档描述如何人工采集所需的场景图和按钮图，让 `SceneManager.goto_scene()` 能够正确识别目标场景。

由于本任务涉及实际游戏画面截图（必须由人工操作完成），无法由 AI 子代理代为执行。本 README 作为人工执行的操作手册。

## 待采集资产清单

### 整屏场景图（放 `yys/common/images/scene/`）

| 文件名 | 描述 | 状态 |
|--------|------|------|
| `exploration_chapter_28.bmp` | 探索地图，28 章已选中状态 | TODO |
| `exploration_chapter_29.bmp` | 探索地图，29 章已选中状态 | TODO（可选） |
| `abyss_shadows_entry.bmp` | 狭间暗域入口界面 | TODO |

### 跳转按钮图（放 `yys/common/images/scene_control/`）

| 文件名 | 描述 | 状态 |
|--------|------|------|
| `exploration_to_chapter_28.bmp` | 探索地图上"第二十八章"按钮 | TODO |
| `exploration_chapter_28_to_battle.bmp` | 28 章界面上"探索"按钮 | TODO |
| `soul_to_abyss_shadows.bmp` | 御魂选择界面"狭间暗域"按钮 | TODO |

### 测试 fixture（放 `yys/exploration/images/test/scenes/`）

`yys/exploration/test_exploration_scene_transition.py` 在 `images/test/scenes/` 目录中至少需要一个 `.bmp/.png/.jpg` 文件，才会从 skip 转为可执行。

可复制以下文件到该目录：
- `yys/common/images/scene/home.bmp` → `images/test/scenes/home.bmp`
- `yys/common/images/scene/exploration.bmp` → `images/test/scenes/exploration.bmp`
- `yys/common/images/scene/exploration_chapter_28.bmp`（采集后）→ `images/test/scenes/exploration_chapter_28.bmp`

## 采集流程

### 工具
- **游戏内截图**：Windows 截图快捷键 `Win+Shift+S` 或 `Print Screen`
- **图像裁剪**：可用系统自带的"画图"或其他图像编辑工具

### 步骤

#### 1. 启动游戏
- 启动阴阳师 PC 客户端
- 进入庭院（home 界面）

#### 2. 采集整屏场景图

| 流程 | 操作 | 截屏 | 保存为 |
|------|------|------|--------|
| 2.1 | 点"探索"按钮 → 探索地图 | 整屏 | `exploration.bmp`（**已存在**） |
| 2.2 | 探索地图 → 点"第二十八章" | 整屏 | `exploration_chapter_28.bmp` |
| 2.3 | 探索地图 → 点"第二十九章"（可选） | 整屏 | `exploration_chapter_29.bmp` |
| 2.4 | 主页 → 探索 → 结界突破 | 整屏 | `barrier_breakthrough.bmp`（**已存在**） |
| 2.5 | 御魂选择 → 点"狭间暗域" | 整屏 | `abyss_shadows_entry.bmp` |

保存到 `yys/common/images/scene/`

#### 3. 采集跳转按钮图

| 流程 | 操作 | 截屏 | 保存为 |
|------|------|------|--------|
| 3.1 | 探索地图上 | 截"第二十八章"按钮位置 | `exploration_to_chapter_28.bmp` |
| 3.2 | 28 章界面上 | 截"探索"按钮位置 | `exploration_chapter_28_to_battle.bmp` |
| 3.3 | 御魂选择界面上 | 截"狭间暗域"按钮位置 | `soul_to_abyss_shadows.bmp` |

保存到 `yys/common/images/scene_control/`

> **注意**：按钮图用**局部截图**（只截按钮区域），整屏图用**全屏截图**（覆盖整个游戏窗口）。

## 验证

采集完成后，跑以下测试验证：

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest yys/exploration/test_exploration_scene_transition.py -v
```

预期：从 SKIPPED 转为 PASSED。

如果测试失败，常见原因：
- **场景图分辨率/像素不匹配**：在游戏中重新截图，确保与原图分辨率一致
- **按钮图位置错误**：检查 SceneManager 日志，看哪个 `.bmp` 没找到
- **BFS 路径不通**：检查 `yys/exploration/config/scene_transitions_exploration.json` 的 transitions 列表

## 提交

```bash
git add yys/common/images/scene/exploration_chapter_28.bmp \
        yys/common/images/scene/abyss_shadows_entry.bmp \
        yys/common/images/scene_control/exploration_to_chapter_28.bmp \
        yys/common/images/scene_control/exploration_chapter_28_to_battle.bmp \
        yys/common/images/scene_control/soul_to_abyss_shadows.bmp \
        yys/exploration/images/test/scenes/*.bmp
git commit -m "$(cat <<'EOF'
chore(assets): 补充场景跳转所需的细分场景图

新增场景图：
- exploration_chapter_28（28 章已选中状态）
- abyss_shadows_entry（狭间暗域入口界面）

新增跳转按钮图：
- exploration_to_chapter_28（探索地图-28 章入口）
- exploration_chapter_28_to_battle（28 章-探索按钮）
- soul_to_abyss_shadows（御魂-狭间暗域按钮）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

## 注意事项

- 截图时确保游戏窗口未被遮挡
- 按钮图尽量只裁剪按钮本身（不要包含周围太多背景）
- 整屏图保持全屏大小（不要缩放）
- 命名严格按上述表格，区分大小写
- 截图后请对照下表打勾，便于跟踪进度
