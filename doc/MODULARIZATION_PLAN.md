# 脚本模块化迁移执行计划

> 执行时间: 2026-03-21

## 迁移内容

### 1. realm_raid 模块化

**原位置：** `yys/realm_raid.py`
**新位置：** `yys/realm_raid/realm_raid_script.py`

**迁移的图片（7个）：**
- `yys/images/realm_raid_not_enough.bmp` → `yys/realm_raid/images/`
- `yys/images/realm_raid_jingong.bmp` → `yys/realm_raid/images/`
- `yys/images/realm_raid_user_realm.bmp` → `yys/realm_raid/images/`
- `yys/images/realm_raid_retry.bmp` → `yys/realm_raid/images/`
- `yys/images/realm_raid_retry_silence.bmp` → `yys/realm_raid/images/`
- `yys/images/realm_raid_refresh.bmp` → `yys/realm_raid/images/`
- `yys/images/realm_raid_refresh_confirm.bmp` → `yys/realm_raid/images/`

**保留不动的公共图片：**
- `yys/images/scene/barrier_breakthrough.bmp` - 场景图片

**新导入方式：**
```python
from yys.realm_raid import RealmRaidScript
```

### 2. yuling 模块化

**原位置：** `yys/yuling.py`
**新位置：** `yys/yuling/yuling_script.py`

**迁移的图片（1个）：**
- `yys/images/yuling_tiaozhan.bmp` → `yys/yuling/images/`

**新导入方式：**
```python
from yys.yuling import AutoYuling
```

### 3. soul_raid 模块化

**原位置：** `yys/soul_raid.py`
**新位置：** `yys/soul_raid/soul_raid_script.py`

**迁移的图片（2个）：**
- `yys/images/yuhun_tiaozhan.bmp` → `yys/soul_raid/images/`
- `yys/images/lock_accept_invitation.bmp` → `yys/soul_raid/images/`

**新导入方式：**
```python
from yys.soul_raid import SoulRaidScript, main
```

## 验证结果

- [x] 语法检查通过
- [x] 模块导入验证通过
- [x] `__init__.py` 文件已创建

## 遗留问题

1. ~~旧脚本文件已删除，需要更新所有引用旧路径的代码~~ ✅ 已完成
2. ~~CLAUDE.md 中记录的脚本路径需要更新~~ ✅ 已完成
3. ~~其他使用旧导入路径的脚本需要更新导入语句~~ ✅ 已完成

## 执行状态

| 模块 | 状态 | 完成时间 |
|------|------|----------|
| soul_raid | ✅ 已完成 | 2026-03-21 |
| realm_raid | ✅ 已完成 | 2026-03-21 |
| yuling | ✅ 已完成 | 2026-03-21 |

### 已迁移的图片

- `yys/images/realm_raid_*.bmp` → `yys/realm_raid/images/`
- `yys/images/yuhun_tiaozhan.bmp` → `yys/soul_raid/images/`
- `yys/images/lock_accept_invitation.bmp` → `yys/soul_raid/images/`
- `yys/images/yuling_tiaozhan.bmp` → `yys/yuling/images/`

### 公共图片（未迁移）

- `yys/images/scene/barrier_breakthrough.bmp` - 场景图片，保留在原位置
