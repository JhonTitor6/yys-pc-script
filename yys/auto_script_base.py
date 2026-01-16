import time

from common_util import *
from loguru import logger


class YYSAutoScript:
    """
    TODO: 使用状态机优化脚本
    阴阳师自动化脚本基类
    封装公共方法，方便编写各种副本的自动化脚本
    """

    def __init__(self, script_name, challenge_image):
        """
        初始化脚本

        Args:
            script_name: 脚本名称，用于日志记录
            challenge_image: 挑战按钮图片路径
        """
        self.script_name = script_name
        self.challenge_image = challenge_image
        self.hwnd = find_window()
        self.cur_battle_count = 0
        self.cur_battle_victory_count = 0
        self.max_battle_count = 0

        # 配置日志
        logger.add(
            f"logs/{script_name}/{{time:YYYY-MM-DD}}.log",
            rotation="00:00",
            retention="7 days",
            encoding="utf-8",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
        )

        logger.info(f"初始化{self.script_name}脚本")

    def run(self):
        """运行脚本的主循环"""
        self.max_battle_count = input_max_battle_count()

        logger.info(f"开始执行{self.script_name}，计划完成{self.max_battle_count}次战斗")

        self.on_script_start()

        while self.cur_battle_count < self.max_battle_count:
            try:
                self.click_challenge()

                # 调用特定于脚本的额外操作
                self.post_click_challenge_actions()
                handle_res, is_battle_victory = self.try_skip_battle_end()
                if handle_res:
                    self.cur_battle_count += 1
                    if is_battle_victory:
                        self.cur_battle_victory_count += 1
                    self.on_battle_end_skip_success_actions(is_battle_victory)
                    logger.success(f"{self.script_name} 通关次数：{self.cur_battle_count}/{self.max_battle_count} 胜利次数：{self.cur_battle_victory_count}")

                random_sleep(0.2, 0.5)
            except Exception as e:
                logger.exception(f"{self.script_name} 出现异常", e)
                time.sleep(3)

        logger.info(f"{self.script_name} 已完成所有战斗")
        self.on_script_end()

    def click_challenge(self):
        """点击挑战按钮的公共方法"""
        point = bg_find_pic(self.hwnd, self.challenge_image, similarity=0.8)
        return bg_left_click_with_range(self.hwnd, point, x_range=20, y_range=20)

    def post_click_challenge_actions(self):
        """
        点击挑战后的额外操作
        子类可以重写此方法添加特定逻辑
        """
        pass

    def on_battle_end_skip_success_actions(self, is_battle_victory):
        """
        成功跳过战斗结束画面后的操作
        子类可以重写此方法添加特定逻辑
        """
        pass

    def try_skip_battle_end(self):
        return try_handle_battle_end(self.hwnd)


    def on_script_start(self):
        """
        脚本启动前的准备工作
        :return:
        """
        pass

    def on_script_end(self):
        """
        脚本停止前的清理工作
        :return:
        """
        do_script_end()
