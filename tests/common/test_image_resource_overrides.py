from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image

from win_util.image import (
    IMAGE_EXCLUDED_DIRS,
    PROJECT_ROOT,
    production_image_ids,
    to_project_path,
)


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image_format = "BMP" if path.suffix.lower() == ".bmp" else "PNG"
    Image.new("RGB", (7, 5), color).save(path, format=image_format)


def test_catalog_matches_dynamic_install_tree() -> None:
    """产品契约：目录由安装树动态计算，不依赖固定图片数量。"""
    expected = sorted(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in (PROJECT_ROOT / "yys").rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".bmp", ".png"}
        and not IMAGE_EXCLUDED_DIRS.intersection(
            part.lower()
            for part in path.relative_to(PROJECT_ROOT / "yys").parts[:-1]
        )
    )
    assert production_image_ids() == expected
    assert expected


def test_relative_and_project_absolute_images_share_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """产品契约：普通模板与 SceneManager 绝对模板读取同一用户覆盖。"""
    resource_id = production_image_ids()[0]
    builtin = PROJECT_ROOT.joinpath(*PurePosixPath(resource_id).parts)
    override = tmp_path / "image-overrides" / Path(*PurePosixPath(resource_id).parts)
    _write_image(override, (12, 34, 56))
    monkeypatch.setenv("YYS_USER_DATA_DIR", str(tmp_path))

    assert Path(to_project_path(resource_id)) == override
    assert Path(to_project_path(str(builtin))) == override


def test_directories_external_files_and_invalid_overrides_keep_old_behavior(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """产品契约：目录、外部绝对路径及无效覆盖不得改变原路径语义。"""
    resource_id = production_image_ids()[0]
    builtin = PROJECT_ROOT.joinpath(*PurePosixPath(resource_id).parts)
    override = tmp_path / "image-overrides" / Path(*PurePosixPath(resource_id).parts)
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_bytes(b"not-an-image")
    external = tmp_path / "external.bmp"
    _write_image(external, (1, 2, 3))
    monkeypatch.setenv("YYS_USER_DATA_DIR", str(tmp_path))

    assert Path(to_project_path(resource_id)) == builtin
    assert Path(to_project_path(str(external))) == external
    assert Path(to_project_path("yys/common/images/scene")) == PROJECT_ROOT / "yys/common/images/scene"
    assert "image-overrides" not in to_project_path("yys/../outside.bmp")


def test_unreadable_override_falls_back_to_builtin(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """产品契约：不可读覆盖不得被传给运行中的图片匹配器。"""
    resource_id = production_image_ids()[0]
    builtin = PROJECT_ROOT.joinpath(*PurePosixPath(resource_id).parts)
    override = tmp_path / "image-overrides" / Path(*PurePosixPath(resource_id).parts)
    _write_image(override, (12, 34, 56))
    monkeypatch.setenv("YYS_USER_DATA_DIR", str(tmp_path))
    original_open = Path.open

    def deny_override(path: Path, *args: object, **kwargs: object) -> Any:
        if path == override:
            raise PermissionError("测试中的占用冲突")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_override)

    assert Path(to_project_path(resource_id)) == builtin
