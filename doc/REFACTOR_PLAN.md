# 重构计划

> 生成时间: 2026-03-21
> 项目: yys-pc-script

## 一、待处理 TODO 汇总

共发现 **15** 个 TODO，分类如下：

### 1. 命名规范重构 (P0 - 高优先级)

| 文件 | TODO | 描述 |
|------|------|------|
| `yys/yuhun.py:5` | ~~修改所有项目中拼音命名~~ | ✅ 已完成 → `soul_raid.py` |
| `yys/realm_raid.py:18` | 加个config类 | 配置类规范化 |

**重构方案**：
- ~~`yuhun.py` → `soul_raid.py`，类 `YuHunScript` → `SoulRaidScript`~~ ✅ 已完成
- `douji.py` → `collect_formation.py` 或保留（待确认语义）
- 参考已完成的 `jiejietupo` → `realm_raid` 重构模式

---

### 2. 模块化/架构重构 (P1 - 中优先级)

| 文件 | TODO | 描述 |
|------|------|------|
| `yys/yuhun.py:6` | 将项目中每个脚本单独一个文件夹，图片放在脚本子文件夹下 |
| `yys/scene_manager.py:40` | 改为编程式注册 | ✅ 已完成 |
| `yys/scene_manager.py:41` | 支持图片放在功能脚本目录下 | ✅ 已完成 |
| `yys/scene_manager.py:54` | 将具体scene编写到代码枚举 |
| `yys/scene_manager.py:72` | 暴露接口注册 scene | ✅ 已完成 |
| `yys/scene_manager.py:133` | source -> dest 支持多条路径 | ✅ 已完成 |

**重构方案**：

```
yys/
├── soul_raid/              # 新目录结构
│   ├── soul_raid.py       # 主脚本
│   └── images/            # 图片资源
├── realm_raid/
│   ├── realm_raid.py
│   └── images/
├── rifts_shadows/
│   ├── rifts_shadows_script.py
│   └── images/
...
```

**SceneManager 编程式注册 API 设计**：
```python
class SceneManager:
    def register_scene(self, name: str, image_paths: List[str]):
        """注册场景"""

    def register_transition(self, from_scene: str, to_scene: str, button_path: str):
        """注册场景跳转"""

    def register_global_transition(self, to_scene: str, button_path: str):
        """注册通用跳转按钮"""
```

---

### 3. 功能增强 (P2 - 中优先级)

| 文件 | TODO | 描述 |
|------|------|------|
| `yys/event_script_base.py:133` | 支持只接收勾协（accept_wq_type = 2） | ✅ 已完成枚举扩展 |
| `yys/douji.py:50` | 检测上方是否有绿色标记 |
| `yys/rifts_shadows/rifts_shadows_script.py:182` | 识别已击破 |
| `yys/exploration.py:17` | 图片匹配增加场景条件 |

**重构方案**：
- `WantedQuestAcceptType` 枚举扩展：
  ```python
  class WantedQuestAcceptType(IntEnum):
      REFUSE = 0
      ACCEPT_ALL = 1
      ACCEPT_GOUGU = 2  # 只接勾协
  ```

---

### 4. 技术债务清理 (P1 - 中优先级)

| 文件 | TODO | 描述 |
|------|------|------|
| `yys/common_util.py:12` | 重构并删除common_util |
| `win_util/image.py:180` | 不依赖 hwnd，hwnd 抽到 WinController |
| `win_util/image.py:291` | return 最好封装为对象 | ✅ 已完成 |
| `win_util/ocr.py:29` | 优化性能 |

**重构方案**：

#### common_util.py 清理
- `bg_find_pic` → 使用 `WinController.find_image()`
- `bg_find_pic_with_timeout` → 使用 `WinController.find_image_with_timeout()`
- `try_handle_battle_end` → 迁移到 `YYSBaseScript` 或 `WinController`
- `try_bg_click_pic_with_timeout` → 迁移到 `WinController`
- 删除 `common_util.py`

#### ImageFinder 封装优化 ✅ 已完成
- 添加 `ImageMatchResult` 数据类
- 添加 `find_image()` 和 `find_image_by_cache()` 方法
- 导出到 `win_util` 包

---

## 二、重构优先级排序

```
P0 (立即处理):
├── ~~yuhun.py 拼音命名重构~~ ✅ 已完成

P1 (计划内):
├── ~~模块化: soul_raid/realm_raid/yuling~~ ✅ 已完成
├── 技术债务: common_util 清理（部分完成：event_script_base.py 已迁移）
├── 技术债务: ImageFinder 返回值封装 ✅ 已完成
└── SceneManager: 编程式注册 API ✅ 已完成

P2 (后续迭代):
├── 功能: 勾协接受类型扩展（枚举完成，OCR检测待完善）
├── 功能: 绿色标记检测
├── 功能: 已击破识别
└── 性能: OCR 优化
```

---

## 三、已完成的同类重构 (参考)

| 重构项 | 状态 | 提交 |
|--------|------|------|
| `jiejietupo` → `realm_raid` | ✅ 已完成 | `9dea08b` |
| `yuhun.py` → `soul_raid.py` | ✅ 已完成 | - |
| `yuhun.py/realm_raid.py/yuling.py` 模块化 | ✅ 已完成 | - |
| `SceneManager` 编程式注册 API | ✅ 已完成 | - |
| `event_script_base.py` 消除 `common_util` 依赖 | ✅ 已完成 | - |
| `ImageMatchResult` 封装 | ✅ 已完成 | - |
| `WantedQuestAcceptType` 枚举扩展 | ✅ 已完成 | - |
| `YYSBaseScript` 子类消除 `logger`/`random_sleep` 导入 | ✅ 已完成 | - |

---

## 四、执行建议

1. **命名重构** 优先完成，确保代码风格统一
2. **模块化重构** 一次性完成，避免频繁变更目录结构
3. **技术债务** 可在日常开发中逐步清理
4. 每次重构后运行 `python -m py_compile` 验证语法
