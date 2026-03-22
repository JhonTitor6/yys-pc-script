"""
统一日志管理模块
提供结构化的日志管理功能，支持：
1. 结构化：通过参数传入 script_name 自动创建对应的日志文件夹
2. 解耦：业务代码只需调用 get_logger()，无需关注 rotation 等底层配置
3. 扩展性：提供自定义 sink 示例，预留发送日志到前端的接口
4. 上下文：利用 loguru 的 bind 功能，在每条日志中自动包含 script_name 字段
"""

from pathlib import Path
from typing import Callable

from loguru import logger


class LoggerManager:
    """
    统一日志管理器
    """
    _instances = {}

    def __new__(cls, script_name: str):
        """
        单例模式，为每个 script_name 创建唯一的 logger 实例
        
        Args:
            script_name: 脚本名称，用于创建对应的日志文件夹
        """
        if script_name not in cls._instances:
            instance = super(LoggerManager, cls).__new__(cls)
            cls._instances[script_name] = instance
            instance._initialized = False
        return cls._instances[script_name]

    def __init__(self, script_name: str):
        """
        初始化日志管理器
        
        Args:
            script_name: 脚本名称，用于创建对应的日志文件夹
        """
        if self._initialized:
            return

        self.script_name = script_name
        self.log_dir = Path("../logs") / script_name
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 创建基础 logger，绑定 script_name
        self._logger = logger.bind(script_name=script_name)

        # 添加文件处理器
        self._setup_file_sink()

        # 预留自定义 sink 接口，例如用于发送日志到前端
        self._custom_sinks = []

        self._initialized = True

    def _setup_file_sink(self):
        """
        设置文件日志处理器
        """
        log_file_path = self.log_dir / "{time:YYYY-MM-DD}.log"

        # 为避免格式错误，使用一个默认值格式化函数
        def format_record(record):
            script_name = record["extra"].get("script_name", "general")
            return "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[script_name]: <10} | {message}\n".format(
                time=record["time"],
                level=record["level"].name,
                extra={"script_name": script_name},
                message=record["message"]
            )

        self._logger.add(
            log_file_path,
            rotation="00:00",  # 每天轮换
            retention="7 days",  # 保留7天
            encoding="utf-8",
            level="DEBUG",
            format=format_record,  # 使用自定义格式化函数
            enqueue=True,  # 在多线程环境下推荐使用
            filter=self._filter_records  # 只记录当前脚本的日志
        )

    def _filter_records(self, record):
        """
        过滤日志记录，只保留当前脚本的日志
        """
        return record["extra"].get("script_name") == self.script_name

    def add_custom_sink(self, sink: Callable, level: str = "DEBUG", **kwargs):
        """
        添加自定义 sink，例如用于发送日志到前端
        
        Args:
            sink: 自定义处理函数
            level: 日志级别
            **kwargs: 其他参数
        """
        sink_id = self._logger.add(sink, level=level, **kwargs)
        self._custom_sinks.append(sink_id)
        return sink_id

    def remove_custom_sink(self, sink_id):
        """
        移除自定义 sink
        
        Args:
            sink_id: 由 add_custom_sink 返回的 sink ID
        """
        if sink_id in self._custom_sinks:
            self._logger.remove(sink_id)
            self._custom_sinks.remove(sink_id)

    def get_logger(self):
        """
        获取配置好的 logger 实例
        
        Returns:
            loguru.logger: 配置好的 logger 实例
        """
        return self._logger


# 全局日志获取函数，供业务代码使用
def get_logger(script_name: str = "default"):
    """
    获取日志实例的便捷函数
    
    Args:
        script_name: 脚本名称，默认为 "default"
        
    Returns:
        loguru.logger: 配置好的 logger 实例
    """
    manager = LoggerManager(script_name)
    return manager.get_logger()


# 示例：自定义 sink 函数，用于发送日志到前端
def electron_log_sink(message):
    """
    示例自定义 sink 函数，用于将日志发送到 Electron 前端
    这里只是一个示例，实际实现需要根据具体前端通信方式调整
    
    Args:
        message: loguru 格式的消息对象
    """
    # 这里可以实现向 Electron 前端发送日志的逻辑
    # 例如通过 WebSocket 或 IPC 通道发送
    formatted_message = message.record
    script_name = formatted_message["extra"].get("script_name", "unknown")
    level = formatted_message["level"].name
    content = formatted_message["message"]
    timestamp = formatted_message["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    # 示例：打印到控制台，实际应该发送给前端
    print(f"[Frontend Log] {timestamp} | {level} | {script_name} | {content}")


# 使用示例
if __name__ == "__main__":
    # 获取不同脚本的日志记录器
    yuhun_logger = get_logger("yuhun")
    tansuo_logger = get_logger("tansuo")

    # 记录日志
    yuhun_logger.info("御魂脚本开始运行")
    tansuo_logger.info("探索脚本开始运行")

    # 为特定脚本添加自定义 sink
    yuhun_manager = LoggerManager("yuhun")
    yuhun_manager.add_custom_sink(electron_log_sink, level="INFO")

    yuhun_logger.info("这条日志会同时写入文件和发送到前端")
