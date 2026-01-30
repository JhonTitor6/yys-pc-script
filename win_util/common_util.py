import random
import time


def random_sleep(min, max):
    sleep_seconds = random.uniform(min, max)
    # logger.debug(f"等待{sleep_seconds}秒")
    time.sleep(sleep_seconds)