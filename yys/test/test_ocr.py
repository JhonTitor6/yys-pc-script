import cv2

from win_util.ocr import CommonOcr


def crop_screenshot_cache(screenshot_cache, x0=0, y0=0, x1=99999, y1=99999):
    """从截图缓存中裁剪指定区域"""
    h, w = screenshot_cache.shape[:2]
    # 限制裁剪区域在图像范围内
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(w, x1)
    y1 = min(h, y1)

    # 确保裁剪区域有效
    if x0 >= x1 or y0 >= y1:
        return screenshot_cache

    return screenshot_cache[y0:y1, x0:x1]

def test_damage_ocr():
    ocr = CommonOcr()
    img = cv2.imread("./images/test_damage_ocr.bmp")
    img = crop_screenshot_cache(img, 3, 99, 283, 143)

    # cv2.imshow("img", img)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    ocr_result = ocr.find_all_texts(img, similarity_threshold=0.2, allowlist='0123456789')
    print(ocr_result)