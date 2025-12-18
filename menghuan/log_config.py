from loguru import logger


def init():
    # 配置loguru日志
    logger.add(
        "logs/ghost_hunting_{time:YYYY-MM-DD}.log",  # 按日期分割日志文件
        rotation="00:00",  # 每天午夜创建新日志
        retention="7 days",  # 保留7天日志
        encoding="utf-8",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
    )