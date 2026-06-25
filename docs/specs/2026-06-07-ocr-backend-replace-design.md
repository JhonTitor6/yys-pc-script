# OCR Backend 替换设计

**日期**：2026-06-07
**状态**：Draft (post spec review)
**作者**：Claude + 用户

## 背景与目标

当前 `yys-pc-script` 使用 EasyOCR 作为唯一 OCR 后端。在 2026-06-07 完成第一次 PyInstaller 打包后，发现以下痛点：

| 痛点 | 量化 |
|------|------|
| 打包体积巨大 | portable exe 1.72 GB（其中 torch 6.3 GB） |
| 启动慢 | 每次 `WinController()` 触发 torch import，冷启动 +3-5s |
| 模型下载慢 | 115 MB 模型（craft 79 MB + 中文 21 MB + 英文 14 MB） |

**目标**：在不破坏现有 OCR 业务调用（特别是 `YysYuHunOCR`）的前提下：
1. 把打包体积从 ~1.7 GB 瘦到 <350 MB
2. 启动时不再强制 import OCR 运行时
3. 保留 easyocr 作为可回退的备选 backend
4. 业务代码 (`YysYuHunOCR`) 改动最小化

## 方案选型

经过对比 RapidOCR / ddddocr / Tesseract / WinRT / 云 API，确定采用 **RapidOCR (onnxruntime 引擎)**：

| 维度 | RapidOCR | 备注 |
|------|----------|------|
| 模型大小 | ~10 MB | vs EasyOCR 115 MB |
| 运行时 | onnxruntime ~50 MB | vs torch 6.3 GB |
| 中文准确率 | 良 | PaddleOCR 蒸馏版，与 EasyOCR 同级 |
| 接口兼容 | `(box, text, conf)` | 与 easyocr 一致 |
| 离线 | 是 | 模型可预下载 |
| 改造量 | 小 | 替换 backend 实例化即可 |

## 架构

### 模块组织

```
win_util/
├── ocr.py                     # CommonOcr 入口（懒加载调度）
├── ocr_config.py              # 读 ui_config.json 解析 backend 名
└── ocr_backends/
    ├── __init__.py            # 注册表：BACKEND_REGISTRY
    ├── base.py                # OcrBackend Protocol
    ├── rapid.py               # RapidOCRBackend
    └── easy.py                # EasyOcrBackend（标 deprecated，保留兜底）
```

### 类关系

```
┌────────────────────────┐
│  config/ui_config.json │
│  {"ocr_backend": "..."} │
└──────────┬─────────────┘
           │ get_ocr_backend_name()
           ▼
┌────────────────────────────┐
│  win_util/ocr_config       │  ← 新增
│  get_ocr_backend_name()    │
│  get_ocr_model_dir(name)   │
└──────────┬─────────────────┘
           │ "rapidocr" / "easyocr"
           ▼
┌────────────────────────────────────┐
│  win_util/ocr.py::CommonOcr        │
│                                    │
│  __init__(reader=None,             │  ← 旧签名保留（向后兼容）
│           lang_list=None,          │
│           gpu=False,               │
│           backend=None,            │  ← 新增参数
│           model_dir=None,          │
│           **kwargs):               │
│    self._backend = None            │
│    self._legacy_reader = reader    │  ← 兼容旧 test 注入
│                                    │
│  @property                         │
│  def backend(self) -> OcrBackend:  │
│    if self._backend is None:       │
│      self._backend = _load(...)    │  ← 首次访问才 import
│    return self._backend            │
│                                    │
│  ocr(img) -> backend.readtext(img) │
│  contains_text / find_text_*       │  ← 转发到 backend
└────────┬───────────────────────────┘
         │ 选择
         ├──────────────────┐
         ▼                  ▼
┌────────────────┐   ┌────────────────┐
│ RapidOcrBackend│   │ EasyOcrBackend │
│ (rapidocr-     │   │ (easyocr +     │
│  onnxruntime)  │   │  torch)        │
└────────────────┘   └────────────────┘
```

## 接口设计

### `win_util/ocr_config.py`（新增）

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
    """dev: 项目根/config/ui_config.json
    pack: exe 同目录/config/ui_config.json（与 ui_workbench.db 同位）
    永远基于 cwd，不读 _MEIPASS（详见 §10 路径约定）。
    """
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
    """解析 backend 模型目录（pack 模式下从 _MEIPASS 读）。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        if backend == "rapidocr":
            # RapidOCR 1.3+ 默认读 ~/rapidocr（无 dot），pack 模式从 _MEIPASS/rapidocr 读
            candidate = meipass / "rapidocr"
            return candidate if candidate.is_dir() else None
        candidate = meipass / ".EasyOCR" / "model"
        return candidate if candidate.is_dir() else None
    return None
```

### `win_util/ocr_backends/base.py`（新增）

```python
"""OCR backend 抽象接口。"""
from __future__ import annotations
from typing import Protocol, Any

OcrResult = tuple[list[list[int]], str, float]  # (box, text, conf)


class OcrBackend(Protocol):
    """统一的 OCR backend 接口，与 easyocr.readtext 返回格式一致。"""
    name: str

    def readtext(self, image: Any, **kwargs) -> list[OcrResult]:
        """识别图像中的文字。返回 [(box, text, conf), ...]"""
        ...
```

### `win_util/ocr_backends/rapid.py`（新增）

```python
"""RapidOCR backend（onnxruntime 引擎）。

需要的资源文件（必须在运行时可访问）：
- ch_PP-OCRv4_det_infer.onnx     # 文字检测
- ch_PP-OCRv4_rec_infer.onnx     # 文字识别
- ch_ppocr_mobile_v2_cls_infer.onnx  # 方向分类（可选）
- ppocr_keys_v1.txt              # 字符字典（必需！缺它识别结果永远为空）
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from loguru import logger


class RapidOcrBackend:
    name = "rapidocr"

    def __init__(self, model_dir: Path | None = None) -> None:
        from rapidocr_onnxruntime import RapidOCR  # 懒导入

        kwargs: dict[str, Any] = {}
        if model_dir is not None and model_dir.is_dir():
            kwargs["det_model_path"] = str(model_dir / "ch_PP-OCRv4_det_infer.onnx")
            kwargs["rec_model_path"] = str(model_dir / "ch_PP-OCRv4_rec_infer.onnx")
            kwargs["cls_model_path"] = str(model_dir / "ch_ppocr_mobile_v2_cls_infer.onnx")
            kwargs["rec_keys_path"] = str(model_dir / "ppocr_keys_v1.txt")
        self._engine = RapidOCR(**kwargs)
        logger.info(f"[RapidOCR] 已初始化，model_dir={model_dir}")

    def readtext(self, image: Any, **kwargs):
        # RapidOCR(image) 返回 (result, elapsed)；result 是 [[box,text,conf],...]
        result, _elapsed = self._engine(image, **kwargs)
        return result or []
```

### `win_util/ocr_backends/easy.py`（新增）

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

### `win_util/ocr.py`（改造）

```python
"""CommonOcr 入口：懒加载 + 转发到 backend。"""
from __future__ import annotations
from pathlib import Path
from typing import Any

from loguru import logger

from win_util.ocr_config import BackendName, get_ocr_backend_name, get_ocr_model_dir


class CommonOcr:
    """统一 OCR 入口。

    向后兼容：
    - 旧调用 CommonOcr(['ch_sim', 'en']) 仍能工作（lang_list 落到 kwargs 或 legacy_reader）
    - 旧测试通过 set_reader 注入的 mock reader 仍生效
    - get_reader() 标记 deprecated，建议改用 ocr(img) 统一入口
    """

    def __init__(
        self,
        reader: Any = None,                    # 旧：直接注入 reader
        lang_list: list[str] | None = None,    # 旧：传给 easyocr
        gpu: bool = False,                     # 旧：传给 easyocr
        backend: BackendName | None = None,    # 新
        model_dir: Path | None = None,         # 新
        **kwargs,
    ) -> None:
        # 旧语义兼容：第一个位置参数如果不是字符串列表（lang_list），
        # 而是个对象（reader），则原样保留作为 legacy reader。
        self._legacy_reader = reader
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

    def _create_backend(self):
        # legacy 优先：测试用 set_reader 注入的 mock 直接用
        if self._legacy_reader is not None:
            return self._legacy_reader

        from win_util.ocr_backends.rapid import RapidOcrBackend
        from win_util.ocr_backends.easy import EasyOcrBackend

        if self._backend_name == "rapidocr":
            return RapidOcrBackend(model_dir=self._model_dir)
        elif self._backend_name == "easyocr":
            return EasyOcrBackend(
                lang_list=self._legacy_lang_list or ["ch_sim", "en"],
                gpu=self._legacy_gpu,
                model_dir=self._model_dir,
            )
        else:  # pragma: no cover
            raise ValueError(f"未知 OCR backend: {self._backend_name}")

    def ocr(self, img, **readtext_kwargs):
        """识别图像，返回 [(box, text, conf), ...]（与 easyocr 一致）。"""
        return self.backend.readtext(img, **readtext_kwargs)

    # 兼容旧 API
    def get_reader(self):
        """已废弃。rapid 模式返回 backend 自身；easyocr 模式返回原生 reader。
        建议改用 common_ocr.ocr(img) 统一入口。
        """
        import warnings
        warnings.warn(
            "CommonOcr.get_reader() 已被废弃，请改用 .ocr(img) 入口",
            DeprecationWarning,
            stacklevel=2,
        )
        backend = self.backend
        return getattr(backend, "_reader", backend)

    def set_reader(self, reader):
        """直接注入 reader（兼容旧测试）。"""
        self._legacy_reader = reader
        self._backend = reader  # 立即生效

    def contains_text(self, img, target_text, case_sensitive=False) -> bool:
        # ... 复用现有逻辑，转发给 self.ocr(...)
        ...

    def find_text_position(self, img, target_text, similarity_threshold=0.3, case_sensitive=False):
        # ... 复用现有逻辑
        ...
```

### `win_util/controller.py`（懒加载 ocr）

```python
from __future__ import annotations  # ← 必须加，避免 CommonOcr 类型解析触发循环 import

class WinController:
    def __init__(self, hwnd=None, env=None):
        self.hwnd = hwnd
        self._env = env
        self.image_finder = ImageFinder(env=env, hwnd=hwnd)
        self.keyboard = KeyboardController(hwnd)
        self.mouse = MouseController(env=env, hwnd=hwnd)
        # ocr 改为懒加载——不在 __init__ 实例化
        self._ocr: CommonOcr | None = None

    @property
    def ocr(self) -> CommonOcr:
        """首次访问时才实例化 CommonOcr（避免 import torch/onnxruntime）。"""
        if self._ocr is None:
            self._ocr = CommonOcr()
        return self._ocr

    # 现有 __getattr__ 前缀映射 + ocr_/find_text 仍走 self.ocr.xxx
    # 注意：__getattr__ 只在常规查找失败时调用；property ocr 会先匹配，
    # 所以现有调用 `controller.ocr_xxx()` 仍工作（先拿到 ocr property，
    # 再调 .ocr_xxx(...)）。
```

## 配置文件

### `config/ui_config.json`

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

## 依赖调整

### `requirements.txt`

```diff
-aircv==1.4.6
 loguru==0.7.3
 mss==10.0.0
 numpy==1.26.4
 Pillow==11.1.0
 pywin32==308
-easyocr~=1.7.2
+rapidocr-onnxruntime>=1.3,<2.0
+onnxruntime>=1.15,<2.0
 fastapi>=0.115.0,<1.0.0
 httpx>=0.27.0,<1.0.0
 uvicorn[standard]>=0.30.0,<1.0.0
```

> `torch` / `torchvision` / `scipy` / `scikit-image` 当前是 easyocr 的传递依赖，删除 easyocr 后自动消失。如残留，手动 `pip uninstall` 即可。

## 打包调整

### `build_backend.spec`

- `HIDDENIMPORTS` 中删除：`easyocr`, `torch.*`, `torchvision`, `scipy.*`, `skimage.*`
- `HIDDENIMPORTS` 新增（rapidocr + onnxruntime 全量）：
  ```python
  # onnxruntime
  'onnxruntime',
  'onnxruntime.capi._pybind_state',
  'onnxruntime.capi.onnxruntime_pybind11_state',  # 新版
  'onnxruntime.providers',
  'onnxruntime.providers.cpu',
  'onnxruntime.providers.cpu.cpu_execution_provider',
  # rapidocr
  'rapidocr_onnxruntime',
  'rapidocr_onnxruntime.rapid_ocr',
  'rapidocr_onnxruntime.ch_ppocr_det',
  'rapidocr_onnxruntime.ch_ppocr_rec',
  'rapidocr_onnxruntime.ch_ppocr_cls',
  'rapidocr_onnxruntime.utils',
  'rapidocr_onnxruntime.onnx_wrapper',
  ```
- `DATAS` 新增：`('assets/ocr_models_rapid', 'rapidocr')`（如果目录非空）
- `excludes` **追加**：`torch`, `torchvision`, `scipy`, `scikit-image`
  - 不要 exclude `PIL`（RapidOCR 内部依赖）

> **首次打包验证**：先跑一次 `python -m PyInstaller --collect-all rapidocr_onnxruntime onnxruntime build_backend.spec` 验证无 `ImportError`，再切回标准 spec 命令。

## OCR 模型下载

### `scripts/download_ocr_models.py` 改造

支持 `--backend rapidocr | easyocr`：

```bash
python scripts/download_ocr_models.py --backend rapidocr
# 1) 实例化 RapidOCR() 触发模型下载到 ~/rapidocr/
# 2) 复制到 <project>/assets/ocr_models_rapid/
#    ├── ch_PP-OCRv4_det_infer.onnx
#    ├── ch_PP-OCRv4_rec_infer.onnx
#    ├── ch_ppocr_mobile_v2_cls_infer.onnx
#    └── ppocr_keys_v1.txt       ← 字符字典（必需）
```

> 旧 easyocr 路径作为 `--backend easyocr` 保留，输出到 `assets/ocr_models_easy/`，向后兼容。

## 打包前检查清单

每次跑 `build_release.ps1` 前确认：

- [ ] `ls assets/ocr_models_rapid/` 非空（含 3 个 .onnx + ppocr_keys_v1.txt）
- [ ] `python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR()"` 成功（确认 onnxruntime + 模型都能加载）
- [ ] `pip show easyocr` 显示未安装（已删除）
- [ ] `pytest tests/common/ yys/yuhun_score_helper/` 全部通过

## 测试策略

### 单元测试

- `tests/common/test_ocr_config.py`（新增）：
  - `ui_config.json` 缺失 → 默认 rapidocr
  - `ui_config.json` 含 `ocr_backend: "easyocr"` → easyocr
  - `ocr_backend: "RAPIDOCR"`（大写） → rapidocr（.lower() 处理）
  - `ocr_backend: "unknown"` → 警告 + 默认
  - `ui_config.json` 是非法 JSON → 警告 + 默认
- `tests/common/test_ocr_backends.py`（新增）：
  - mock rapidocr 验证接口契约
  - mock easyocr 验证接口契约
- `tests/common/test_ocr.py`（现有）：保持通过（monkeypatch `CommonOcr` 仍生效）

### 真实御魂截图对比（**至少 20 张**）

样本策略：覆盖
- 5 类有效属性 × 2 稀有度（5 星 / 6 星） = 10 张
- 6 个位置（上 / 中 / 下 × 主 / 副属性）= 6 张
- 几张无效属性 / 边界情况（满级 +0、+15 等）= 4+ 张
- 至少 1 张全空属性（误报率测试）

**双指标**：
- **召回率** = 真实属性被正确识别数 / 真实属性总数
- **误报率** = 错误识别的有效属性（如把"防御"误判为"攻击加成"）数 / 识别出的属性总数

验收：
- 召回率 ≥ 90%
- 误报率 ≤ 5%（脚本按识别结果自动评分，误报 = 算错分）

输出到 `tests/common/fixtures/yuhun_comparison.md`：每个属性对比 easyocr vs rapidocr 的结果。

### 集成验证

```bash
pytest tests/common/ yys/yuhun_score_helper/ -q
# 目标：原有 60+ passed 不掉，OCR 相关 mock 测试不破坏
```

## 路径约定（dev / pack 行为对齐）

| 配置 / 资源 | dev 模式 | pack 模式 |
|-------------|----------|-----------|
| `ui_config.json` | `<project_root>/config/` | `<exe_dir>/config/`（用户可改） |
| `ui_workbench.db` | `<project_root>/config/` | `<exe_dir>/config/` |
| `rapidocr` 模型 | `~/rapidocr/`（首次自动下载） | `<exe_dir>/resources/backend/_internal/rapidocr/`（通过 build_backend.spec datas 注入） |
| `easyocr` 模型 | `~/.EasyOCR/model/` | 同上路径（`_internal/.EasyOCR/model/`） |

> `ocr_config.py._config_path()` **永远基于 cwd**（pack 模式 cwd = exe 同目录）。
> pack 模式不会从 `_MEIPASS/config/` 读 `ui_config.json`（用户改 exe 同目录那个）。
> 首次启动如果 `cwd/config/ui_config.json` 不存在，从 `_MEIPASS/config/ui_config.json` 复制一份（仅在 ui_backend/app.py 启动逻辑中处理，不在 ocr_config.py）。

## 风险与回退

| 风险 | 缓解 |
|------|------|
| RapidOCR 在御魂艺术字下准确率不足 | 保留 `easyocr` backend；首次上线跑 20+ 张真实截图对比；不达标时改 `ocr_backend: "easyocr"` 即可回退 |
| onnxruntime 与 Windows ARM 兼容问题 | 不在本次范围（用户机器 x64） |
| 模型下载源被墙 | PaddleOCR 模型在百度 CDN（国内可访问），预下载到本地再打包 |
| 删除 torch 后某些隐藏依赖 | 跑 `pytest tests/common/` 全绿后清理；excludes 显式加 torch 等 |
| `ppocr_keys_v1.txt` 漏打包 → 识别永远空 | 打包前 checklist 强制检查；build_backend.spec 注释里点名这个文件 |
| 老用户保留 `easyocr` 习惯 | CommonOcr 签名完全向后兼容；旧 `YysYuHunOCR` 代码 0 改动 |

## 验收标准

- [ ] `pytest tests/common/ yys/yuhun_score_helper/` 全部通过
- [ ] `pip uninstall easyocr torch torchvision scipy scikit-image` 后脚本仍能 OCR（用 rapidocr）
- [ ] 实际打包 `dist-electron/*.exe` 体积 < 350 MB
- [ ] 启动 WinController 不再 import easyocr/torch（用 `python -X importtime` 验证）
- [ ] 御魂 20+ 张真实截图：召回率 ≥ 90%，误报率 ≤ 5%
- [ ] `config/ui_config.json` 切换 `ocr_backend` 后，重启生效
- [ ] 老 `CommonOcr(['ch_sim', 'en'])` 调用方式仍能跑（YysYuHunOCR 零改动）

## 工作量估计

- 新增文件：**5 个**（`ocr_config.py`, `ocr_backends/{__init__,base,rapid,easy}.py`）
- 修改文件：7 个（`ocr.py`, `controller.py`, `ui_config.json`, `requirements.txt`, `build_backend.spec`, `download_ocr_models.py`, 视情况 `yys_yu_hun_ocr.py`）
- 新增测试：2 个
- 实施时间：~半天

## 后续（不在本次范围）

- 添加 `RapidOCR` GUI 配置面板（让用户运行时切换 backend）
- `easyocr` 真正下线（标记 deprecated 2-3 个月后删除）
- onnxruntime GPU 加速（当前仅 CPU）
- 录制式回归测试：用真实御魂截图做 golden fixture
