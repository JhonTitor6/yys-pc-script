from __future__ import annotations

import os
import tempfile
import warnings
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image, UnidentifiedImageError

from win_util.image import (
    PROJECT_ROOT,
    effective_image_path,
    image_override_root,
    production_image_ids,
)


MAX_IMAGE_BYTES = 16 * 1024 * 1024


class ImageResourceError(Exception):
    """图片资源请求错误。"""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class ImageResourceService:
    """管理安装树图片目录和当前用户的单版本覆盖。"""

    def __init__(
        self,
        user_data_dir: Path | str | None,
        project_root: Path = PROJECT_ROOT,
    ) -> None:
        self.project_root = Path(project_root)
        self.user_data_dir = Path(user_data_dir) if user_data_dir else None

    def list_resources(self) -> list[dict[str, Any]]:
        """列出当前安装树中的全部生产图片。"""
        return [self.describe(resource_id) for resource_id in production_image_ids(self.project_root)]

    def describe(self, resource_id: str) -> dict[str, Any]:
        """返回单个资源的 GUI 安全元数据。"""
        builtin = self._builtin_path(resource_id)
        effective = effective_image_path(resource_id, self.project_root, self.user_data_dir)
        with Image.open(effective) as image:
            width, height = image.size
            image_format = image.format
        parts = PurePosixPath(resource_id).parts
        return {
            "resource_id": resource_id,
            "group": parts[1] if len(parts) > 2 else "yys",
            "filename": parts[-1],
            "format": image_format,
            "width": width,
            "height": height,
            "overridden": effective != builtin,
        }

    def content_path(self, resource_id: str, variant: str = "effective") -> Path:
        """返回内置或当前生效图片路径。"""
        builtin = self._builtin_path(resource_id)
        if variant == "builtin":
            return builtin
        if variant != "effective":
            raise ImageResourceError("variant 只允许 effective 或 builtin")
        return effective_image_path(resource_id, self.project_root, self.user_data_dir)

    def replace(self, resource_id: str, payload: bytes) -> dict[str, Any]:
        """校验并原子替换单个当前用户版本。"""
        builtin = self._builtin_path(resource_id)
        if not payload:
            raise ImageResourceError("图片内容不能为空")
        if len(payload) > MAX_IMAGE_BYTES:
            raise ImageResourceError(f"图片内容不能超过 {MAX_IMAGE_BYTES} 字节", 413)

        image = self._decode(payload)
        target_format = "BMP" if builtin.suffix.lower() == ".bmp" else "PNG"
        converted = image.convert("RGBA" if target_format == "PNG" and "A" in image.getbands() else "RGB")
        override_root = image_override_root(self.user_data_dir)
        if override_root is None:
            raise ImageResourceError("未配置用户数据目录", 503)
        target = override_root.joinpath(*PurePosixPath(resource_id).parts)
        target.parent.mkdir(parents=True, exist_ok=True)

        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temp_path = Path(temporary.name)
            converted.save(temp_path, format=target_format)
            with Image.open(temp_path) as written:
                written.load()
                if written.format != target_format or written.width <= 0 or written.height <= 0:
                    raise ImageResourceError("临时图片校验失败")
            os.replace(temp_path, target)
        except ImageResourceError:
            raise
        except OSError as exc:
            raise ImageResourceError(f"原子替换失败：{exc}", 409) from exc
        finally:
            converted.close()
            image.close()
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
        return self.describe(resource_id)

    def restore(self, resource_id: str) -> dict[str, Any]:
        """删除单个用户覆盖，立即恢复当前安装版本。"""
        self._builtin_path(resource_id)
        override_root = image_override_root(self.user_data_dir)
        if override_root is not None:
            target = override_root.joinpath(*PurePosixPath(resource_id).parts)
            try:
                target.unlink(missing_ok=True)
            except OSError as exc:
                raise ImageResourceError(f"恢复默认失败：{exc}", 409) from exc
        return self.describe(resource_id)

    def _builtin_path(self, resource_id: str) -> Path:
        if (
            not resource_id
            or "\\" in resource_id
            or PurePosixPath(resource_id).is_absolute()
            or ".." in PurePosixPath(resource_id).parts
            or PurePosixPath(resource_id).as_posix() != resource_id
        ):
            raise ImageResourceError("资源 ID 无效")
        if resource_id not in set(production_image_ids(self.project_root)):
            raise ImageResourceError("图片资源不存在或已从安装包移除", 404)
        return self.project_root.joinpath(*PurePosixPath(resource_id).parts)

    @staticmethod
    def _decode(payload: bytes) -> Image.Image:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                image = Image.open(BytesIO(payload))
                if image.format not in {"BMP", "PNG"}:
                    raise ImageResourceError("只支持可解码的 BMP 或 PNG 图片")
                image.load()
                if image.width <= 0 or image.height <= 0:
                    raise ImageResourceError("图片尺寸无效")
                return image.copy()
        except ImageResourceError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ImageResourceError("图片像素数量过大", 413)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImageResourceError("图片内容无法解码") from exc
