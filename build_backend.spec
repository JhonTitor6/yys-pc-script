# -*- mode: python ; coding: utf-8 -*-
"""
yys-pc-script Python 后端 PyInstaller 打包配置（--onedir）

产物：dist/backend/yys-backend.exe + 运行时依赖目录/
electron-builder 通过 extraResources 把整个 dist/backend 注入到
  resources/backend/，再被 gui/main.js 启动。

运行时数据（config/、yys/logs/）落在 cwd（即 exe 同目录），
与开发模式 Path("config")、Path("yys/logs") 行为一致。
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).resolve()

# Conda 环境的运行库位于 Library/bin。PyInstaller 的依赖扫描不会自动把
# 该目录加入搜索路径，导致打包后的 _ssl、Pillow、SQLite 或 OpenCV 无法启动。
PYTHON_PREFIX = Path(sys.prefix).resolve()
BASE_PREFIX = Path(getattr(sys, "base_prefix", sys.prefix)).resolve()
USING_VENV = PYTHON_PREFIX != BASE_PREFIX
PYTHON_ENV_ROOT = BASE_PREFIX
CONDA_LIBRARY_BIN = PYTHON_ENV_ROOT / "Library" / "bin"
if CONDA_LIBRARY_BIN.is_dir():
    os.environ["PATH"] = os.pathsep.join(
        [str(CONDA_LIBRARY_BIN), str(PYTHON_ENV_ROOT), os.environ.get("PATH", "")]
    )

RUNTIME_DLL_NAMES = [
    "libssl-3-x64.dll",
    "libcrypto-3-x64.dll",
    "liblzma.dll",
    "libbz2.dll",
    "ffi.dll",
    "freetype.dll",
    "openjp2.dll",
    "libjpeg.dll",
    "libtiff.dll",
    "libwebp.dll",
    "libwebpdemux.dll",
    "libwebpmux.dll",
    "lcms2.dll",
    "sqlite3.dll",
]

RUNTIME_BINARIES = [
    (str(CONDA_LIBRARY_BIN / name), ".")
    for name in RUNTIME_DLL_NAMES
    if (CONDA_LIBRARY_BIN / name).is_file()
]
if not USING_VENV:
    RUNTIME_BINARIES.extend(
        (str(path), ".")
        for path in sorted(CONDA_LIBRARY_BIN.glob("opencv_*.dll"))
    )


def collect_module_data(
    module_name: str,
    include_globs: list[str],
    exclude_globs: list[str] | None = None,
    destination_root: str = "",
) -> list[tuple[str, str]]:
    """
    收集 <module_name> 目录下匹配 include_globs 的所有文件，
    排除匹配 exclude_globs 的路径。
    返回 list[(src_path, relative_to_module)]，PyInstaller datas 格式。
    """
    module_dir = PROJECT_ROOT / module_name
    if not module_dir.is_dir():
        return []
    exclude_globs = exclude_globs or []
    # 用目录前缀过滤资源，避免 Path.match 对跨层目录模式的行为差异。
    exclude_roots = tuple(
        Path(pattern).parent.parts
        for pattern in exclude_globs
        if pattern.endswith("/**")
    )
    out: list[tuple[str, str]] = []
    for pattern in include_globs:
        for f in module_dir.rglob(pattern):
            if not f.is_file():
                continue
            rel = f.relative_to(module_dir)
            if any(
                rel.parts[index : index + len(root)] == root
                for root in exclude_roots
                for index in range(len(rel.parts) - len(root) + 1)
            ):
                continue
            destination = rel.parent.as_posix()
            if destination_root:
                destination = (
                    destination_root
                    if destination == "."
                    else f"{destination_root}/{destination}"
                )
            out.append((str(f), destination))
    return out

# ---------------------------------------------------------------------------
# 业务模块列表（用于 hiddenimports + 复制资源）
# ---------------------------------------------------------------------------
YYS_MODULES = [
    "yys",
    "yys.common",
    "yys.common.event_script_base",
    "yys.common.scene_manager",
    "yys.common.log_manager",
    "yys.common.script_meta",
    "yys.common.config_manager",
    "yys.common.battle",
    "yys.common.battle.base",
    "yys.common.battle.flow",
    "yys.common.battle.hooks",
    "yys.common.operations",
    "yys.common.constants",
    "yys.abyss_shadows",
    "yys.abyss_shadows.abyss_shadows_script",
    "yys.soul_raid",
    "yys.soul_raid.soul_raid_script",
    "yys.realm_raid",
    "yys.realm_foster",
    "yys.daily_collect",
    "yys.daily_collect.daily_collect_script",
    "yys.soul_soil",
    "yys.soul_soil.soul_soil_script",
    "yys.daily_activity_rewards",
    "yys.daily_activity_rewards.daily_activity_rewards_script",
    "yys.realm_foster.realm_foster_script",
    "yys.fengmo",
    "yys.fengmo.fengmo_script",
    "yys.regional_demon_boss",
    "yys.regional_demon_boss.regional_demon_boss_script",
    "yys.exploration",
    "yys.yuling",
    "yys.douji",
    "yys.douji.douji_script",
    "yys.fujiwara",
    "yys.fujiwara.script_main",
    "yys.omoikane",
    "yys.omoikane.omoikane_script",
    "yys.juexingcailiao",
    "yys.juexingcailiao.juexingcailiao_script",
    "yys.qilingtancha",
    "yys.qilingtancha.qilingtancha_script",
    "yys.qilingjieqi",
    "yys.qilingjieqi.qilingjieqi_script",
    "yys.yeyuanhuo",
    "yys.yeyuanhuo.yeyuanhuo_script",
    "yys.guibingyanwu",
    "yys.guibingyanwu.guibingyanwu_script",
    "yys.kuzunoha",
    "yys.kuzunoha.shadow_realm_elite_script",
    "yys.common_challenge",
    "yys.common_challenge.loop_challenge",
    "yys.util",
    "yys.util.yys_yu_hun_ocr",
    "yys.yuhun_score_helper",
    "yys.yuhun_score_helper.yuhun_score_helper_script",
]

UI_BACKEND_MODULES = [
    "ui_backend",
    "ui_backend.app",
    "ui_backend.main",
    "ui_backend.models",
    "ui_backend.events",
    "ui_backend.events.hub",
    "ui_backend.scripts",
    "ui_backend.scripts.registry",
    "ui_backend.scripts.default_registry",
    "ui_backend.scheduler",
    "ui_backend.scheduler.service",
    "ui_backend.storage",
    "ui_backend.storage.database",
    "ui_backend.storage.repositories",
    "ui_backend.runs",
    "ui_backend.runs.manager",
]

WIN_UTIL_MODULES = [
    "win_util",
    "win_util.event",
    "win_util.image",
    "win_util.mouse",
    "win_util.keyboard",
    "win_util.ocr",
    "win_util.controller",
]

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
    # rapidocr
    "rapidocr_onnxruntime",
    "rapidocr_onnxruntime.ch_ppocr_det",
    "rapidocr_onnxruntime.ch_ppocr_rec",
    "rapidocr_onnxruntime.ch_ppocr_cls",
    "rapidocr_onnxruntime.utils",
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

HIDDENIMPORTS = (
    YYS_MODULES
    + UI_BACKEND_MODULES
    + WIN_UTIL_MODULES
    + THIRD_PARTY_MODULES
)

# ---------------------------------------------------------------------------
# 资源文件
# ---------------------------------------------------------------------------
DATAS = []

# yys/ 下的图片模板、json 配置、txt
# 注：collect_data_files 对 yys/win_util 等 namespace package 报 warning，
# 这里改用 glob 直接遍历，避免误丢资源。
DATAS += collect_module_data(
    "yys",
    include_globs=["*.bmp", "*.png", "*.json", "*.txt"],
    exclude_globs=[
        "test/**",
        "images/debug/**",
        "images/test/**",
        "images/example/**",
        "logs/**",
        "__pycache__/**",
    ],
    destination_root="yys",
)

# win_util/ 下的 egg-info / README（可选，但保持完整）
DATAS += collect_module_data(
    "win_util",
    include_globs=["*.md", "*.toml"],
)

# config/*.json（只读模板，由 fastapi 启动时读 default ui_config）
config_dir = PROJECT_ROOT / "config"
if config_dir.is_dir():
    for json_file in config_dir.glob("*.json"):
        DATAS.append((str(json_file), "config"))

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

# ---------------------------------------------------------------------------
# PyInstaller 配置
# ---------------------------------------------------------------------------
a = Analysis(
    ["web_server.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=RUNTIME_BINARIES,
    datas=DATAS,
    hiddenimports=HIDDENIMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
        # loguru 的 Jupyter 兼容分支不是桌面后端需要的运行时依赖。
        "IPython",
        "ipykernel",
        "jedi",
        "nbformat",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,         # onedir 关键：分离 exe 与依赖
    name="yys-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                 # 不弹黑窗（windowed 模式）
    disable_windowed_traceback=False,
    # PyInstaller 6 默认把支持文件放进 _internal；项目运行时约定资源与
    # yys-backend.exe 同级，因此显式恢复旧式 onedir 布局。
    contents_directory=".",
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="backend",
)
