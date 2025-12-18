import time
from abc import abstractmethod, ABC

from loguru import logger
from pic_and_color_util import ImageMatchConfig, bg_find_pic_by_config, capture_window_region
from my_mouse import bg_left_click_with_range

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
        if debug_log:
            logger.debug(f"触发事件 [{event}]")
        if event in self.event_handler_map:
            callback = self.event_handler_map[event]
            if callback is None and debug_log:
                logger.debug(f"触发事件 [{event}] 回调为空")
                return
            callback_str = type(callback.__self__).__name__ + "." + callback.__name__
            if debug_log:
                logger.debug(f"触发事件 [{event}] 回调 [{callback_str}]")
            callback(data)


class AutoImageEventScript(ABC):
    def __init__(self):
        super().__init__()

        self.screenshot_cache = None

        self._event_manager = EventManager()
        self._image_event_match_configs: [ImageMatchConfig] = []
        self.hwnd = self.find_window()

    def _register_image_match_event(self, image_event_match_config: ImageMatchConfig, callback):
        if image_event_match_config in self._image_event_match_configs:
            self._image_event_match_configs.remove(image_event_match_config)
        self._image_event_match_configs.append(image_event_match_config)
        for target_image_path in image_event_match_config.target_image_path_list:
            self._event_manager.register_event_handler(Event(target_image_path), callback)

    def _on_event_bg_left_click(self, point):
        bg_left_click_with_range(self.hwnd, point, x_range=20, y_range=20)

    def _handle_event_from_screenshot_cache(self):
        for image_match_config in self._image_event_match_configs:
            res = bg_find_pic_by_config(self.screenshot_cache, image_match_config)
            point = res[0]
            if point is not None and point != (-1, -1):
                time.sleep(0.1)
                image_path = res[1]
                self._event_manager.trigger_event(image_path, point)
                return
        self._event_manager.trigger_event(unknown, debug_log=False)

    def _update_screenshot_cache(self):
        self.screenshot_cache = capture_window_region(self.hwnd)

    def run(self):
        while True:
            self._update_screenshot_cache()
            self._handle_event_from_screenshot_cache()
            time.sleep(0.5)

    @abstractmethod
    def find_window(self) -> str:
        pass