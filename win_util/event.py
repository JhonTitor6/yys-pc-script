import threading
import time
from abc import abstractmethod, ABC

from loguru import logger

from win_util.image import ImageFinder, ImageMatchConfig
from win_util.ocr import CommonOcr
from .mouse import bg_left_click_with_range


class Event:
    def __init__(self, event_name):
        self.name = event_name

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return self.name


unknown = Event("unknown")


class EventManager:
    def __init__(self):
        self.event_handler_map = {}

    def register_event_handler(self, event: Event, callback):
        self.event_handler_map[event] = callback

    def trigger_event(self, event: Event | str, data=None, debug_log=True):
        event = Event(event) if isinstance(event, str) else event
        if event in self.event_handler_map:
            callback = self.event_handler_map[event]
            if callback is None and debug_log:
                logger.debug(f"触发事件 [{event}] 回调为空")
                return
            callback_str = type(callback.__self__).__name__ + "." + callback.__name__
            if debug_log:
                logger.debug(f"触发事件 [{event}] 回调 [{callback_str}]")
            callback(data)
            return
        if debug_log:
            logger.debug(f"触发事件 [{event}]")


class EventBaseScript(ABC):
    def __init__(self):
        super().__init__()
        self.screenshot_cache = None

        self.hwnd = self._find_window()
        self.image_finder = ImageFinder(self.hwnd)
        self.ocr = CommonOcr()
        self._event_manager = EventManager()

        self._image_event_match_configs: [ImageMatchConfig] = []
        self._ocr_event_keywords: [str] = []

        # 脚本控制
        self._pause_threading_event = threading.Event()
        self._pause_threading_event.set()
        self._stop_threading_event = threading.Event()

    def _register_image_match_event(self, image_event_match_config: ImageMatchConfig, callback):
        if image_event_match_config in self._image_event_match_configs:
            self._image_event_match_configs.remove(image_event_match_config)
        self._image_event_match_configs.append(image_event_match_config)
        for target_image_path in image_event_match_config.target_image_path_list:
            self._event_manager.register_event_handler(Event(target_image_path), callback)

    def _register_ocr_match_event(self, keyword: str, callback):
        if keyword in self._ocr_event_keywords:
            self._ocr_event_keywords.remove(keyword)
        self._ocr_event_keywords.append(keyword)
        self._event_manager.register_event_handler(Event(keyword), callback)

    def bg_left_click(self, point, x_range=20, y_range=20):
        bg_left_click_with_range(self.hwnd, point, x_range=x_range, y_range=y_range)

    def _trigger_event_from_screenshot_cache(self):
        # 图片
        for image_match_config in self._image_event_match_configs:
            res = self.image_finder.bg_find_pic_by_config(image_match_config)
            point = res[0]
            if point is not None and point != (-1, -1):
                time.sleep(0.1)
                image_path = res[1]
                self._event_manager.trigger_event(image_path, point)
                return image_path
        # ocr
        ocr_result = self.ocr.ocr(self.screenshot_cache)
        for keyword in self._ocr_event_keywords:
            if keyword in ocr_result:
                self._event_manager.trigger_event(keyword, ocr_result)
                return keyword

        self._event_manager.trigger_event(unknown, debug_log=False)
        return None

    def pause(self):
        self._pause_threading_event.clear()

    def resume(self):
        self._pause_threading_event.set()

    def stop(self):
        logger.info("停止脚本")
        self._stop_threading_event.set()

    def pause_point(self):
        self._pause_threading_event.wait()

    def run(self):
        self.on_run()
        while not self._stop_threading_event.is_set():
            self.pause_point()
            self.before_iteration()
            self.image_finder.update_screenshot_cache()
            self._trigger_event_from_screenshot_cache()
            time.sleep(0.2)
            # 扩展点：每轮循环结束触发
            self.after_iteration()
        self._stop_threading_event.clear()

    def on_run(self):
        """Hook: called on run.
        子类可以覆写或外部注册回调使用。
        """
        pass

    def before_iteration(self):
        """Hook: called before each loop iteration.
        子类可以覆写或外部注册回调使用。
        """
        pass

    def after_iteration(self):
        """Hook: called after each loop iteration.
        子类可以覆写或外部注册回调使用。
        """
        pass

    @abstractmethod
    def _find_window(self) -> int:
        pass
