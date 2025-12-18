import random
import time
from pathlib import Path

from menghuan.common_util import find_window
from menghuan.log_config import init
from my_mouse import *
from pic_and_color_util import *
import config as config

hwnd = None
config.DEBUG = True


# 捉鬼任务相关函数
def click_confirm(hwnd):
    """点击确定按钮"""
    return bg_find_pic_and_click(hwnd, "images/confirm.bmp", 760, 420, 950, 530, 0.7)


def click_receive_ghost_hunt_task(hwnd):
    """点击捉鬼任务"""
    return bg_find_pic_and_click(hwnd, "images/ghost_hunt_task.bmp", 1200, 300, 1484, 500, 0.7)


def click_auto(hwnd):
    """点击自动按钮"""
    return bg_find_pic_and_click(hwnd, "images/auto_2.bmp", 1462, 743, 1550, 861, 0.7)


def click_battle_triangle(hwnd):
    """点击战斗中的三角按钮"""
    return bg_find_pic_and_click(hwnd, "images/battle_triangle.bmp", 10, 20, 50, 70, 0.85)


def click_team(hwnd):
    """点击队伍按钮"""
    return bg_find_pic_and_click(hwnd, "images/team.bmp", 84, 168, 134, 222, 0.7)


def click_team_auto_match(hwnd):
    """点击队伍自动匹配"""
    return bg_find_pic_and_click(hwnd, "images/team_auto_match.bmp", 1000, 190, 1190, 260, 0.7)


def click_team_close(hwnd):
    """点击队伍关闭按钮"""
    return bg_find_pic_and_click(hwnd, "images/team_close.bmp", 1000, 100, 1300, 300, 0.7)


def click_zhong_kui(hwnd, similarity):
    x, y = bg_find_pic(hwnd, "images/zhong_kui.bmp", similarity=similarity)
    if x < 0 or y < 0:
        return False
    return bg_left_click(hwnd, x, y - 50)


def click_task_expand_button(hwnd):
    """点击任务展开按钮"""
    return bg_find_pic_and_click(hwnd, "images/task_expand_button.bmp", 1400, 50, 1535, 200, 0.7)


def click_task_button(hwnd):
    """点击任务按钮"""
    return bg_find_pic_and_click(hwnd, "images/task_button.bmp", 1200, 50, 1500, 200, 0.6)


def click_task_zhuo_gui_task(hwnd):
    """点击捉鬼任务"""
    return bg_find_pic_and_click(hwnd, "images/task_zhuo_gui_task.bmp", similarity=0.7)


def click_task_go_now(hwnd):
    """点击马上传送"""
    return bg_find_pic_and_click(hwnd, "images/task_go_now.bmp")


def click_task_close(hwnd):
    """点击任务关闭按钮"""
    return bg_find_pic_and_click(hwnd, "images/task_close.bmp", similarity=0.7)


def handle_battle_leave(hwnd):
    """处理战斗中的暂离"""
    if click_battle_triangle(hwnd):
        time.sleep(random.uniform(0.2, 0.5))
        if click_team(hwnd):
            time.sleep(random.uniform(0.2, 0.5))
            check_team_offline(hwnd)
            time.sleep(0.1)
            click_team_auto_match(hwnd)
            time.sleep(0.5)
            click_team_close(hwnd)


def handle_not_enough_five_man(hwnd):
    """处理不足5人"""
    if bg_find_pic(hwnd, "images/not_enough_five_man.bmp", 570, 330, 985, 550)[0] == -1:
        return False
    time.sleep(1)

    if not bg_find_pic_and_click(hwnd, "images/not_enough_five_man_cancel.bmp", 400, 330, 985, 550):
        return False
    # if not bg_find_pic_and_click(hwnd, "images/not_enough_five_man_confirm.bmp", 570, 330, 985, 550):
    #     return False
    time.sleep(1)
    click_team_auto_match(hwnd)
    time.sleep(1)
    click_team_close(hwnd)


def try_click_zhong_kui(hwnd):
    # 点击钟馗
    for i in range(5):
        similarity = 0.9 - i * 0.1
        if click_zhong_kui(hwnd, similarity):
            return True
        time.sleep(0.5)
    return False


def check_team_offline(hwnd):
    """检查队友离线状态并处理"""
    logger.debug("检查队友离线状态")
    base_x = 392
    x_interval = 163

    x_width = 150
    y_top = 500
    y_bottom = 650

    for i in range(4):
        x_offset = x_interval * (i + 1)
        x_left = base_x + x_offset
        x_right = x_left + x_width

        if bg_find_pic(hwnd, "images/team_offline.bmp", x_left, y_top, x_right, y_bottom, 0.7)[0] > 0:
            logger.warning(f"发现第{i + 1}个队友离线，正在处理...")
            bg_left_click(hwnd, 419 + x_offset, 425)
            time.sleep(1)

            if i == 0:
                bg_left_click(hwnd, 856, 420)
            elif i == 1:
                bg_left_click(hwnd, 1018, 420)
            elif i == 2:
                bg_left_click(hwnd, 752, 420)
            elif i == 3:
                bg_left_click(hwnd, 916, 420)

            time.sleep(1)


def go_to_zhuo_gui_task(hwnd):
    if click_task_expand_button(hwnd):
        time.sleep(2)
    click_task_button(hwnd)
    time.sleep(0.2)
    click_task_button(hwnd)
    time.sleep(0.5)
    # 进入任务界面
    if not click_task_zhuo_gui_task(hwnd):
        click_task_close(hwnd)
        return False
    time.sleep(0.5)
    click_task_go_now(hwnd)
    time.sleep(0.5)
    click_task_close(hwnd)
    return True



def ghost_hunting(hwnd, max_rounds):
    """捉鬼任务主循环"""
    logger.info(f"开始捉鬼任务，目标轮数（不包括正在进行中的）: {max_rounds}")
    ghost_hunting_round_count = 0

    while ghost_hunting_round_count < max_rounds:
        try:
            if bg_find_pic(hwnd, "images/continue_ghost_hunting_or_not.bmp", similarity=0.6)[0] > -1:
                if click_confirm(hwnd):
                    time.sleep(5)

            if click_receive_ghost_hunt_task(hwnd):
                ghost_hunting_round_count += 1
                logger.success(f"捉鬼任务第{ghost_hunting_round_count}轮完成 (目标: {max_rounds}轮)")
                time.sleep(1)
                go_to_zhuo_gui_task(hwnd)

            # click_auto(hwnd)
            if try_click_zhong_kui(hwnd):
                time.sleep(5)
                if click_receive_ghost_hunt_task(hwnd):
                    ghost_hunting_round_count += 1
                    logger.success(f"捉鬼任务第{ghost_hunting_round_count}轮完成 (目标: {max_rounds}轮)")
                time.sleep(1)
                go_to_zhuo_gui_task(hwnd)

            handle_battle_leave(hwnd)
            handle_not_enough_five_man(hwnd)
            click_team_close(hwnd)
            time.sleep(random.uniform(1, 3))

        except Exception as e:
            logger.exception(f"捉鬼任务出错: {e}")
            time.sleep(5)  # 出错后等待5秒再继续


def get_ghost_hunting_rounds():
    """获取用户输入的捉鬼轮数"""
    while True:
        try:
            rounds_to_hunt = 10
            rounds = int(input(f"请输入要完成的捉鬼轮数(默认{rounds_to_hunt}轮): ") or rounds_to_hunt)
            if rounds > 0:
                return rounds
            print("请输入一个正整数！")
        except ValueError:
            print("请输入有效的数字！")


def main():
    try:
        init()
        hwnd = find_window()

        # 获取用户输入的捉鬼轮数
        max_rounds = get_ghost_hunting_rounds()

        logger.info("测试找图功能...")
        bg_find_pic(hwnd, "images/enter_battle.bmp")
        logger.success("找图功能测试通过")

        ghost_hunting(hwnd, max_rounds)
    except Exception as e:
        logger.critical(f"程序发生致命错误: {str(e)}")
        raise e
    finally:
        logger.info("程序结束")


if __name__ == "__main__":
    # 确保日志目录存在
    Path("logs").mkdir(exist_ok=True)
    main()