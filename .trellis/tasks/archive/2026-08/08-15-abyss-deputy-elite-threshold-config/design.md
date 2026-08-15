# 狭间暗域副将与精英阈值配置技术设计

## 1. Existing Data Flow

```text
AbyssShadowsConfig ConfigMeta
        ↓ get_config_schema()/ScriptRegistry
/api/scripts → GUI 通用表单 → PATCH 保存原始键
        ↓ 下一次 RunRequest
YYSBaseScript._apply_config() → self.<field>
        ↓ Main.__init__()
Enemy.target_damage → _check_current_damage() 的严格大于判断
```

公共 `_apply_config()` 已负责默认合并、范围校验和实例属性注入，本任务不新增配置解析器或脚本专属 GUI 分支。

## 2. Schema Contract

在 `AbyssShadowsConfig` 增加：

| key | label | default | min | max | hot_reloadable |
| --- | --- | ---: | ---: | ---: | --- |
| `commander_damage_limit` | 副将伤害限制 | 1 | 0 | 999999999 | false |
| `elite_damage_limit` | 精英伤害限制 | 6000000 | 0 | 999999999 | false |

- 分组、字段类型和帮助文本沿用 `boss_damage_limit`。
- `SCRIPT_META.default_config` 与 `default_registry.py` 兜底条目使用同一 snake_case 键和值。
- 非热重载与现有首领伤害限制一致：保存返回“下次启动生效”，不改变活动 run 的敌人对象。

## 3. Runtime Wiring

- `super().__init__()` 会在有无显式配置时都按 `SCRIPT_META` 注入默认后的 `self.commander_damage_limit` 与 `self.elite_damage_limit`。
- 删除 `Main.__init__()` 中两个局部硬编码变量。
- 所有副将 `Enemy` 使用 `self.commander_damage_limit`；所有精英使用 `self.elite_damage_limit`；BOSS 继续使用 `self.boss_damage_limit`。
- 不修改 `_check_current_damage()`，保持 `current_damage > target_damage`。
- 不把 `boss_count`、`commander_count`、`elite_count` 接入 `max_challenge_counts`。

## 4. Compatibility

- 旧保存配置缺少新键时，`SCRIPT_META.default_config` 和 `ConfigMeta.default` 均提供原硬编码值。
- `ScriptRegistry` 正常路径仍以类反射为准；更新 `default_registry.py` 只保证导入失败回退结果一致。
- 现有 GUI 生成控件、类型转换和保存端点保持通用逻辑。

## 5. Test Contract

- 更新现有严格字段集合断言，新增两个键及默认/范围/非热重载断言。
- 构造自定义三阈值脚本，逐类断言所有 `Enemy.target_damage`。
- 分别覆盖缺字段默认、越界拒绝、等于不退出、超过退出。
- 断言 `max_challenge_counts`、敌人数量/位置/顺序、BOSS 阈值保持原行为。

## 6. Rollback

删除两个 schema/default 字段并恢复局部硬编码即可回滚；数据库中的多余保存键在旧版本中不会被 schema 表单提交，不需要数据迁移。
