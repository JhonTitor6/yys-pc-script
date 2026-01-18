# 多脚本可配置系统设计方案与实现总结

## 1. 系统概述

我们实现了一个现代化的多脚本可配置系统，解决了原有全局 [config.DEBUG](file:///F:\Users\56440\PythonProjects\win_macro\config.py#L1-L2) 配置造成的耦合问题。

## 2. 核心组件

### 2.1 配置模型层
- **BaseScriptConfig**: 基础配置类，定义通用配置项
- **脚本专用配置**: 如 [YuHunConfig](file:///F:\Users\56440\PythonProjects\win_macro\config_system.py#L31-L35)、[TanSuoConfig](file:///F:\Users\56440\PythonProjects\win_macro\config_system.py#L37-L40) 等
- 使用 dataclass 确保类型安全和代码简洁

### 2.2 配置实体层
- **ScriptConfig**: 封装单个脚本的配置信息，提供属性访问和变更通知机制

### 2.3 配置管理层
- **ConfigManager**: 集中管理所有脚本配置
- 支持配置的注册、查询、更新和持久化
- 线程安全的配置访问
- 支持配置变更监听器

### 2.4 配置仓库层
- **ConfigRepository**: 负责配置的持久化存储
- 支持 JSON 和 YAML 格式

### 2.5 运行时上下文层
- **RuntimeContext**: 管理当前执行上下文的配置
- 使用 `ContextVar` 确保线程安全
- 提供便捷的配置访问方法

### 2.6 工具类集成
- **ConfigAwareUtilMixin**: 混入类，让工具类可以访问当前上下文配置
- 不需修改工具类构造函数

## 3. 关键特性

### 3.1 配置隔离
每个脚本拥有独立的配置实例，互不影响。

### 3.2 线程安全
使用 Python 的 `ContextVar` 和 `RLock` 确保多线程环境下的配置隔离。

### 3.3 面向对象设计
- 完全面向对象的API设计
- 便于扩展和维护
- 支持GUI集成的回调机制

### 3.4 变更通知
支持配置变更监听器，便于GUI实时更新。

### 3.5 向后兼容
保留原有功能接口，支持渐进式迁移。

### 3.6 可扩展性
易于添加新的配置项和脚本类型。

### 3.7 持久化支持
支持 JSON 和 YAML 格式的配置保存和加载。

## 4. 使用示例

### 4.1 脚本中使用配置

```python
from yys.config_manager import runtime_context, YuHunConfig


class YuHunScript:
    def __init__(self):
        runtime_context.set_current_script("御魂")
        self.config = runtime_context.get_current_config(YuHunConfig)

    def some_method(self):
        if self.config.debug:
            print("Debug info")
```

### 4.2 面向对象方式使用

```python
from yys.config_manager import config_manager

# 获取配置对象
yuhun_config = config_manager.get_config("御魂")
if yuhun_config:
    print(f"调试模式: {yuhun_config.config.debug}")

    # 更新配置
    yuhun_config.set_property("debug", True)

    # 或者使用管理器API
    config_manager.update_config("御魂", {"max_battle_count": 50})
```

### 4.3 GUI集成
```python
def on_config_change(script_name, property_name, old_value, new_value):
    print(f"{script_name}的{property_name}从{old_value}变为{new_value}")

# 添加监听器
config_manager.add_config_change_listener(on_config_change)

# 修改配置会触发回调
config_manager.update_config("御魂", {"debug": True})
```

### 4.4 工具类使用混入

```python
from yys.config_manager import ConfigAwareUtilMixin


class MyUtility(ConfigAwareUtilMixin):
    def utility_method(self):
        if self.is_debug_mode():
            # 调试逻辑
            pass
```

### 4.5 配置管理
```python
# 更新配置
config_manager.update_config("御魂", {"debug": True, "max_battle_count": 50})

# 保存配置
config_manager.save_to_file("config.json")

# 加载配置
config_manager.load_from_file("config.json")
```

## 5. 迁移指南

### 5.1 渐进式迁移
1. 保持原有 [config.DEBUG](file:///F:\Users\56440\PythonProjects\win_macro\config.py#L1-L2) 不变
2. 新功能使用新配置系统
3. 逐步替换旧配置引用
4. 最终移除全局配置依赖

### 5.2 已完成的迁移
- [event_script_base.py](file:///F:\Users\56440\PythonProjects\win_macro\yys\event_script_base.py) - 使用新配置系统
- [common_util.py](file:///F:\Users\56440\PythonProjects\win_macro\yys\common_util.py) - 使用混入类模式
- [yuhun.py](file:///F:\Users\56440\PythonProjects\win_macro\yys\yuhun.py) - 使用新配置系统

## 6. 前端集成

### 6.1 API 接口
- `GET /api/config` - 获取所有配置
- `GET /api/config/{script_name}` - 获取特定脚本配置
- `POST /api/config/{script_name}` - 更新特定脚本配置
- `POST /api/config/save` - 保存配置到文件
- `POST /api/config/load` - 从文件加载配置

### 6.2 GUI 集成能力
- 配置变更监听器支持
- 面向对象的配置访问API
- 适合未来GUI实现的架构

## 7. 优势总结

1. **解耦**: 消除了业务逻辑与全局配置的强耦合
2. **灵活性**: 每个脚本可独立配置
3. **可测试**: 配置可模拟和控制
4. **可维护**: 面向对象设计，结构清晰
5. **可视化就绪**: 支持变更通知，便于GUI实现
6. **向后兼容**: 保持原有功能
7. **线程安全**: 支持并发访问

## 8. 后续优化建议

1. 添加配置验证机制
2. 实现配置版本管理
3. 添加配置变更历史记录
4. 实现配置热更新