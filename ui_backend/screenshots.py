from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

from yys.common.recording.session import validate_capture_frame


MAX_SCREENSHOT_BYTES = 32 * 1024 * 1024
_SCREENSHOT_ID = re.compile(r"^[0-9a-f]{32}$")
_SCREENSHOT_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SCREENSHOT_KINDS = frozenset({"full", "crop"})
_SCREENSHOT_TRIGGERS = frozenset(
    {"manual", "unknown_scene", "script_error", "entry_error", "stop_timeout"}
)


class ScreenshotError(Exception):
    """截图请求或持久化错误。"""

    def __init__(
        self,
        detail: str,
        status_code: int = 400,
        *,
        restore_required: bool = False,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.restore_required = restore_required


class ScreenshotService:
    """管理 userData 中的永久截图和同名元数据。"""

    def __init__(self, user_data_dir: Path | str | None) -> None:
        self.root = Path(user_data_dir) / "screenshots" if user_data_dir else None

    def save_full(
        self,
        frame: Any,
        *,
        trigger: str,
        run_id: int | None = None,
        script_id: str | None = None,
        stage: str | None = None,
    ) -> dict[str, Any]:
        """校验并永久保存一张完整客户区画面。"""
        image = self._frame_image(frame)
        try:
            validate_capture_frame(np.asarray(image))
            return self._save(
                image,
                kind="full",
                trigger=trigger,
                source_id=None,
                run_id=run_id,
                script_id=script_id,
                stage=stage,
            )
        except RuntimeError as exc:
            raise ScreenshotError("完整截图为空或近似纯色，请确认游戏窗口正常显示") from exc
        finally:
            image.close()

    def save_crop(
        self,
        source_id: str,
        payload: bytes,
        *,
        run_id: int | None = None,
        script_id: str | None = None,
        stage: str | None = None,
    ) -> dict[str, Any]:
        """校验 Cropper.js 输出并保存独立 PNG 副本。"""
        source = self.get(source_id)
        if not source["available"]:
            raise ScreenshotError("源截图已删除或不可用", 404)
        if not payload:
            raise ScreenshotError("裁剪图片不能为空")
        if len(payload) > MAX_SCREENSHOT_BYTES:
            raise ScreenshotError(f"裁剪图片不能超过 {MAX_SCREENSHOT_BYTES} 字节", 413)
        try:
            with Image.open(BytesIO(payload)) as decoded:
                if decoded.format != "PNG":
                    raise ScreenshotError("裁剪结果必须是 PNG")
                decoded.load()
                if decoded.width <= 0 or decoded.height <= 0:
                    raise ScreenshotError("裁剪选区尺寸无效")
                if decoded.width > source["width"] or decoded.height > source["height"]:
                    raise ScreenshotError("裁剪选区超出源截图范围")
                image = decoded.convert("RGBA" if "A" in decoded.getbands() else "RGB")
        except ScreenshotError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ScreenshotError("裁剪图片无法解码") from exc
        try:
            return self._save(
                image,
                kind="crop",
                trigger="manual",
                source_id=source_id,
                run_id=run_id if run_id is not None else source.get("run_id"),
                script_id=script_id if script_id is not None else source.get("script_id"),
                stage=stage if stage is not None else source.get("stage"),
            )
        finally:
            image.close()

    def list(self) -> list[dict[str, Any]]:
        """按时间倒序列出永久截图；当前规模直接线性扫描。"""
        if self.root is None or not self.root.is_dir():
            return []
        items: list[dict[str, Any]] = []
        for path in self.root.glob("*/*.json"):
            try:
                item = self._read_metadata(path)
                item["available"] = self._content_is_valid(path.with_suffix(".png"), item)
                items.append(item)
            except ScreenshotError:
                continue
        return sorted(items, key=lambda item: str(item.get("created_at", "")), reverse=True)

    def get(self, screenshot_id: str) -> dict[str, Any]:
        """按稳定 ID 读取截图元数据。"""
        metadata_path = self._find(screenshot_id, ".json")
        item = self._read_metadata(metadata_path, expected_id=screenshot_id)
        item["available"] = self._content_is_valid(metadata_path.with_suffix(".png"), item)
        return item

    def content_path(self, screenshot_id: str) -> Path:
        """返回可读 PNG 路径。"""
        metadata_path = self._find(screenshot_id, ".json")
        metadata = self._read_metadata(metadata_path, expected_id=screenshot_id)
        path = metadata_path.with_suffix(".png")
        if not self._content_is_valid(path, metadata):
            raise ScreenshotError("截图已删除或不可用", 404)
        return path

    def delete(self, screenshot_id: str) -> dict[str, Any]:
        """只删除用户明确选中的一张截图。"""
        metadata = self.get(screenshot_id)
        metadata_path = self._find(screenshot_id, ".json")
        image_path = metadata_path.with_suffix(".png")
        try:
            image_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
        except OSError as exc:
            raise ScreenshotError(f"删除截图失败：{exc}", 409) from exc
        metadata["available"] = False
        return metadata

    def _save(
        self,
        image: Image.Image,
        *,
        kind: str,
        trigger: str,
        source_id: str | None,
        run_id: int | None,
        script_id: str | None,
        stage: str | None,
    ) -> dict[str, Any]:
        if self.root is None:
            raise ScreenshotError("未配置用户数据目录", 503)
        created_at = datetime.now(timezone.utc).astimezone().isoformat()
        screenshot_id = uuid.uuid4().hex
        directory = self.root / created_at[:10]
        directory.mkdir(parents=True, exist_ok=True)
        image_path = directory / f"{screenshot_id}.png"
        metadata_path = directory / f"{screenshot_id}.json"
        metadata = {
            "id": screenshot_id,
            "created_at": created_at,
            "kind": kind,
            "trigger": trigger,
            "width": image.width,
            "height": image.height,
            "source_id": source_id,
            "run_id": run_id,
            "script_id": script_id,
            "stage": stage,
        }
        image_temp = self._temp_path(directory, screenshot_id, ".png.tmp")
        metadata_temp = self._temp_path(directory, screenshot_id, ".json.tmp")
        image_committed = False
        try:
            image.save(image_temp, format="PNG")
            if image_temp.stat().st_size <= 0 or image_temp.stat().st_size > MAX_SCREENSHOT_BYTES:
                raise ScreenshotError(f"截图文件不能超过 {MAX_SCREENSHOT_BYTES} 字节", 413)
            with Image.open(image_temp) as written:
                written.load()
                if written.format != "PNG" or written.size != image.size:
                    raise ScreenshotError("截图临时文件校验失败")
            metadata_temp.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(image_temp, image_path)
            image_committed = True
            os.replace(metadata_temp, metadata_path)
        except ScreenshotError:
            raise
        except OSError as exc:
            raise ScreenshotError(f"截图原子保存失败：{exc}", 409) from exc
        finally:
            for temp_path in (image_temp, metadata_temp):
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            if image_committed and not metadata_path.is_file():
                try:
                    image_path.unlink(missing_ok=True)
                except OSError:
                    pass
        return {**metadata, "available": True}

    def _find(self, screenshot_id: str, suffix: str) -> Path:
        if self.root is None:
            raise ScreenshotError("未配置用户数据目录", 503)
        if not _SCREENSHOT_ID.fullmatch(screenshot_id):
            raise ScreenshotError("截图 ID 无效")
        matches = list(self.root.glob(f"*/{screenshot_id}{suffix}"))
        if len(matches) != 1:
            raise ScreenshotError("截图不存在", 404)
        path = matches[0]
        try:
            path.resolve().relative_to(self.root.resolve())
        except (OSError, ValueError) as exc:
            raise ScreenshotError("截图路径无效", 404) from exc
        return path

    def _read_metadata(
        self,
        path: Path,
        *,
        expected_id: str | None = None,
    ) -> dict[str, Any]:
        """校验元数据路径、字段与文件名的一致性。"""
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            screenshot_id = item.get("id") if isinstance(item, dict) else None
            created_at = item.get("created_at") if isinstance(item, dict) else None
            if (
                not isinstance(item, dict)
                or not isinstance(screenshot_id, str)
                or not _SCREENSHOT_ID.fullmatch(screenshot_id)
                or (expected_id is not None and screenshot_id != expected_id)
                or path.name != f"{screenshot_id}.json"
                or not _SCREENSHOT_DATE.fullmatch(path.parent.name)
                or not isinstance(created_at, str)
                or datetime.fromisoformat(created_at).date().isoformat() != path.parent.name
                or item.get("kind") not in _SCREENSHOT_KINDS
                or item.get("trigger") not in _SCREENSHOT_TRIGGERS
                or not isinstance(item.get("width"), int)
                or not isinstance(item.get("height"), int)
                or item["width"] <= 0
                or item["height"] <= 0
            ):
                raise ValueError("元数据字段无效")
            source_id = item.get("source_id")
            if item["kind"] == "full" and source_id is not None:
                raise ValueError("完整帧不能包含来源 ID")
            if item["kind"] == "crop" and (
                not isinstance(source_id, str) or not _SCREENSHOT_ID.fullmatch(source_id)
            ):
                raise ValueError("裁剪图来源 ID 无效")
            if item.get("run_id") is not None and (
                not isinstance(item["run_id"], int) or item["run_id"] <= 0
            ):
                raise ValueError("运行 ID 无效")
            for field in ("script_id", "stage"):
                if item.get(field) is not None and not isinstance(item[field], str):
                    raise ValueError(f"{field} 无效")
            return item
        except (OSError, TypeError, ValueError) as exc:
            raise ScreenshotError("截图元数据不可读", 404) from exc

    @staticmethod
    def _content_is_valid(path: Path, metadata: dict[str, Any]) -> bool:
        """确认 PNG 内容、尺寸和字节数与元数据一致。"""
        try:
            size = path.stat().st_size
            if size <= 0 or size > MAX_SCREENSHOT_BYTES:
                return False
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                return image.format == "PNG" and image.size == (
                    metadata["width"],
                    metadata["height"],
                )
        except (OSError, KeyError, UnidentifiedImageError, ValueError):
            return False

    @staticmethod
    def _temp_path(directory: Path, screenshot_id: str, suffix: str) -> Path:
        with tempfile.NamedTemporaryFile(
            dir=directory,
            prefix=f".{screenshot_id}.",
            suffix=suffix,
            delete=False,
        ) as temporary:
            return Path(temporary.name)

    @staticmethod
    def _frame_image(frame: Any) -> Image.Image:
        if isinstance(frame, Image.Image):
            return frame.convert("RGB")
        array = np.asarray(frame)
        if array.ndim == 2:
            return Image.fromarray(array).convert("RGB")
        if array.ndim != 3 or array.shape[2] not in (3, 4):
            raise ScreenshotError("截图尺寸或通道无效")
        # ImageFinder 缓存来自 OpenCV，通道顺序为 BGR/BGRA。
        if array.shape[2] == 4:
            array = array[:, :, [2, 1, 0, 3]]
            return Image.fromarray(array, "RGBA").convert("RGB")
        return Image.fromarray(array[:, :, ::-1], "RGB")
