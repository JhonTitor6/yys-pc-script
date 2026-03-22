"""
测试日志管理系统的功能
"""

from yys.log_manager import get_logger, LoggerManager, electron_log_sink


def test_basic_logging():
    """测试基本日志功能"""
    print("测试基本日志功能...")
    
    # 获取不同脚本的日志记录器
    yuhun_logger = get_logger("yuhun")
    tansuo_logger = get_logger("tansuo")
    
    # 记录日志
    yuhun_logger.info("御魂脚本开始运行")
    yuhun_logger.debug("调试信息")
    yuhun_logger.warning("警告信息")
    yuhun_logger.error("错误信息")
    
    tansuo_logger.info("探索脚本开始运行")
    tansuo_logger.success("成功信息")
    
    print("基本日志功能测试完成")
    

def test_custom_sink():
    """测试自定义 sink 功能"""
    print("\n测试自定义 sink 功能...")
    
    # 为御魂脚本添加自定义 sink
    yuhun_manager = LoggerManager("yuhun")
    sink_id = yuhun_manager.add_custom_sink(electron_log_sink, level="INFO")
    
    yuhun_logger = get_logger("yuhun")
    yuhun_logger.info("这条日志会同时写入文件和发送到前端")
    
    # 移除自定义 sink
    yuhun_manager.remove_custom_sink(sink_id)
    
    yuhun_logger.info("这条日志只会写入文件")
    
    print("自定义 sink 功能测试完成")


def test_singleton_behavior():
    """测试单例行为"""
    print("\n测试单例行为...")
    
    logger1 = get_logger("test_script")
    logger2 = get_logger("test_script")
    logger3 = get_logger("another_script")
    
    print(f"logger1 和 logger2 是否相同: {logger1 is logger2}")
    print(f"logger1 和 logger3 是否相同: {logger1 is logger3}")
    
    logger1.info("来自 logger1 的消息")
    logger2.info("来自 logger2 的消息")
    
    print("单例行为测试完成")


if __name__ == "__main__":
    test_basic_logging()
    test_custom_sink()
    test_singleton_behavior()
    
    print("\n所有测试完成！请检查 logs 目录下的日志文件。")