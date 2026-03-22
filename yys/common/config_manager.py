"""
多脚本可配置系统
包含配置管理、运行时上下文和工具类配置访问
"""
import json
import threading
from contextvars import ContextVar
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Type, TypeVar, Callable

import yaml


@dataclass
class BaseScriptConfig:
    """基础脚本配置类"""
    debug: bool = False
    log_level: str = "INFO"
    max_battle_count: int = 20
    battle_interval_min: float = 0.5
    battle_interval_max: float = 1.0
    # 添加更多通用配置项


@dataclass
class YuHunConfig(BaseScriptConfig):
    """御魂脚本配置"""
    team_member_count: int = 4
    auto_invite: bool = True
    use_speed_up: bool = True


@dataclass
class TanSuoConfig(BaseScriptConfig):
    """探索脚本配置"""
    enable_boss_fight: bool = True
    boss_only: bool = False


@dataclass
class JieJieTuPoConfig(BaseScriptConfig):
    """借借突破配置"""
    quit_after_n_battles: int = 9
    quit_times: int = 3


T = TypeVar('T', bound=BaseScriptConfig)


class ScriptConfig:
    """脚本配置实体类，封装单个脚本的配置信息"""
    
    def __init__(self, name: str, config: BaseScriptConfig):
        self.name = name
        self.config = config
        self.listeners: list[Callable[[str, Any], None]] = []  # 配置变更监听器
    
    def update(self, updates: Dict[str, Any]):
        """更新配置并通知监听器"""
        for key, value in updates.items():
            if hasattr(self.config, key):
                old_value = getattr(self.config, key)
                setattr(self.config, key, value)
                # 通知监听器配置已更改
                self._notify_listeners(key, old_value, value)
    
    def add_listener(self, listener: Callable[[str, Any, Any], None]):
        """添加配置变更监听器"""
        self.listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[str, Any, Any], None]):
        """移除配置变更监听器"""
        if listener in self.listeners:
            self.listeners.remove(listener)
    
    def _notify_listeners(self, key: str, old_value: Any, new_value: Any):
        """通知所有监听器配置已更改"""
        for listener in self.listeners:
            listener(self.name, key, old_value, new_value)
    
    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典"""
        return asdict(self.config)
    
    def get_property(self, property_name: str) -> Any:
        """获取配置属性值"""
        return getattr(self.config, property_name, None)
    
    def set_property(self, property_name: str, value: Any):
        """设置配置属性值"""
        if hasattr(self.config, property_name):
            setattr(self.config, property_name, value)


class ConfigRepository:
    """配置仓库 - 负责配置的持久化存储"""
    
    def __init__(self, storage_format: str = "json"):
        self.storage_format = storage_format
        self.file_path = "../config/script_configs.json"
    
    def save(self, configs: Dict[str, ScriptConfig], filepath: str = None) -> bool:
        """保存配置到文件"""
        filepath = filepath or self.file_path
        try:
            configs_dict = {}
            for name, script_config in configs.items():
                configs_dict[name] = script_config.to_dict()
            
            # 确保目录存在
            import os
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            if self.storage_format.lower() == "json":
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(configs_dict, f, indent=2, ensure_ascii=False)
            elif self.storage_format.lower() == "yaml":
                with open(filepath, 'w', encoding='utf-8') as f:
                    yaml.dump(configs_dict, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            print(f"保存配置时出错: {e}")
            return False
    
    def load(self, filepath: str = None) -> Dict[str, Dict[str, Any]]:
        """从文件加载配置"""
        filepath = filepath or self.file_path
        try:
            if self.storage_format.lower() == "json":
                with open(filepath, 'r', encoding='utf-8') as f:
                    configs_dict = json.load(f)
            elif self.storage_format.lower() == "yaml":
                with open(filepath, 'r', encoding='utf-8') as f:
                    configs_dict = yaml.safe_load(f)
            else:
                return {}
            return configs_dict
        except FileNotFoundError:
            # 文件不存在时返回空字典
            return {}
        except Exception as e:
            print(f"加载配置时出错: {e}")
            return {}


class ConfigManager:
    """配置管理器 - 集中管理所有脚本配置"""
    
    def __init__(self, repository: ConfigRepository = None):
        self._configs: Dict[str, ScriptConfig] = {}
        self._lock = threading.RLock()  # 使用RLock支持递归锁定
        self.repository = repository or ConfigRepository()
        self.config_change_listeners: list[Callable[[str, str, Any, Any], None]] = []
        self._initialized = False  # 标记是否已初始化默认配置
    
    def _ensure_initialized(self):
        """确保默认配置已初始化（懒加载）"""
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._init_default_configs()
                    self._initialized = True
    
    def _init_default_configs(self):
        """初始化默认配置"""
        self.register_config("御魂", YuHunConfig())
        self.register_config("探索", TanSuoConfig())
        self.register_config("借借突破", JieJieTuPoConfig())
    
    def register_config(self, script_name: str, config: BaseScriptConfig) -> ScriptConfig:
        """注册脚本配置"""
        with self._lock:
            script_config = ScriptConfig(script_name, config)
            # 添加管理器级别的配置变更监听器
            script_config.add_listener(self._on_config_changed)
            self._configs[script_name] = script_config
            return script_config
    
    def get_config(self, script_name: str) -> Optional[ScriptConfig]:
        """获取脚本配置对象"""
        # 确保已初始化
        self._ensure_initialized()
        with self._lock:
            return self._configs.get(script_name)
    
    def get_config_values(self, script_name: str, config_type: Type[T] = BaseScriptConfig) -> T:
        """获取脚本配置值（兼容旧接口）"""
        # 确保已初始化
        self._ensure_initialized()
        with self._lock:
            script_config = self._configs.get(script_name)
            if script_config:
                return script_config.config
            # 返回默认配置
            return config_type()
    
    def update_config(self, script_name: str, updates: Dict[str, Any]) -> bool:
        """更新脚本配置"""
        # 确保已初始化
        self._ensure_initialized()
        with self._lock:
            script_config = self._configs.get(script_name)
            if script_config:
                script_config.update(updates)
                return True
            return False
    
    def get_all_configs(self) -> Dict[str, ScriptConfig]:
        """获取所有配置对象"""
        # 确保已初始化
        self._ensure_initialized()
        with self._lock:
            return self._configs.copy()
    
    def get_all_config_values(self) -> Dict[str, BaseScriptConfig]:
        """获取所有配置值（兼容旧接口）"""
        # 确保已初始化
        self._ensure_initialized()
        with self._lock:
            result = {}
            for name, script_config in self._configs.items():
                result[name] = script_config.config
            return result
    
    def save_to_file(self, filepath: str = None) -> bool:
        """保存所有配置到文件"""
        # 确保已初始化
        self._ensure_initialized()
        return self.repository.save(self._configs, filepath)
    
    def load_from_file(self, filepath: str = None):
        """从文件加载配置"""
        configs_dict = self.repository.load(filepath)
        
        with self._lock:
            for name, config_data in configs_dict.items():
                # 根据配置名称确定配置类型
                if "yuhun" in name.lower():
                    config_obj = YuHunConfig(**{k: v for k, v in config_data.items() if k in YuHunConfig.__annotations__})
                elif "tansuo" in name.lower():
                    config_obj = TanSuoConfig(**{k: v for k, v in config_data.items() if k in TanSuoConfig.__annotations__})
                elif "jiejietupo" in name.lower():
                    config_obj = JieJieTuPoConfig(**{k: v for k, v in config_data.items() if k in JieJieTuPoConfig.__annotations__})
                else:
                    config_obj = BaseScriptConfig(**{k: v for k, v in config_data.items() if k in BaseScriptConfig.__annotations__})
                
                self.register_config(name, config_obj)
    
    def add_config_change_listener(self, listener: Callable[[str, str, Any, Any], None]):
        """添加配置变更监听器（用于GUI更新等）"""
        self.config_change_listeners.append(listener)
    
    def remove_config_change_listener(self, listener: Callable[[str, str, Any, Any], None]):
        """移除配置变更监听器"""
        if listener in self.config_change_listeners:
            self.config_change_listeners.remove(listener)
    
    def _on_config_changed(self, script_name: str, key: str, old_value: Any, new_value: Any):
        """内部方法：当配置变更时调用"""
        for listener in self.config_change_listeners:
            listener(script_name, key, old_value, new_value)


class RuntimeContext:
    """运行时上下文 - 管理当前执行上下文的配置"""
    
    # 使用 ContextVar 来确保线程安全的上下文
    _current_script_name: ContextVar[Optional[str]] = ContextVar('_current_script_name', default=None)
    
    def __init__(self, manager: ConfigManager = None):
        self.config_manager = manager or self._get_global_config_manager()
    
    def _get_global_config_manager(self):
        """获取全局配置管理器实例"""
        # 为了避免循环导入，这里动态获取
        import sys
        if 'config_manager' in globals():
            return globals()['config_manager']
        elif 'config_manager' in sys.modules.get(__name__, {}):
            return sys.modules[__name__].config_manager
        else:
            # 创建一个新的实例
            return ConfigManager()
    
    def set_current_script(self, script_name: str):
        """设置当前脚本名称到上下文中"""
        self._current_script_name.set(script_name)
    
    def get_current_script(self) -> Optional[str]:
        """获取当前脚本名称"""
        return self._current_script_name.get()
    
    def get_current_config(self, config_type: Type[T] = BaseScriptConfig) -> T:
        """获取当前脚本的配置"""
        script_name = self.get_current_script()
        if script_name:
            return self.config_manager.get_config_values(script_name, config_type)
        # 如果没有设置当前脚本，则返回默认配置
        return config_type()
    
    def is_debug_mode(self) -> bool:
        """检查当前是否为调试模式"""
        config = self.get_current_config()
        return getattr(config, 'debug', False)
    
    def should_log_verbose(self) -> bool:
        """检查是否应记录详细日志"""
        config = self.get_current_config()
        return getattr(config, 'debug', False)


# 全局配置管理器实例
config_manager = ConfigManager()


class ConfigAwareUtilMixin:
    """配置感知工具类混入 - 让工具类可以读取当前脚本配置而不修改构造函数"""
    
    def get_current_config(self, config_type: Type[T] = BaseScriptConfig) -> T:
        """获取当前上下文的配置"""
        return runtime_context.get_current_config(config_type)
    
    def is_debug_mode(self) -> bool:
        """检查是否为调试模式"""
        return runtime_context.is_debug_mode()
    
    def should_log_verbose(self) -> bool:
        """检查是否应记录详细日志"""
        return runtime_context.should_log_verbose()
    
    def get_current_script_name(self) -> Optional[str]:
        """获取当前脚本名称"""
        return runtime_context.get_current_script()


# 全局运行时上下文实例
runtime_context = RuntimeContext(config_manager)