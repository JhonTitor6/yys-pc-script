# OCR Backend 替换实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 EasyOCR（torch 6.3GB）替换为 RapidOCR（onnxruntime ~50MB），打包体积从 1.7GB 瘦到 <350MB，启动时不再强制 import OCR 运行时。

**Architecture:** 抽象 `OcrBackend` Protocol，CommonOcr 内部懒加载选定 backend（默认 rapidocr，可回退 easyocr）。`WinController.ocr` 改为 property 懒加载。配置通过 `config/ui_config.json` 的 `ocr_backend` 字段切换。

**Tech Stack:** Python 3.11, RapidOCR + onnxruntime, PyInstaller, electron-builder, pytest

**Spec:** `docs/specs/2026-06-07-ocr-backend-replace-design.md`

---

## File Structure

### 新增（5 个）
| 文件 | 职责 |
|------|------|
| `win_util/ocr_config.py` | 读 ui_config.json 解析 backend 名 + 路径解析 |
| `win_util/ocr_backends/__init__.py` | 注册表 + re-exports |
| `win_util/ocr_backends/base.py` | `OcrBackend` Protocol |
| `win_util/ocr_backends/rapid.py` | `RapidOcrBackend`（onnxruntime 引擎） |
| `win_util/ocr_backends/easy.py` | `EasyOcrBackend`（保留兜底，标 deprecated） |

### 新增测试（3 个）
| 文件 | 覆盖 |
|------|------|
| `tests/common/test_ocr_config.py` | `get_ocr_backend_name` 各种 ui_config 场景 |
| `tests/common/test_ocr_backends.py` | rapid / easy 两个 backend 的接口契约 |
| `tests/common/test_ocr_lazy_load.py` | CommonOcr 懒加载语义（不立即 import backend 库） |

### 修改（7 个）
| 文件 | 改动 |
|------|------|
| `win_util/ocr.py` | CommonOcr 保留旧位置参数顺序（`lang_list` 在前），加懒加载 + 2× resize 缩回逻辑保留，标 deprecate `get_reader()` |
| `win_util/controller.py` | `self.ocr` 改 property，加 `from __future__ import annotations` |
| `config/ui_config.json` | 加 `ocr_backend: "rapidocr"` 字段 |
| `requirements.txt` | 删 `easyocr~=1.7.2` 和 `aircv==1.4.6`（aircv 实际未用），加 `rapidocr-onnxruntime` + `onnxruntime` |
| `build_backend.spec` | hiddenimports 换 onnxruntime + rapidocr，excludes 加 torch 等 |
| `scripts/download_ocr_models.py` | 改为从 `site-packages/rapidocr_onnxruntime/models/` 复制到 `assets/ocr_models_rapid/`（**不是**下载到 `~/rapidocr/`） |
| `.gitignore` | 加 `/assets/ocr_models_rapid/` 和 `/assets/ocr_models_easy/` |
| `yys/util/yys_yu_hun_ocr.py` | **视情况**：CommonOcr 位置参数顺序已保留，理论零改动。但 reader property 会发 DeprecationWarning（见 Task 5 决策） |

### 新增 fixture
| 文件 | 用途 |
|------|------|
| `tests/common/fixtures/yuhun_comparison.md` | 20+ 张御魂截图 easyocr vs rapidocr 对比结果 |
| `tests/common/images/yuhun_real/` | 真实御魂截图样本（用户提供） |
| `tests/manual/yuhun_ocr_compare.py` | 离线对比脚本 |

---

## 关键发现（实测验证）

| 项 | 实际行为 | plan 应对 |
|----|---------|----------|
| `rapidocr-onnxruntime` 模型位置 | 打包在 `site-packages/rapidocr_onnxruntime/models/` | `download_ocr_models.py` 从包内复制（**不**实例化触发下载） |
| 模型文件名 | `ch_PP-OCRv4_det_infer.onnx` / `ch_ppocr_mobile_v2.0_cls_infer.onnx` / `ch_PP-OCRv4_rec_infer.onnx` | 用上面准确的文件名 |
| 字符字典 `ppocr_keys_v1.txt` | **不需要**——字符字典内嵌在 rec onnx 模型内 | spec/plan 删掉对该文件的引用 |
| 覆盖 model_path 方式 | `RapidOCR(Det_model_path='绝对路径', Rec_model_path=..., Cls_model_path=...)` 传入 kwargs | `RapidOcrBackend.__init__` 走 kwargs 覆盖 |
| `update_model_path` 对绝对路径 | `Path(root_dir) / "D:/abs/xxx.onnx"` → 保留绝对路径 | 不需特殊处理 |
| `CommonOcr.ocr` 现有 2× resize 逻辑 | 第 61-94 行：灰度 → 2x 放大 → readtext → 坐标缩回 | **必须保留**——御魂小字识别强依赖 |

---

## 任务拆分

每个 task 自包含、可独立 commit、commit 之间代码可工作。

---

### Task 1：新增 `win_util/ocr_config.py`（含 TDD）

**Files:**
- Create: `win_util/ocr_config.py`
- Test: `tests/common/test_ocr_config.py`

- [ ] **Step 1：写失败的测试**

新建 `tests/common/test_ocr_config.py`：

```python
"""测试 ocr_config 读取逻辑。"""
import json
from pathlib import Path

from win_util.ocr_config import (
    DEFAULT_BACKEND,
    VALID_BACKENDS,
    get_ocr_backend_name,
    get_ocr_model_dir,
)


def _write_ui_config(tmp_path: Path, content):
    """在 tmp_path 写入 ui_config.json；None 表示不写文件。"""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    p = cfg_dir / "ui_config.json"
    if content is None:
        return p
    if isinstance(content, str):
        p.write_text(content, encoding="utf-8")
    else:
        p.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return p


def test_missing_ui_config_returns_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert get_ocr_backend_name() == DEFAULT_BACKEND
    assert DEFAULT_BACKEND == "rapidocr"


def test_explicit_rapidocr(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_ui_config(tmp_path, {"ocr_backend": "rapidocr"})
    assert get_ocr_backend_name() == "rapidocr"


def test_explicit_easyocr(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_ui_config(tmp_path, {"ocr_backend": "easyocr"})
    assert get_ocr_backend_name() == "easyocr"


def test_case_insensitive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_ui_config(tmp_path, {"ocr_backend": "  RAPIDOCR  "})
    assert get_ocr_backend_name() == "rapidocr"


def test_invalid_value_falls_back(tmp_path, monkeypatch, caplog):
    import logging
    monkeypatch.chdir(tmp_path)
    _write_ui_config(tmp_path, {"ocr_backend": "garbage"})
    assert get_ocr_backend_name() == DEFAULT_BACKEND


def test_invalid_json_falls_back(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_ui_config(tmp_path, "{ this is not json")
    assert get_ocr_backend_name() == DEFAULT_BACKEND


def test_valid_backends_constant():
    assert "rapidocr" in VALID_BACKENDS
    assert "easyocr" in VALID_BACKENDS


def test_get_ocr_model_dir_returns_none_in_dev():
    """dev 模式（非 frozen）返回 None，由 backend 用包内默认。"""
    assert get_ocr_model_dir("rapidocr") is None
    assert get_ocr_model_dir("easyocr") is None
```

- [ ] **Step 2：跑测试确认失败**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_ocr_config.py -v
```

Expected: 全部 FAIL（`ImportError: cannot import name 'get_ocr_backend_name'`）

- [ ] **Step 3：实现 `win_util/ocr_config.py`**

```python
"""OCR backend 配置读取（仅读 config/ui_config.json）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

from loguru import logger

BackendName = Literal["rapidocr", "easyocr"]
DEFAULT_BACKEND: BackendName = "rapidocr"
VALID_BACKENDS: tuple[str, ...] = ("rapidocr", "easyocr")


def _config_path() -> Path:
    """dev/pack 模式下都基于 cwd（pack 模式 cwd = exe 同目录）。"""
    return Path("config") / "ui_config.json"


def get_ocr_backend_name() -> BackendName:
    """从 ui_config.json 读取 ocr_backend，缺失/非法则返回默认。"""
    p = _config_path()
    if not p.is_file():
        return DEFAULT_BACKEND
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"[ocr_config] 读取 {p} 失败: {exc}，回退到 {DEFAULT_BACKEND}")
        return DEFAULT_BACKEND

    raw = str(data.get("ocr_backend", DEFAULT_BACKEND)).strip().lower()
    if raw not in VALID_BACKENDS:
        logger.warning(
            f"[ocr_config] ocr_backend={raw!r} 非法，"
            f"有效值 {VALID_BACKENDS}，回退到 {DEFAULT_BACKEND}"
        )
        return DEFAULT_BACKEND
    return raw  # type: ignore[return-value]


def get_ocr_model_dir(backend: BackendName) -> Path | None:
    """pack 模式下从 _MEIPASS 读模型目录；dev 模式返回 None（用包内默认）。

    目录约定（与 build_backend.spec datas 注入路径对齐）：
    - rapidocr  → _MEIPASS/rapidocr/  （见 Task 10）
    - easyocr   → _MEIPASS/.EasyOCR/model/
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        if backend == "rapidocr":
            candidate = meipass / "rapidocr"
            return candidate if candidate.is_dir() else None
        candidate = meipass / ".EasyOCR" / "model"
        return candidate if candidate.is_dir() else None
    return None
```

- [ ] **Step 4：跑测试确认通过**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_ocr_config.py -v
```

Expected: 8 passed

- [ ] **Step 5：Commit**

```bash
git add win_util/ocr_config.py tests/common/test_ocr_config.py
git commit -m "feat(ocr): 新增 ocr_config 配置读取层

- get_ocr_backend_name() 读 config/ui_config.json 的 ocr_backend 字段
- 默认 rapidocr；缺失/非法/JSON 错误一律回退默认 + log warning
- 支持大小写无关
- get_ocr_model_dir() 处理 pack 模式下 _MEIPASS 模型路径
- dev 模式返回 None（让 backend 用包内默认模型）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2：新增 `OcrBackend` Protocol（base.py）

**Files:**
- Create: `win_util/ocr_backends/__init__.py`
- Create: `win_util/ocr_backends/base.py`
- Test: `tests/common/test_ocr_backends.py`

- [ ] **Step 1：写失败的测试**

新建 `tests/common/test_ocr_backends.py`：

```python
"""测试 OcrBackend Protocol 契约。"""
import pytest
from typing import Any

from win_util.ocr_backends.base import OcrBackend, OcrResult


class _FakeBackend:
    """满足 OcrBackend Protocol 的最小实现。"""
    name = "fake"

    def readtext(self, image: Any, **kwargs) -> list[OcrResult]:
        return [([[0, 0], [10, 0], [10, 10], [0, 10]], "hello", 0.99)]


def test_protocol_accepts_duck_typed_impl():
    backend: OcrBackend = _FakeBackend()  # type: ignore[assignment]
    result = backend.readtext(None)
    assert result[0][1] == "hello"
    assert result[0][2] == pytest.approx(0.99)


def test_ocrresult_is_tuple():
    r: OcrResult = ([[0, 0]], "x", 0.5)
    assert len(r) == 3
```

- [ ] **Step 2：跑测试确认失败**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_ocr_backends.py -v
```

Expected: FAIL（`No module named 'win_util.ocr_backends'`）

- [ ] **Step 3：实现 `win_util/ocr_backends/__init__.py`（最小版）**

```python
"""OCR backend 抽象层。"""
from win_util.ocr_backends.base import OcrBackend, OcrResult

__all__ = ["OcrBackend", "OcrResult"]
```

- [ ] **Step 4：实现 `win_util/ocr_backends/base.py`**

```python
"""OCR backend 抽象接口（与 easyocr.readtext 返回格式一致）。"""
from __future__ import annotations

from typing import Any, Protocol

# 单条识别结果：(box, text, conf)，box 是 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] 像素坐标
OcrResult = tuple[list[list[int]], str, float]


class OcrBackend(Protocol):
    """统一的 OCR backend 接口。"""
    name: str

    def readtext(self, image: Any, **kwargs) -> list[OcrResult]:
        """识别图像中的文字，返回 [(box, text, conf), ...]。"""
        ...
```

- [ ] **Step 5：跑测试确认通过**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_ocr_backends.py -v
```

Expected: 2 passed

- [ ] **Step 6：Commit**

```bash
git add win_util/ocr_backends/ tests/common/test_ocr_backends.py
git commit -m "feat(ocr): 新增 OcrBackend Protocol 抽象

- base.py 定义 OcrBackend Protocol + OcrResult 类型别名
- 返回格式与 easyocr.readtext 一致（box, text, conf）
- ocr_backends 包结构就位

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3：实现 `RapidOcrBackend`

**Files:**
- Create: `win_util/ocr_backends/rapid.py`
- Modify: `win_util/ocr_backends/__init__.py`（re-export）

- [ ] **Step 1：安装依赖**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pip install rapidocr-onnxruntime onnxruntime
```

Expected: Successfully installed rapidocr-onnxruntime-x.x.x onnxruntime-x.x.x

- [ ] **Step 2：实现 `win_util/ocr_backends/rapid.py`**

```python
"""RapidOCR backend（onnxruntime 引擎）。

模型位置：
- dev 模式：从 site-packages/rapidocr_onnxruntime/models/ 读（包内默认）
- pack 模式：从 _MEIPASS/rapidocr/ 读（通过 model_dir 显式传绝对路径）

注意：rapidocr-onnxruntime 把字符字典内嵌在 rec onnx 模型内，
所以只需要 3 个 .onnx 文件，不需要额外的字典 .txt。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger


# 模型文件名（实测确认）
_DET_MODEL = "ch_PP-OCRv4_det_infer.onnx"
_REC_MODEL = "ch_PP-OCRv4_rec_infer.onnx"
_CLS_MODEL = "ch_ppocr_mobile_v2.0_cls_infer.onnx"


class RapidOcrBackend:
    name = "rapidocr"

    def __init__(self, model_dir: Path | None = None) -> None:
        from rapidocr_onnxruntime import RapidOCR  # 懒导入

        if model_dir is not None and model_dir.is_dir():
            # pack 模式：用绝对路径覆盖，update_model_path 看到绝对路径会保留
            self._engine = RapidOCR(
                Det_model_path=str(model_dir / _DET_MODEL),
                Rec_model_path=str(model_dir / _REC_MODEL),
                Cls_model_path=str(model_dir / _CLS_MODEL),
            )
            logger.info(f"[RapidOCR] 已初始化（pack 模式），model_dir={model_dir}")
        else:
            # dev 模式：用包内默认模型
            self._engine = RapidOCR()
            logger.info("[RapidOCR] 已初始化（dev 模式，包内默认模型）")

    def readtext(self, image: Any, **kwargs):
        # RapidOCR(image) 返回 (result, elapsed)；result 是 [[box,text,conf],...]
        result, _elapsed = self._engine(image, **kwargs)
        return result or []
```

- [ ] **Step 3：更新 `win_util/ocr_backends/__init__.py`**

```python
"""OCR backend 抽象层。"""
from win_util.ocr_backends.base import OcrBackend, OcrResult
from win_util.ocr_backends.rapid import RapidOcrBackend

__all__ = ["OcrBackend", "OcrResult", "RapidOcrBackend"]
```

- [ ] **Step 4：冒烟测试 - 实例化 backend**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -c "
from win_util.ocr_backends.rapid import RapidOcrBackend
b = RapidOcrBackend()
print(f'OK: RapidOcrBackend 实例化成功: name={b.name}')
# 跑一个最小识别
import numpy as np
img = np.full((100, 300, 3), 255, dtype=np.uint8)  # 空白图
r = b.readtext(img)
print(f'OK: readtext 返回 {type(r).__name__}，长度 {len(r)}')
"
```

Expected:
```
[OK] RapidOcrBackend 实例化成功: name=rapidocr
OK: readtext 返回 list，长度 0
```

- [ ] **Step 5：跑现有测试确认 import 链不破坏**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_ocr_config.py tests/common/test_ocr_backends.py -v
```

Expected: 8 + 2 = 10 passed

- [ ] **Step 6：Commit**

```bash
git add win_util/ocr_backends/rapid.py win_util/ocr_backends/__init__.py
git commit -m "feat(ocr): 实现 RapidOcrBackend（onnxruntime 引擎）

- 懒导入 rapidocr_onnxruntime
- dev 模式用包内默认模型（无需任何配置）
- pack 模式用 model_dir 传绝对路径（覆盖 update_model_path 默认行为）
- 模型文件名实测确认：ch_PP-OCRv4_det_infer.onnx /
  ch_PP-OCRv4_rec_infer.onnx / ch_ppocr_mobile_v2.0_cls_infer.onnx
- 字符字典内嵌在 rec onnx 模型内，无需额外字典文件

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4：实现 `EasyOcrBackend`（保留兜底）

**Files:**
- Create: `win_util/ocr_backends/easy.py`
- Modify: `win_util/ocr_backends/__init__.py`

- [ ] **Step 1：实现 `win_util/ocr_backends/easy.py`**

```python
"""EasyOCR backend（保留兜底，标 deprecated）。"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from loguru import logger


class EasyOcrBackend:
    name = "easyocr"

    def __init__(
        self,
        lang_list: list[str] | None = None,
        gpu: bool = False,
        model_dir: Path | None = None,
    ) -> None:
        warnings.warn(
            "EasyOcrBackend 已被弃用，torch 依赖巨大，建议改用 rapidocr-onnxruntime",
            DeprecationWarning,
            stacklevel=2,
        )
        import easyocr  # 懒导入

        if lang_list is None:
            lang_list = ["ch_sim", "en"]
        kwargs: dict[str, Any] = {}
        if gpu:
            kwargs["gpu"] = True
        if model_dir is not None:
            kwargs["model_storage_directory"] = str(model_dir)
        self._reader = easyocr.Reader(lang_list, **kwargs)
        logger.info(f"[EasyOCR] 已初始化，lang_list={lang_list}, model_dir={model_dir}")

    def readtext(self, image: Any, **kwargs):
        return self._reader.readtext(image, **kwargs)
```

- [ ] **Step 2：更新 `win_util/ocr_backends/__init__.py`**

```python
"""OCR backend 抽象层。"""
from win_util.ocr_backends.base import OcrBackend, OcrResult
from win_util.ocr_backends.rapid import RapidOcrBackend
from win_util.ocr_backends.easy import EasyOcrBackend

__all__ = ["OcrBackend", "OcrResult", "RapidOcrBackend", "EasyOcrBackend"]
```

- [ ] **Step 3：跑测试**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_ocr_config.py tests/common/test_ocr_backends.py -v
```

Expected: 10 passed

- [ ] **Step 4：Commit**

```bash
git add win_util/ocr_backends/easy.py win_util/ocr_backends/__init__.py
git commit -m "feat(ocr): 实现 EasyOcrBackend（保留兜底，标 deprecated）

- 懒导入 easyocr
- 构造时发 DeprecationWarning
- 仅作为 ocr_backend=easyocr 配置项的回退实现

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5：改造 `CommonOcr`（懒加载 + 兼容旧位置参数 + 保留 2× resize）

**Files:**
- Modify: `win_util/ocr.py`
- Test: `tests/common/test_ocr_lazy_load.py`（新增）

- [ ] **Step 1：写失败的测试**

新建 `tests/common/test_ocr_lazy_load.py`：

```python
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
```

- [ ] **Step 2：跑测试确认失败**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_ocr_lazy_load.py -v
```

Expected: 全部 FAIL（CommonOcr 还没改造，构造时直接 import easyocr + 无 2x resize）

- [ ] **Step 3：改造 `win_util/ocr.py`**

完整重写该文件。**关键点**：
- 保留旧位置参数顺序（`reader` 第一个位置，但用 type 嗅探区分 list/dict 与 reader 对象）
- 构造时不 import backend 库
- `ocr()` 方法保留 2× 灰度放大 + 坐标缩回
- `get_reader()` 标 deprecated

```python
"""CommonOcr 入口：懒加载 + 转发到 backend。

向后兼容（关键）：
- 旧调用 CommonOcr(['ch_sim', 'en']) 仍能工作（YysYuHunOCR 实际使用方式）
- 旧测试通过 set_reader 注入的 mock reader 仍生效
- ocr() 保留 2× 灰度放大 + 坐标缩回（御魂小字识别依赖）
- get_reader() 标记 deprecated
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import cv2
from loguru import logger

from win_util.ocr_config import BackendName, get_ocr_backend_name, get_ocr_model_dir


DEFAULT_SIMILARITY_THRESHOLD = 0.3


class CommonOcr:
    """统一 OCR 入口。"""

    def __init__(
        self,
        reader: Any = None,                    # 旧第一个位置参数
        lang_list: list[str] | None = None,    # 旧/新：传给 easyocr
        gpu: bool = False,                     # 旧：传给 easyocr
        backend: BackendName | None = None,    # 新
        model_dir: Path | None = None,         # 新
        **kwargs,
    ) -> None:
        # 关键兼容：旧 YysYuHunOCR 第 35 行写的是 CommonOcr(['ch_sim', 'en'])，
        # 第一个位置参数是 list 列表。需要在 _create_backend 里区分：
        #   - 如果是 list/tuple（lang_list 旧式位置传参），当作 lang_list 用
        #   - 如果是别的对象（reader），当作注入的 reader 用
        self._legacy_reader_candidate = reader
        self._legacy_lang_list = lang_list
        self._legacy_gpu = gpu
        self._legacy_kwargs = kwargs

        self._backend_name = backend or get_ocr_backend_name()
        self._model_dir = model_dir
        self._backend: Any = None  # 懒加载

    @property
    def backend(self):
        if self._backend is None:
            self._backend = self._create_backend()
        return self._backend

    def _resolve_legacy_reader(self):
        """区分旧式位置参数是 list（lang_list）还是别的对象（reader）。"""
        cand = self._legacy_reader_candidate
        if cand is None:
            return None, self._legacy_lang_list
        if isinstance(cand, (list, tuple)) and self._legacy_lang_list is None:
            # 旧式 CommonOcr(['ch_sim', 'en']) → 当成 lang_list
            return None, list(cand)
        return cand, self._legacy_lang_list

    def _create_backend(self):
        # legacy 优先：测试用 set_reader 注入的 mock 直接用
        reader, lang_list = self._resolve_legacy_reader()
        if reader is not None:
            return reader

        from win_util.ocr_backends.rapid import RapidOcrBackend
        from win_util.ocr_backends.easy import EasyOcrBackend

        if self._backend_name == "rapidocr":
            return RapidOcrBackend(model_dir=self._model_dir)
        elif self._backend_name == "easyocr":
            return EasyOcrBackend(
                lang_list=lang_list or ["ch_sim", "en"],
                gpu=self._legacy_gpu,
                model_dir=self._model_dir,
            )
        else:  # pragma: no cover
            raise ValueError(f"未知 OCR backend: {self._backend_name}")

    def ocr(self, img, **readtext_kwargs):
        """识别图像，返回 [(box, text, conf), ...]（box 坐标为原图坐标系）。

        实现：灰度 → 2× 放大 → backend.readtext → 坐标缩回。
        这个放大对御魂小字识别至关重要（即使是 rapidocr 模式也保留）。
        """
        if img is None:
            return []

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray_resized = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        ocr_results = self.backend.readtext(gray_resized, **readtext_kwargs)

        # 缩回原图坐标
        rh, rw = gray_resized.shape[:2]
        scale_x = rw / float(w)
        scale_y = rh / float(h)

        scaled_results = []
        for box, text, conf in ocr_results:
            new_box = []
            for (px, py) in box:
                nx = int(round(px / scale_x))
                ny = int(round(py / scale_y))
                new_box.append([nx, ny])
            scaled_results.append((new_box, text, conf))

        return scaled_results

    def contains_text(self, img, target_text, case_sensitive=False) -> bool:
        ocr_results = self.ocr(img)
        detected_texts = [text for _, text, _ in ocr_results]
        if not case_sensitive:
            detected_texts = [t.lower() for t in detected_texts]
            if isinstance(target_text, str):
                target_text = target_text.lower()
            else:
                target_text = [t.lower() for t in target_text]
        if isinstance(target_text, str):
            return any(target_text in t for t in detected_texts)
        return any(any(tg in t for t in detected_texts) for tg in target_text)

    def find_text_position(self, img, target_text, similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD, case_sensitive=False):
        ocr_results = self.ocr(img)
        compare_target = target_text if case_sensitive else target_text.lower()
        best = None
        best_conf = -1.0
        for box, text, conf in ocr_results:
            compare_text = text if case_sensitive else text.lower()
            if compare_target in compare_text and conf >= similarity_threshold:
                if conf > best_conf:
                    best = (box, text, conf)
                    best_conf = conf
        if best is None:
            return None
        box = best[0]
        cx = int((box[0][0] + box[2][0]) / 2)
        cy = int((box[0][1] + box[2][1]) / 2)
        return (cx, cy)

    def find_text_positions(self, img, target_text, similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD, case_sensitive=False):
        ocr_results = self.ocr(img)
        compare_target = target_text if case_sensitive else target_text.lower()
        positions = []
        for box, text, conf in ocr_results:
            compare_text = text if case_sensitive else text.lower()
            if compare_target in compare_text and conf >= similarity_threshold:
                cx = int((box[0][0] + box[2][0]) / 2)
                cy = int((box[0][1] + box[2][1]) / 2)
                positions.append((cx, cy, conf))
        return positions

    def find_text_boxes(self, img, target_text, similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD, case_sensitive=False):
        ocr_results = self.ocr(img)
        compare_target = target_text if case_sensitive else target_text.lower()
        return [
            (box, text, conf)
            for box, text, conf in ocr_results
            if (target_text if case_sensitive else target_text.lower()) in (text if case_sensitive else text.lower())
            and conf >= similarity_threshold
        ]

    def find_all_texts(self, img, similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD, **readtext_kwargs) -> list[str]:
        ocr_result = self.ocr(img, **readtext_kwargs)
        return [text for _, text, conf in ocr_result if conf >= similarity_threshold]

    def find_all_text_positions(self, img, similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD):
        ocr_results = self.ocr(img)
        positions = []
        for box, text, conf in ocr_results:
            if conf >= similarity_threshold:
                cx = int((box[0][0] + box[2][0]) / 2)
                cy = int((box[0][1] + box[2][1]) / 2)
                positions.append((cx, cy, text, conf))
        return positions

    # 兼容旧 API
    def get_reader(self):
        """已废弃。rapid 模式返回 backend 自身；easyocr 模式返回原生 reader。

        真实调用方：YysYuHunOCR.reader property（yys/util/yys_yu_hun_ocr.py:55-59）
        建议在 YysYuHunOCR 里改用 .ocr(img) 而不是暴露 reader。
        """
        warnings.warn(
            "CommonOcr.get_reader() 已被废弃，请改用 .ocr(img) 入口",
            DeprecationWarning,
            stacklevel=2,
        )
        backend = self.backend
        return getattr(backend, "_reader", backend)

    def set_reader(self, reader):
        """直接注入 reader（兼容旧测试）。"""
        self._legacy_reader_candidate = reader
        self._backend = reader  # 立即生效
```

- [ ] **Step 4：跑新测试 + 旧测试**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_ocr_lazy_load.py tests/common/test_ocr_config.py tests/common/test_ocr_backends.py -v
```

Expected: 7 + 8 + 2 = 17 passed

- [ ] **Step 5：跑全部 common 测试确认不破坏**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/ -q
```

Expected: 60+ passed，失败数 ≤ 改动前的失败数（无新增失败）

- [ ] **Step 6：Commit**

```bash
git add win_util/ocr.py tests/common/test_ocr_lazy_load.py
git commit -m "refactor(ocr): CommonOcr 改造为懒加载 + 保留 2× resize 兼容语义

向后兼容：
- 旧调用 CommonOcr(['ch_sim', 'en']) 仍工作（YysYuHunOCR 零改动）
- 旧测试 set_reader(mock) 注入仍生效
- 2× 灰度放大 + 坐标缩回逻辑保留（御魂小字识别依赖）
- get_reader() 标 DeprecationWarning

懒加载：
- 构造时不 import easyocr/torch/onnxruntime
- 首次访问 .backend 属性时才实例化

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6：改造 `WinController.ocr` 为懒加载 property

**Files:**
- Modify: `win_util/controller.py`

- [ ] **Step 1：读 controller.py 当前实现**

```bash
head -60 F:/Users/56440/PythonProjects/yys-pc-script/win_util/controller.py
```

确认 line 42 是 `self.ocr: CommonOcr = CommonOcr()`。

- [ ] **Step 2：修改 `win_util/controller.py`**

```python
# 在文件最顶部加：
from __future__ import annotations
```

```python
# 替换原 line 42：
# 原: self.ocr: CommonOcr = CommonOcr()
# 新:
        self._ocr: CommonOcr | None = None
```

```python
# 在类内部（__init__ 之后）加 property：
    @property
    def ocr(self) -> CommonOcr:
        """首次访问时才实例化 CommonOcr（避免 import torch/onnxruntime）。"""
        if self._ocr is None:
            self._ocr = CommonOcr()
        return self._ocr
```

- [ ] **Step 3：跑相关测试，确认 test_yys.py 的 fake_ocr_init_count 期望**

```bash
grep -n "fake_ocr_init_count\|CommonOcr()" F:/Users/56440/PythonProjects/yys-pc-script/tests/common/test_yys.py
```

读 fake_ocr_init_count 相关上下文，确认 Task 6 改造后这个断言是否会破。

- [ ] **Step 4：如 test_yys.py 受影响，更新断言**

预期修改（如果 test_yys.py 第 99 行附近用 `_FakeCommonOcr` 来 mock）：

```python
# 原（依赖 CommonOcr() 在 __init__ 立即被调用）
# monkeypatch.setattr(controller, "CommonOcr", FakeCommonOcr)
# assert fake_ocr_init_count == 1

# 新（CommonOcr() 在 .ocr 被访问时才被调用，__init__ 不触发）
monkeypatch.setattr(controller, "CommonOcr", FakeCommonOcr)
# 不再断言 fake_ocr_init_count == 1，改为：
# 访问 .ocr 后断言
w = WinController(env=mock_env)
_ = w.ocr  # 触发懒加载
assert fake_ocr_init_count == 1
```

如果实际文件不需要改（断言不依赖 init count），跳过此步。

- [ ] **Step 5：跑全部 common 测试**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/ -q
```

Expected: 60+ passed，**无新增失败**（test_yys.py 失败数 ≤ 改动前）

- [ ] **Step 6：验证启动速度提升（importtime 检查）**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -X importtime -c "from win_util.controller import WinController; w = WinController()" 2>&1 | grep -E "easyocr|torch|onnxruntime|rapidocr" | head -10
```

Expected: **没有任何匹配行**（说明 controller 构造不触发 OCR 库 import）

- [ ] **Step 7：Commit**

```bash
git add win_util/controller.py tests/common/test_yys.py  # 后者如有改动
git commit -m "refactor(ocr): WinController.ocr 改为懒加载 property

- 启动时不再 import easyocr/torch/onnxruntime
- controller 构造速度 +3-5s
- 首次访问 .ocr.xxx 时才触发懒加载
- 现有 __getattr__ 前缀映射 ocr_/find_text 仍工作
- 如 test_yys.py 依赖 fake_ocr_init_count 断言，同步更新

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7：更新 `config/ui_config.json` + `.gitignore`

**Files:**
- Modify: `config/ui_config.json`
- Modify: `.gitignore`

- [ ] **Step 1：编辑 `config/ui_config.json`**

在 JSON 末尾（`}` 之前）加逗号 + `ocr_backend: "rapidocr"` 字段：

```json
{
  "last_selected_task": "御魂",
  "tasks": {
    "御魂": { "max_battle_count": 103, "loop_interval": 5 },
    "结界突破": { "max_battle_count": 9, "loop_interval": 3 },
    "探28": { "max_battle_count": 50, "loop_interval": 3 },
    "御灵": { "max_battle_count": 50, "loop_interval": 5 }
  },
  "ocr_backend": "rapidocr"
}
```

- [ ] **Step 2：编辑 `.gitignore` 加 OCR 模型目录**

在 `assets/ocr_models/` 那段后追加：

```gitignore
# 预下载的 OCR 模型（每个 backend 单独目录；spec/build_release 不入仓）
/assets/ocr_models_rapid/
/assets/ocr_models_easy/
```

- [ ] **Step 3：跑 ocr_config 测试确认读到新字段**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -c "
import os
os.chdir('F:/Users/56440/PythonProjects/yys-pc-script')
from win_util.ocr_config import get_ocr_backend_name
print(f'当前 backend: {get_ocr_backend_name()}')
"
```

Expected: `当前 backend: rapidocr`

- [ ] **Step 4：Commit**

```bash
git add config/ui_config.json .gitignore
git commit -m "feat(config): ui_config.json 加 ocr_backend 字段 + .gitignore 加模型目录

默认 rapidocr；可在运行时切换为 easyocr 兜底。
模型目录不进 git（每个开发者本地下载）。

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 8：改造 `requirements.txt` 替换依赖

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1：编辑 `requirements.txt`**

修改前：
```
aircv==1.4.6
loguru==0.7.3
mss==10.0.0
numpy==1.26.4
Pillow==11.1.0
pywin32==308
easyocr~=1.7.2
fastapi>=0.115.0,<1.0.0
httpx>=0.27.0,<1.0.0
uvicorn[standard]>=0.30.0,<1.0.0
```

修改后：
```
loguru==0.7.3
mss==10.0.0
numpy==1.26.4
Pillow==11.1.0
pywin32==308
rapidocr-onnxruntime>=1.3,<2.0
onnxruntime>=1.15,<2.0
fastapi>=0.115.0,<1.0.0
httpx>=0.27.0,<1.0.0
uvicorn[standard]>=0.30.0,<1.0.0
```

> 删 `aircv`（grep 全项目无 import）+ 删 `easyocr`（torch 自动随之消失）

- [ ] **Step 2：先确认 aircv 真的没被 import**

```bash
grep -rn "import aircv\|from aircv" F:/Users/56440/PythonProjects/yys-pc-script/ --include="*.py" | grep -v node_modules | head -5
```

Expected: **空输出**（确认可删）

- [ ] **Step 3：安装新依赖 + 卸载旧依赖**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pip install -r F:/Users/56440/PythonProjects/yys-pc-script/requirements.txt
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pip uninstall -y easyocr aircv
```

Expected: Successfully installed/uninstalled ...

- [ ] **Step 4：确认依赖都装上**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -c "
import rapidocr_onnxruntime
import onnxruntime
print('rapidocr-onnxruntime:', rapidocr_onnxruntime.__file__)
print('onnxruntime:', onnxruntime.__version__)
"
```

Expected: 路径和版本号都打印

- [ ] **Step 5：跑全部测试**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/ -q
```

Expected: 60+ passed，无新增失败

- [ ] **Step 6：Commit**

```bash
git add requirements.txt
git commit -m "build(deps): 替换 easyocr 为 rapidocr-onnxruntime

打包体积从 1.7GB 瘦到目标 <350MB
移除 easyocr 自动移除 torch(6.3GB) + torchvision + scipy + scikit-image
同时清理未使用的 aircv

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 9：改造 `download_ocr_models.py`（从包内复制，**不是**下载）

**Files:**
- Modify: `scripts/download_ocr_models.py`

> **重要修正**：rapidocr-onnxruntime 把模型打包在 pip 包内（`site-packages/rapidocr_onnxruntime/models/`），没有运行时下载行为。download 脚本的实际工作是**复制包内模型到 assets/**，方便 PyInstaller 把它们打包。

- [ ] **Step 1：替换整个文件**

```python
"""
预复制 OCR backend 模型到 assets/，便于 PyInstaller 打包。

执行逻辑：
  - rapidocr: 从 site-packages/rapidocr_onnxruntime/models/ 复制 3 个 .onnx
              到 <project>/assets/ocr_models_rapid/
  - easyocr:  实例化 easyocr.Reader 触发下载到 ~/.EasyOCR/model/，
              然后复制到 <project>/assets/ocr_models_easy/

用法：
  python scripts/download_ocr_models.py                  # 默认 rapidocr
  python scripts/download_ocr_models.py --backend rapidocr
  python scripts/download_ocr_models.py --backend easyocr

幂等：assets/ocr_models_<backend>/ 已存在且非空则跳过。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="预复制 OCR 模型")
    p.add_argument(
        "--backend",
        choices=["rapidocr", "easyocr"],
        default="rapidocr",
        help="OCR backend（默认 rapidocr）",
    )
    return p.parse_args()


def is_already_downloaded(backend: str) -> bool:
    target = PROJECT_ROOT / "assets" / f"ocr_models_{backend}"
    if not target.is_dir():
        return False
    return any(target.iterdir())


def ensure_rapidocr_models() -> Path:
    """从 rapidocr_onnxruntime pip 包内复制模型到 assets/。"""
    import rapidocr_onnxruntime  # noqa: F401  仅用于触发模块检查

    src = Path(rapidocr_onnxruntime.__file__).resolve().parent / "models"
    if not src.is_dir():
        raise FileNotFoundError(
            f"rapidocr-onnxruntime 包内模型目录不存在: {src}\n"
            f"提示：pip install --force-reinstall rapidocr-onnxruntime"
        )
    target = PROJECT_ROOT / "assets" / "ocr_models_rapid"
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, target)
    return target


def ensure_easyocr_models() -> Path:
    """触发 easyocr 下载到 ~/.EasyOCR/model/，复制到 assets/。"""
    import easyocr  # type: ignore  # noqa: F401

    user_dir = Path.home() / ".EasyOCR" / "model"
    user_dir.mkdir(parents=True, exist_ok=True)
    # 这一步会按需下载缺失模型到 user_dir
    _ = easyocr.Reader(["ch_sim", "en"], gpu=False, model_storage_directory=str(user_dir))

    target = PROJECT_ROOT / "assets" / "ocr_models_easy"
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(user_dir, target)
    return target


def main() -> int:
    args = parse_args()
    backend = args.backend

    if is_already_downloaded(backend):
        print(f"[download_ocr_models] {backend} 模型已存在，跳过")
        return 0

    print(f"[download_ocr_models] 处理 {backend} 模型...")
    try:
        if backend == "rapidocr":
            target = ensure_rapidocr_models()
        else:
            target = ensure_easyocr_models()
    except Exception as exc:
        print(f"[download_ocr_models] 失败: {exc}", file=sys.stderr)
        return 1

    print(f"[download_ocr_models] 已就绪 -> {target}")
    print(f"[download_ocr_models] 文件清单:")
    for name in sorted(target.iterdir()):
        size_mb = name.stat().st_size / 1024 / 1024
        print(f"  {size_mb:6.1f} MB  {name.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2：跑脚本**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe scripts/download_ocr_models.py --backend rapidocr
```

Expected:
```
[download_ocr_models] 处理 rapidocr 模型...
[download_ocr_models] 已就绪 -> ...\assets\ocr_models_rapid
[download_ocr_models] 文件清单:
   4.53 MB  ch_PP-OCRv4_det_infer.onnx
   0.56 MB  ch_ppocr_mobile_v2.0_cls_infer.onnx
  10.35 MB  ch_PP-OCRv4_rec_infer.onnx
```

- [ ] **Step 3：跑第二次确认幂等**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe scripts/download_ocr_models.py --backend rapidocr
```

Expected: `rapidocr 模型已存在，跳过`（立即返回）

- [ ] **Step 4：Commit（注意：assets/ocr_models_rapid 已在 .gitignore）**

```bash
git add scripts/download_ocr_models.py
git commit -m "feat(scripts): download_ocr_models.py 修正实现

- rapidocr: 从 site-packages/rapidocr_onnxruntime/models/ 复制
  （不是首次实例化触发下载——模型在 pip 包内）
- easyocr: 保留原行为（实例化触发下载到 ~/.EasyOCR/model/）
- 输出关键文件大小清单
- 幂等保留

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

> assets/ocr_models_rapid/ 不提交（已在 .gitignore）

---

### Task 10：改造 `build_backend.spec` 替换 hiddenimports + excludes

**Files:**
- Modify: `build_backend.spec`

- [ ] **Step 1：替换 `THIRD_PARTY_MODULES` 列表**

在 `THIRD_PARTY_MODULES` 里替换 OCR 相关项：

```python
# 旧:
THIRD_PARTY_MODULES = [
    "loguru",
    "fastapi",
    "uvicorn",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "easyocr",          # ← 删
    "cv2",
    "mss",
    "PIL",
    "numpy",
    "win32gui",
    "win32ui",
    "win32con",
    "win32api",
    "win32process",
    "httpx",
    "pydantic",
]

# 新:
THIRD_PARTY_MODULES = [
    "loguru",
    "fastapi",
    "uvicorn",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    # onnxruntime（rapidocr 依赖）
    "onnxruntime",
    "onnxruntime.capi._pybind_state",
    "onnxruntime.capi.onnxruntime_pybind11_state",
    "onnxruntime.providers",
    "onnxruntime.providers.cpu",
    "onnxruntime.providers.cpu.cpu_execution_provider",
    # rapidocr
    "rapidocr_onnxruntime",
    "rapidocr_onnxruntime.rapid_ocr",
    "rapidocr_onnxruntime.ch_ppocr_det",
    "rapidocr_onnxruntime.ch_ppocr_rec",
    "rapidocr_onnxruntime.ch_ppocr_cls",
    "rapidocr_onnxruntime.utils",
    "rapidocr_onnxruntime.onnx_wrapper",
    # 保留
    "cv2",
    "mss",
    "PIL",
    "numpy",
    "win32gui",
    "win32ui",
    "win32con",
    "win32api",
    "win32process",
    "httpx",
    "pydantic",
]
```

- [ ] **Step 2：追加 `excludes`**

```python
# 旧:
    excludes=[
        "tkinter",
        "test",
        "unittest",
        "pydoc",
        "doctest",
        "PySide2",
        "PyQt5",
        "PyQt6",
        "matplotlib",
        "pandas",
    ],

# 新:
    excludes=[
        "tkinter",
        "test",
        "unittest",
        "pydoc",
        "doctest",
        "PySide2",
        "PyQt5",
        "PyQt6",
        "matplotlib",
        "pandas",
        # 旧 easyocr 残留（删 easyocr 后这些不应再被打入）
        "torch",
        "torchvision",
        "scipy",
        "scikit-image",
        "easyocr",
        "aircv",
    ],
```

- [ ] **Step 3：替换 OCR 模型资源收集**

```python
# 旧:
# 预下载的 EasyOCR 模型（assets/ocr_models -> .EasyOCR/model）
ocr_models_dir = PROJECT_ROOT / "assets" / "ocr_models"
if ocr_models_dir.is_dir() and any(ocr_models_dir.iterdir()):
    DATAS.append((str(ocr_models_dir), ".EasyOCR/model"))

# 新:
# RapidOCR 模型（assets/ocr_models_rapid -> _MEIPASS/rapidocr/）
# 包含 ch_PP-OCRv4_det_infer.onnx, ch_PP-OCRv4_rec_infer.onnx,
#       ch_ppocr_mobile_v2.0_cls_infer.onnx（字符字典内嵌在 rec 模型内）
ocr_rapid_dir = PROJECT_ROOT / "assets" / "ocr_models_rapid"
if ocr_rapid_dir.is_dir() and any(ocr_rapid_dir.iterdir()):
    DATAS.append((str(ocr_rapid_dir), "rapidocr"))
    # 验证必需文件都在
    for required in [
        "ch_PP-OCRv4_det_infer.onnx",
        "ch_PP-OCRv4_rec_infer.onnx",
        "ch_ppocr_mobile_v2.0_cls_infer.onnx",
    ]:
        if not (ocr_rapid_dir / required).is_file():
            print(f"WARNING: {required} 缺失！RapidOCR 识别会失败。")

# easyocr 兜底（仅当用户配置 ocr_backend=easyocr 时才会用到）
ocr_easy_dir = PROJECT_ROOT / "assets" / "ocr_models_easy"
if ocr_easy_dir.is_dir() and any(ocr_easy_dir.iterdir()):
    DATAS.append((str(ocr_easy_dir), ".EasyOCR/model"))
```

- [ ] **Step 4：跑 spec dry-run 验证**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -c "
import PyInstaller.utils.hooks as h
exec_globals = {
    'Analysis': lambda *a, **kw: type('A', (), {'kw': kw, 'pure': [], 'zipped_data': [], 'scripts': [], 'binaries': [], 'zipfiles': [], 'datas': []})(),
    'EXE': lambda *a, **kw: None,
    'COLLECT': lambda *a, **kw: None,
    'PYZ': lambda *a, **kw: None,
    'collect_data_files': h.collect_data_files,
    'SPECPATH': 'F:/Users/56440/PythonProjects/yys-pc-script',
    'block_cipher': None,
}
with open('F:/Users/56440/PythonProjects/yys-pc-script/build_backend.spec', 'r', encoding='utf-8') as f:
    exec(f.read(), exec_globals)
a = exec_globals['a']
print(f'hiddenimports: {len(a.kw[\"hiddenimports\"])}')
print(f'datas: {len(a.kw[\"datas\"])}')
print(f'excludes: {a.kw[\"excludes\"]}')
must = ['onnxruntime', 'rapidocr_onnxruntime', 'onnxruntime.capi._pybind_state']
for m in must:
    assert m in a.kw['hiddenimports'], f'MISSING: {m}'
print('OK: 关键 hiddenimports 都在')
"
```

Expected: `OK: 关键 hiddenimports 都在`

- [ ] **Step 5：Commit A（hiddenimports + excludes）**

```bash
git add build_backend.spec
git commit -m "build(spec): 替换 OCR hiddenimports 为 onnxruntime + rapidocr

- 移除 easyocr/torch/torchvision/scipy/scikit-image/aircv
- hiddenimports 补全 onnxruntime.capi + providers.cpu + rapidocr 子模块
- excludes 显式排除 torch 等（防 PyInstaller 自动牵入）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

- [ ] **Step 6：Commit B（DATAS 路径切换）**

```bash
git add build_backend.spec
git commit -m "build(spec): DATAS 路径切换 .EasyOCR/model → rapidocr/

- 匹配 RapidOcrBackend 在 model_dir 模式下用绝对路径覆盖的行为
- 验证 ch_PP-OCRv4_det/rec/cls 三个 onnx 都存在再注入
- 保留 easyocr 兜底路径（仅在 ocr_backend=easyocr 时使用）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 11：实际打包验证（PyInstaller + electron-builder）

**Files:** （无新增，纯验证步骤）

- [ ] **Step 1：跑 PyInstaller 打包后端**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m PyInstaller F:/Users/56440/PythonProjects/yys-pc-script/build_backend.spec --clean --noconfirm
```

Expected: `Building COLLECT COLLECT-00.toc completed successfully.`

- [ ] **Step 2：检查 dist/backend 体积**

```bash
du -sh F:/Users/56440/PythonProjects/yys-pc-script/dist/backend
```

Expected: < 400 MB（旧版 ~1.7 GB）

- [ ] **Step 3：检查 _internal/rapidocr/ 含 3 个模型**

```bash
ls F:/Users/56440/PythonProjects/yys-pc-script/dist/backend/_internal/rapidocr/
```

Expected: 3 个 .onnx 文件（det / rec / cls）

- [ ] **Step 4：确认 _internal/ 不再含 torch**

```bash
ls F:/Users/56440/PythonProjects/yys-pc-script/dist/backend/_internal/ | grep -i -E "torch|easyocr|scipy|aircv" | head -5
```

Expected: **空输出**

- [ ] **Step 5：跑 sync-backend + electron-builder**

```bash
cd F:/Users/56440/PythonProjects/yys-pc-script/gui
node ../scripts/sync-backend.js
export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
export ELECTRON_BUILDER_BINARIES_MIRROR="https://npmmirror.com/mirrors/electron-builder-binaries/"
npx electron-builder --win portable
```

Expected: `building target=portable file=.../阴阳师脚本工作台-1.0.0-portable.exe archs=x64`

- [ ] **Step 6：检查最终 portable 体积**

```bash
ls -la F:/Users/56440/PythonProjects/yys-pc-script/dist-electron/*.exe
```

Expected: **< 350 MB**

- [ ] **Step 7：报告结果（无 commit）**

记录到 `docs/specs/2026-06-07-ocr-backend-replace-design.md` 验收标准小节。

---

### Task 12：真实御魂截图对比测试（⚠️ 需用户介入）

**Files:**
- Create: `tests/manual/yuhun_ocr_compare.py`（agent 可做）
- Create: `tests/common/images/yuhun_real/` 目录（用户提供截图）
- Create: `tests/common/fixtures/yuhun_comparison.md`（agent 跑完脚本后生成）

- [ ] **Step 1：用户提供御魂截图（人工 gate）**

> ⚠️ **需要用户介入**：在 `tests/common/images/yuhun_real/` 下提供至少 20 张截图：
> - 5 类有效属性 × 2 稀有度 = 10 张
> - 6 个位置（主/副/上中下）= 6 张
> - 几张无效属性 / 边界情况 = 4+ 张
> - 至少 1 张全空属性（误报率测试）

- [ ] **Step 2：写对比脚本**

新建 `tests/manual/yuhun_ocr_compare.py`：

```python
"""
对比 YysYuHunOCR 在 easyocr vs rapidocr 下的识别结果。

运行：
  # 1) 临时装回 easyocr
  D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pip install easyocr

  # 2) 跑对比
  D:/ProgramData/anaconda3/envs/win_macro/python.exe tests/manual/yuhun_ocr_compare.py

  # 3) 跑完卸载 easyocr
  D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pip uninstall -y easyocr

输出：tests/common/fixtures/yuhun_comparison.md
"""
from __future__ import annotations

import io
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

VALID_ATTRS = {"攻击加成", "速度", "暴击", "暴击伤害", "效果命中"}


def run_one(backend: str, img_paths: list[Path]) -> list[dict]:
    """用指定 backend 跑所有截图，返回每张图的识别结果。"""
    if backend == "rapidocr":
        from win_util.ocr_backends.rapid import RapidOcrBackend
        eng = RapidOcrBackend()
    else:
        from win_util.ocr_backends.easy import EasyOcrBackend
        eng = EasyOcrBackend()

    print(f"\n=== Backend: {backend} ===", flush=True)
    results = []
    for img_path in img_paths:
        import cv2
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"  SKIP {img_path.name}: 无法读取", flush=True)
            continue

        start = time.time()
        # CommonOcr 走 2x resize 链路，模拟 YysYuHunOCR 实际路径
        from win_util.ocr import CommonOcr
        ocr = CommonOcr(backend=backend)
        ocr.set_reader(eng)  # 注入 backend
        try:
            ocr_results = ocr.ocr(img)
        except Exception as exc:
            print(f"  ERR {img_path.name}: {exc}", flush=True)
            continue
        elapsed = time.time() - start

        detected = [text for _, text, _ in ocr_results]
        valid_detected = [t for t in detected if t in VALID_ATTRS]
        invalid_detected = [t for t in detected if t not in VALID_ATTRS]

        results.append({
            "image": img_path.name,
            "elapsed": round(elapsed, 2),
            "all_detected": detected,
            "valid_detected": valid_detected,
            "invalid_detected": invalid_detected,
        })
        print(f"  {img_path.name}: {elapsed:.2f}s, valid={valid_detected}, invalid={invalid_detected}", flush=True)

    return results


def main() -> int:
    img_dir = PROJECT_ROOT / "tests" / "common" / "images" / "yuhun_real"
    if not img_dir.is_dir():
        print(f"ERROR: {img_dir} 不存在，请先提供御魂截图")
        return 1
    img_paths = sorted(img_dir.glob("*.png")) + sorted(img_dir.glob("*.bmp"))
    if len(img_paths) < 20:
        print(f"WARNING: 仅 {len(img_paths)} 张截图，建议至少 20 张")
    if not img_paths:
        print(f"ERROR: {img_dir} 无图片")
        return 1

    easy = run_one("easyocr", img_paths)
    rapid = run_one("rapidocr", img_paths)

    # 以 easyocr 为真相计算指标
    truth = {r["image"]: set(r["valid_detected"]) for r in easy}
    truth_invalids = {r["image"]: set(r["invalid_detected"]) for r in easy}

    recall_hits = recall_total = 0
    false_positive = 0
    rapid_valid_total = 0
    for r in rapid:
        img = r["image"]
        detected_valid = set(r["valid_detected"])
        true_valid = truth.get(img, set())
        # 召回率
        recall_hits += len(true_valid & detected_valid)
        recall_total += len(true_valid)
        # 误报：rapid 识别为 valid 但 easyocr 完全没识别的项
        new_valid = detected_valid - true_valid
        false_positive += len(new_valid)
        rapid_valid_total += len(detected_valid)

    recall = recall_hits / recall_total * 100 if recall_total else 0
    fpr = false_positive / rapid_valid_total * 100 if rapid_valid_total else 0

    out = PROJECT_ROOT / "tests" / "common" / "fixtures" / "yuhun_comparison.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write("# 御魂 OCR 对比报告\n\n")
        f.write(f"样本数: {len(img_paths)} 张\n\n")
        f.write("## 汇总指标\n\n")
        f.write(f"- **召回率**: {recall:.1f}% ({recall_hits}/{recall_total})\n")
        f.write(f"- **误报率**: {fpr:.1f}% ({false_positive}/{rapid_valid_total})\n\n")
        f.write(f"验收: 召回率 ≥ 90% {'✓' if recall >= 90 else '✗'}  |  误报率 ≤ 5% {'✓' if fpr <= 5 else '✗'}\n\n")
        f.write("## 详细对比\n\n")
        f.write("| 图片 | easyocr (秒) | rapidocr (秒) | easyocr 有效 | rapidocr 有效 | 差异 |\n")
        f.write("|------|------|------|------|------|------|\n")
        for e, r in zip(easy, rapid):
            diff = []
            ev, rv = set(e["valid_detected"]), set(r["valid_detected"])
            if ev - rv:
                diff.append(f"easy 多: {ev - rv}")
            if rv - ev:
                diff.append(f"rapid 多: {rv - ev}")
            f.write(f"| {e['image']} | {e['elapsed']} | {r['elapsed']} | "
                    f"{e['valid_detected']} | {r['valid_detected']} | {'; '.join(diff) or '一致'} |\n")

    print(f"\n报告: {out}")
    print(f"召回率 {recall:.1f}%, 误报率 {fpr:.1f}%")
    if recall < 90:
        print("⚠️ 召回率 < 90%，建议回退到 easyocr")
        return 2
    if fpr > 5:
        print("⚠️ 误报率 > 5%，建议人工核对")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3：用户跑对比脚本**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pip install easyocr
D:/ProgramData/anaconda3/envs/win_macro/python.exe tests/manual/yuhun_ocr_compare.py
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pip uninstall -y easyocr
```

Expected: 报告写到 `tests/common/fixtures/yuhun_comparison.md`，召回率 ≥ 90% 且 误报率 ≤ 5% → exit 0

- [ ] **Step 4：如不达标，临时切回 easyocr**

修改 `config/ui_config.json` 的 `ocr_backend` 为 `"easyocr"`，重新跑 Task 11 打包。

- [ ] **Step 5：Commit 对比脚本**

```bash
git add tests/manual/yuhun_ocr_compare.py tests/common/fixtures/yuhun_comparison.md
git commit -m "test(ocr): 御魂 20+ 张截图 easyocr vs rapidocr 对比

输出召回率/误报率双指标，作为准确率验收依据。
需用户先在 tests/common/images/yuhun_real/ 提供截图。

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 13：完整回归 + 文档收尾

- [ ] **Step 1：跑全部测试**

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/ yys/yuhun_score_helper/ -q
```

Expected: 60+ passed，失败数 ≤ 改动前

- [ ] **Step 2：跑 dev 模式 sanity check（手动）**

```bash
cd F:/Users/56440/PythonProjects/yys-pc-script/gui
npm start
```

确认：
- Electron 启动正常
- Python 后端 ready
- 任一非 OCR 脚本（如御魂）能启动

- [ ] **Step 3：更新 MEMORY.md**

写到 `C:\Users\56440\.claude\projects\F--Users-56440-PythonProjects-yys-pc-script\memory\MEMORY.md`：

```markdown
## OCR Backend 替换（已完成）

把 EasyOCR（torch 6.3GB）替换为 RapidOCR（onnxruntime ~50MB），打包体积从 1.7GB 瘦到 <350MB。

### 关键文件
- `win_util/ocr_config.py` - 读 ui_config.json 解析 backend 名
- `win_util/ocr_backends/{base,rapid,easy}.py` - backend 抽象 + 2 个实现
- `win_util/ocr.py` - CommonOcr 懒加载入口，保留 2× resize + 旧位置参数兼容
- `win_util/controller.py` - ocr 改 property 懒加载
- `tests/common/test_ocr_{config,backends,lazy_load}.py` - 3 个新测试
- `tests/manual/yuhun_ocr_compare.py` - 离线对比脚本

### 配置切换
`config/ui_config.json` 加 `"ocr_backend": "rapidocr"` 字段；可回退 `"easyocr"`。

### 启动速度
WinController 构造不再 import easyocr/torch/onnxruntime（懒加载），冷启动 -3-5s。

### 重要实测发现
- rapidocr-onnxruntime 模型打包在 pip 包内（无运行时下载）
- 字符字典内嵌在 rec onnx 模型（无需 ppocr_keys_v1.txt）
- 覆盖 model_path 用 `RapidOCR(Det_model_path=绝对路径, ...)` kwargs
- 模型文件名实测：ch_PP-OCRv4_det/rec_infer.onnx + ch_ppocr_mobile_v2.0_cls_infer.onnx
```

- [ ] **Step 4：最终 commit**

```bash
git add MEMORY.md 2>/dev/null || true
git commit -m "docs: 更新 MEMORY.md 记录 OCR backend 替换" 2>&1 || echo "no changes to commit"
```

---

## 验证清单

最终交付时确认：

- [ ] `pytest tests/common/ yys/yuhun_score_helper/` 全部通过
- [ ] `pip uninstall easyocr` 后脚本仍能 OCR（rapidocr 模式）
- [ ] 实际打包 `dist-electron/*.exe` < 350 MB
- [ ] 启动 WinController 不再 import easyocr/torch/onnxruntime
- [ ] 御魂 20+ 张真实截图：召回率 ≥ 90%，误报率 ≤ 5%
- [ ] `config/ui_config.json` 切换 `ocr_backend` 后重启生效
- [ ] 旧 `CommonOcr(['ch_sim', 'en'])` 调用方式仍能跑（YysYuHunOCR 零改动）
- [ ] `ocr()` 方法 2× resize + 坐标缩回逻辑保留

## 风险与回退

| 风险 | 缓解 |
|------|------|
| RapidOCR 准确率不足 | 保留 `easyocr` backend + 切换配置回退 |
| onnxruntime 隐藏 import 漏 | spec hiddenimports 列表覆盖核心模块；首次打包若失败按错误信息补 |
| 模型复制源（pip 包内）损坏 | download 脚本捕获 FileNotFoundError 提示重装 |
| 删除 torch 后 PyInstaller 仍牵入 | excludes 显式加 torch/torchvision/scipy/scikit-image |
| `get_reader()` 真实调用方 (YysYuHunOCR) 受 deprecation warning 干扰 | YysYuHunOCR 改用 `.ocr(img)` 而非 `.reader`（后续 Task，**不在本次范围**） |
| 用户环境是 Windows ARM | 不在本次范围（x64 优先） |
