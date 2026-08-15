from __future__ import annotations

from io import BytesIO
from pathlib import Path, PurePosixPath

from fastapi.testclient import TestClient
from PIL import Image

import ui_backend.image_resources as image_resources_module
from ui_backend.app import create_app
from ui_backend.image_resources import ImageResourceError, ImageResourceService, MAX_IMAGE_BYTES
from win_util.image import PROJECT_ROOT, production_image_ids, to_project_path


def _image_bytes(image_format: str, color: tuple[int, int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGB", (9, 6), color).save(output, format=image_format)
    return output.getvalue()


def _client(tmp_path: Path, token: str = "") -> TestClient:
    return TestClient(
        create_app(
            db_path=tmp_path / "ui.db",
            api_token=token,
            user_data_dir=tmp_path / "user-data",
        )
    )


def test_catalog_is_dynamic_and_token_protected(tmp_path: Path) -> None:
    client = _client(tmp_path, token="secret")
    assert client.get("/api/image-resources").status_code == 403

    response = client.get(
        "/api/image-resources",
        headers={"X-YYS-UI-Token": "secret"},
    )
    assert response.status_code == 200
    resources = response.json()
    assert [item["resource_id"] for item in resources] == production_image_ids()
    assert all(not Path(item["resource_id"]).is_absolute() for item in resources)
    assert all({"group", "filename", "format", "width", "height", "overridden"} <= item.keys() for item in resources)

    for item in resources:
        builtin = PROJECT_ROOT.joinpath(*PurePosixPath(item["resource_id"]).parts)
        with Image.open(builtin) as image:
            assert item["format"] == image.format

    preview = next(
        (
            item
            for item in resources
            if item["format"] != Path(item["resource_id"]).suffix[1:].upper()
        ),
        resources[0],
    )
    content = client.get(
        "/api/image-resources/content",
        params={"resource_id": preview["resource_id"]},
        headers={"X-YYS-UI-Token": "secret"},
    )
    assert content.status_code == 200
    assert content.headers["content-type"] == f"image/{preview['format'].lower()}"


def test_replace_is_persistent_and_immediately_used_then_restored(
    tmp_path: Path,
    monkeypatch,
) -> None:
    user_data = tmp_path / "user-data"
    monkeypatch.setenv("YYS_USER_DATA_DIR", str(user_data))
    client = _client(tmp_path)
    resource_id = production_image_ids()[0]
    target_format = "BMP" if resource_id.lower().endswith(".bmp") else "PNG"
    payload = _image_bytes("PNG", (23, 45, 67))

    response = client.put(
        "/api/image-resources/override",
        params={"resource_id": resource_id},
        content=payload,
    )
    assert response.status_code == 200
    assert response.json()["overridden"] is True
    effective = Path(to_project_path(resource_id))
    assert effective == user_data / "image-overrides" / Path(*PurePosixPath(resource_id).parts)
    with Image.open(effective) as image:
        assert image.format == target_format
        assert image.size == (9, 6)

    content = client.get(
        "/api/image-resources/content",
        params={"resource_id": resource_id, "variant": "effective"},
    )
    assert content.status_code == 200
    with Image.open(BytesIO(content.content)) as image:
        assert image.size == (9, 6)

    restored = client.delete(
        "/api/image-resources/override",
        params={"resource_id": resource_id},
    )
    assert restored.status_code == 200
    assert restored.json()["overridden"] is False
    assert Path(to_project_path(resource_id)) == PROJECT_ROOT.joinpath(*PurePosixPath(resource_id).parts)


def test_invalid_inputs_never_create_effective_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path)
    resource_id = production_image_ids()[0]
    endpoint = "/api/image-resources/override"

    assert client.put(endpoint, params={"resource_id": "../secret.bmp"}, content=b"x").status_code == 400
    assert client.put(endpoint, params={"resource_id": "yys/missing.bmp"}, content=b"x").status_code == 404
    assert client.put(endpoint, params={"resource_id": resource_id}, content=b"").status_code == 400
    assert client.put(endpoint, params={"resource_id": resource_id}, content=b"not-an-image").status_code == 400
    assert client.put(
        endpoint,
        params={"resource_id": resource_id},
        content=_image_bytes("JPEG", (1, 2, 3)),
    ).status_code == 400
    assert client.put(
        endpoint,
        params={"resource_id": resource_id},
        content=b"x" * (MAX_IMAGE_BYTES + 1),
    ).status_code == 413
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)
    assert client.put(
        endpoint,
        params={"resource_id": resource_id},
        content=_image_bytes("PNG", (1, 2, 3)),
    ).status_code == 413
    assert not list((tmp_path / "user-data" / "image-overrides").rglob("*.tmp"))


def test_atomic_replace_failure_preserves_previous_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path)
    resource_id = production_image_ids()[0]
    endpoint = "/api/image-resources/override"
    first = client.put(
        endpoint,
        params={"resource_id": resource_id},
        content=_image_bytes("PNG", (10, 20, 30)),
    )
    assert first.status_code == 200
    target = tmp_path / "user-data" / "image-overrides" / Path(*PurePosixPath(resource_id).parts)
    previous = target.read_bytes()

    def fail_replace(_source: Path, _target: Path) -> None:
        raise PermissionError("测试中的占用冲突")

    monkeypatch.setattr(image_resources_module.os, "replace", fail_replace)
    failed = client.put(
        endpoint,
        params={"resource_id": resource_id},
        content=_image_bytes("BMP", (200, 100, 50)),
    )
    assert failed.status_code == 409
    assert target.read_bytes() == previous
    assert not list(target.parent.glob(f".{target.name}.*.tmp"))


def test_existing_override_survives_service_restart(tmp_path: Path) -> None:
    """产品契约：升级或重启只重新枚举内置树，不重写用户覆盖。"""
    user_data = tmp_path / "user-data"
    resource_id = production_image_ids()[0]
    first = ImageResourceService(user_data)
    first.replace(resource_id, _image_bytes("PNG", (11, 22, 33)))

    restarted = ImageResourceService(user_data)
    assert restarted.describe(resource_id)["overridden"] is True
    assert restarted.content_path(resource_id).is_file()


def test_existing_override_survives_install_tree_change(tmp_path: Path) -> None:
    """产品契约：重新安装更换安装树后，同一 userData 覆盖继续生效。"""
    resource_id = "yys/example_script/images/template.bmp"
    user_data = tmp_path / "user-data"
    install_v1 = tmp_path / "install-v1"
    install_v2 = tmp_path / "install-v2"
    for install_root, color in (
        (install_v1, (10, 20, 30)),
        (install_v2, (200, 210, 220)),
    ):
        builtin = install_root / Path(*PurePosixPath(resource_id).parts)
        builtin.parent.mkdir(parents=True, exist_ok=True)
        builtin.write_bytes(_image_bytes("BMP", color))

    ImageResourceService(user_data, project_root=install_v1).replace(
        resource_id,
        _image_bytes("PNG", (40, 50, 60)),
    )

    reinstalled = ImageResourceService(user_data, project_root=install_v2)
    effective = reinstalled.content_path(resource_id)
    assert reinstalled.describe(resource_id)["overridden"] is True
    assert effective == user_data / "image-overrides" / Path(*PurePosixPath(resource_id).parts)
    with Image.open(effective) as image:
        assert image.getpixel((0, 0)) == (40, 50, 60)


def test_concurrent_reads_only_observe_complete_versions(tmp_path: Path) -> None:
    """产品契约：运行中替换时，读取方只能看到替换前或替换后的完整文件。"""
    user_data = tmp_path / "user-data"
    resource_id = production_image_ids()[0]
    service = ImageResourceService(user_data)
    first_payload = _image_bytes("PNG", (10, 20, 30))
    second_payload = _image_bytes("PNG", (200, 210, 220))
    service.replace(resource_id, first_payload)
    target = service.content_path(resource_id)
    before = target.read_bytes()
    service.replace(resource_id, second_payload)
    after = target.read_bytes()
    service.replace(resource_id, first_payload)

    replacement_error: ImageResourceError | None = None
    with target.open("rb") as reader:
        assert reader.read() == before
        reader.seek(0)
        try:
            service.replace(resource_id, second_payload)
        except ImageResourceError as exc:
            replacement_error = exc
        assert reader.read() == before

    if replacement_error is not None:
        assert replacement_error.status_code == 409
        assert target.read_bytes() == before
        service.replace(resource_id, second_payload)

    assert target.read_bytes() == after
