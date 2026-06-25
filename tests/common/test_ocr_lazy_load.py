"""测试 CommonOcr 懒加载 + 向后兼容语义。"""
import sys
import pytest


def test_construct_does_not_import_easyocr(monkeypatch):
    """CommonOcr() 默认 backend=rapidocr，不应触发 easyocr import。"""
    monkeypatch.setitem(sys.modules, "easyocr", None)
    from win_util.ocr import CommonOcr
    ocr = CommonOcr()
    assert ocr._backend is None  # 懒加载：构造时不实例化


def test_construct_does_not_import_rapidocr(monkeypatch):
    """CommonOcr() 构造时不应触发 rapidocr_onnxruntime import。"""
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)
    from win_util.ocr import CommonOcr
    ocr = CommonOcr()
    assert ocr._backend is None


def test_legacy_positional_lang_list_works():
    """旧调用 CommonOcr(['ch_sim', 'en']) 不应抛 TypeError，且不被当成 reader。

    这是 YysYuHunOCR 第 35 行的实际调用方式。
    """
    from win_util.ocr import CommonOcr
    ocr = CommonOcr(['ch_sim', 'en'])  # type: ignore[arg-type]
    # lang_list 落到 _legacy_lang_list；第一个位置参数是 list（不是 reader），
    # 所以 _legacy_reader 应为 None
    assert ocr._legacy_reader is None
    assert ocr._legacy_lang_list == ['ch_sim', 'en']


def test_legacy_kwarg_lang_list_works():
    """旧调用 CommonOcr(lang_list=['ch_sim', 'en'], gpu=True) 也支持。"""
    from win_util.ocr import CommonOcr
    ocr = CommonOcr(lang_list=['ch_sim', 'en'], gpu=True)
    assert ocr._legacy_reader is None
    assert ocr._legacy_lang_list == ['ch_sim', 'en']
    assert ocr._legacy_gpu is True


def test_set_reader_injection_still_works():
    """旧测试用 set_reader(mock) 注入，行为保留。"""
    from win_util.ocr import CommonOcr
    ocr = CommonOcr()
    mock_reader = object()
    ocr.set_reader(mock_reader)
    assert ocr._backend is mock_reader


def test_get_reader_emits_deprecation_warning():
    """get_reader() 应发 DeprecationWarning。"""
    from win_util.ocr import CommonOcr
    ocr = CommonOcr()
    ocr.set_reader(object())
    with pytest.warns(DeprecationWarning, match="get_reader"):
        _ = ocr.get_reader()


def test_ocr_preserves_2x_resize_for_rapidocr(monkeypatch):
    """CommonOcr.ocr(img) 即使在 rapidocr 模式下也应做 2× 灰度放大 + 坐标缩回。

    这是 YysYuHunOCR 御魂小字识别的关键。
    """
    from win_util.ocr import CommonOcr
    import numpy as np

    # 构造一个 100x300 假图
    img = np.full((100, 300, 3), 200, dtype=np.uint8)

    # mock RapidOcrBackend，让它返回 2x 坐标的结果
    class _MockBackend:
        name = "mock-rapid"
        def __init__(self):
            self.calls = []
        def readtext(self, image, **kwargs):
            # 记录实际拿到的 image 尺寸（应该被 2x 放大）
            self.calls.append(image.shape)
            # 模拟在 2x 放大图上的识别结果
            return [
                ([[0, 0], [200, 0], [200, 40], [0, 40]], "text", 0.9),
            ]

    mock = _MockBackend()
    ocr = CommonOcr()
    ocr.set_reader(mock)  # 注入 mock
    results = ocr.ocr(img)

    # 1) backend 收到的 image 应该是 2x 放大图
    assert mock.calls[0][0] == 200  # height
    assert mock.calls[0][1] == 600  # width

    # 2) 返回的 box 应被缩回原图
    box = results[0][0]
    assert box[0] == [0, 0]
    assert box[1] == [100, 0]  # 200/2
    assert box[2] == [100, 20]  # 200/2, 40/2
    assert box[3] == [0, 20]
