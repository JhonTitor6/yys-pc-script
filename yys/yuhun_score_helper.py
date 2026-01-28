import time

import cv2
from loguru import logger

from common_util import find_window
from win_util.image import ImageFinder
from yys.util.yys_yu_hun_ocr import YysYuHunOCR

image_finder = None


def capture_yuhun_detail_img():
    img = image_finder.update_screenshot_cache()

    x1 = 99999
    point_share = image_finder.bg_find_pic_by_cache("yys/images/yuhun_detail_share.bmp", 0, 0, 99999, 99999, 0.95)
    point_qiang_hua = image_finder.bg_find_pic_by_cache("yys/images/yuhun_qiang_hua.bmp", 0, 0, 99999, 99999, 0.95)
    if (point_share is not None and point_share != (-1, -1)) or (
            point_qiang_hua is not None and point_qiang_hua != (-1, -1)):
        x1 = 1020

    point2 = image_finder.bg_find_pic_by_cache("yys/images/yuhun_detail.bmp", 0, 0, x1, 99999, 0.95)
    if point2 is not None and point2 != (-1, -1):
        return img[point2[1] + 110:point2[1] + 236, point2[0] - 130:point2[0] + 130]
    return None


if __name__ == '__main__':
    logger.info("启动")
    hwnd = find_window()
    image_finder = ImageFinder(hwnd)

    logger.info("初始化ocr")
    yysOcr = YysYuHunOCR()
    logger.info("初始化ocr完成")

    yysOcr.set_attr_rule_4(['暴击伤害'])

    last_ocr_time = 0
    ocr_interval = 0.01  # 每0.04秒识别一次
    last_img = None
    last_result = None

    while True:
        now = time.time()

        # 只在间隔时间到时OCR一次
        if now - last_ocr_time > ocr_interval:
            last_img = capture_yuhun_detail_img(hwnd)
            last_result = yysOcr.ocr(last_img)
            last_ocr_time = now

            # 用上一次的识别结果计算分数
            if last_img is not None:
                result_img, results, total_score = yysOcr.calc_score(last_result, last_img)
                win_name = "Yuhun Score"
                cv2.namedWindow(win_name, cv2.WINDOW_GUI_NORMAL | cv2.WINDOW_NORMAL)
                cv2.resizeWindow(win_name, 262, 165)
                cv2.setWindowProperty(win_name, cv2.WND_PROP_TOPMOST, 1)
                cv2.imshow(win_name, result_img)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cv2.destroyAllWindows()
