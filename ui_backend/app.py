from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image

from ui_backend.events.hub import EventHub
from ui_backend.image_resources import ImageResourceError, ImageResourceService, MAX_IMAGE_BYTES
from ui_backend.models import RunRequest, RunSourceType, ScriptDefinition
from ui_backend.runs.manager import RunManager
from ui_backend.scheduler.service import SchedulerService
from ui_backend.screenshots import MAX_SCREENSHOT_BYTES, ScreenshotError, ScreenshotService
from ui_backend.scripts.registry import ScriptRegistry
from ui_backend.storage.database import Database
from ui_backend.storage.repositories import Storage


ALLOWED_ORIGINS = [
    "null",
    "file://",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]


def create_app(
    db_path: Path | str | None = None,
    api_token: str | None = None,
    user_data_dir: Path | str | None = None,
) -> FastAPI:
    """创建桌面工作台 FastAPI 应用。"""
    resolved_token = api_token if api_token is not None else os.environ.get("YYS_UI_TOKEN")
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def require_ui_token(request: Request, call_next: Any) -> Any:
        """在启用 UI token 时保护本地控制 API。"""
        if request.method == "OPTIONS" or not request.url.path.startswith("/api/"):
            return await call_next(request)
        if not resolved_token:
            return await call_next(request)
        provided_token = request.headers.get("X-YYS-UI-Token") or request.query_params.get("token")
        if provided_token != resolved_token:
            return JSONResponse({"detail": "UI token 无效"}, status_code=403)
        return await call_next(request)

    database = Database(db_path or Path("config") / "ui_workbench.db")
    database.initialize()
    storage = Storage(database)
    storage.runs.mark_unfinished_as_error("后端重启，未完成运行已终止")
    registry = ScriptRegistry()
    event_hub = EventHub()
    resolved_user_data = (
        user_data_dir if user_data_dir is not None else os.environ.get("YYS_USER_DATA_DIR")
    )
    image_resources = ImageResourceService(
        resolved_user_data
    )
    screenshots = ScreenshotService(resolved_user_data)
    run_manager = RunManager(
        storage=storage,
        registry=registry,
        event_hub=event_hub,
        screenshot_service=screenshots,
    )
    scheduler = SchedulerService(run_manager, storage=storage, event_hub=event_hub)

    app.state.database = database
    app.state.storage = storage
    app.state.registry = registry
    app.state.event_hub = event_hub
    app.state.run_manager = run_manager
    app.state.scheduler = scheduler
    app.state.image_resources = image_resources
    app.state.screenshots = screenshots
    app.state.api_token = resolved_token

    @app.on_event("startup")
    async def start_scheduler() -> None:
        """在应用生命周期启动周期调度线程。"""
        app.state.scheduler.start()

    @app.on_event("shutdown")
    async def stop_scheduler() -> None:
        """在应用生命周期停止周期调度线程。"""
        app.state.scheduler.stop()

    @app.get("/api/scripts")
    def list_scripts() -> list[dict[str, Any]]:
        """列出可执行脚本定义。"""
        current_storage = app.state.storage
        return [
            _script_to_dict(item, user_config=current_storage.script_user_configs.get(item.script_id))
            for item in app.state.registry.list_scripts()
        ]

    @app.get("/api/image-resources")
    def list_image_resources() -> list[dict[str, Any]]:
        """列出当前安装树中的生产图片资源。"""
        return app.state.image_resources.list_resources()

    @app.get("/api/image-resources/content")
    def get_image_resource_content(
        resource_id: str,
        variant: str = "effective",
    ) -> FileResponse:
        """读取当前生效或安装包内置图片。"""
        try:
            path = app.state.image_resources.content_path(resource_id, variant)
        except ImageResourceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        with Image.open(path) as image:
            media_type = f"image/{image.format.lower()}"
        return FileResponse(path, media_type=media_type)

    @app.put("/api/image-resources/override")
    async def replace_image_resource(request: Request, resource_id: str) -> dict[str, Any]:
        """校验二进制图片并原子替换单个用户覆盖。"""
        payload = bytearray()
        try:
            async for chunk in request.stream():
                payload.extend(chunk)
                if len(payload) > MAX_IMAGE_BYTES:
                    raise ImageResourceError(
                        f"图片内容不能超过 {MAX_IMAGE_BYTES} 字节",
                        413,
                    )
            return app.state.image_resources.replace(resource_id, bytes(payload))
        except ImageResourceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @app.delete("/api/image-resources/override")
    def restore_image_resource(resource_id: str) -> dict[str, Any]:
        """删除单个用户覆盖并恢复安装包内置版本。"""
        try:
            return app.state.image_resources.restore(resource_id)
        except ImageResourceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @app.post("/api/screenshots/capture")
    def capture_screenshot() -> dict[str, Any]:
        """手动保存完整客户区；活动运行只复制现有缓存。"""
        try:
            return app.state.run_manager.capture_manual_screenshot()
        except ScreenshotError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={
                    "message": exc.detail,
                    "restore_required": exc.restore_required,
                },
            ) from exc

    @app.get("/api/screenshots")
    def list_screenshots() -> list[dict[str, Any]]:
        """列出 userData 中的永久截图。"""
        return app.state.screenshots.list()

    @app.get("/api/screenshots/{screenshot_id}/content")
    def get_screenshot_content(screenshot_id: str) -> FileResponse:
        """读取指定永久截图 PNG。"""
        try:
            path = app.state.screenshots.content_path(screenshot_id)
        except ScreenshotError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        return FileResponse(path, media_type="image/png", filename=path.name)

    @app.post("/api/screenshots/{screenshot_id}/crops")
    async def save_screenshot_crop(
        screenshot_id: str,
        request: Request,
    ) -> dict[str, Any]:
        """校验并保存 Cropper.js 输出的 PNG。"""
        payload = bytearray()
        try:
            async for chunk in request.stream():
                payload.extend(chunk)
                if len(payload) > MAX_SCREENSHOT_BYTES:
                    raise ScreenshotError(
                        f"裁剪图片不能超过 {MAX_SCREENSHOT_BYTES} 字节",
                        413,
                    )
            saved = app.state.screenshots.save_crop(screenshot_id, bytes(payload))
            app.state.run_manager.record_saved_screenshot(saved, "保存运行截图裁剪图")
            return saved
        except ScreenshotError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @app.delete("/api/screenshots/{screenshot_id}")
    def delete_screenshot(screenshot_id: str) -> dict[str, Any]:
        """只删除用户明确选中的一张截图。"""
        try:
            return app.state.screenshots.delete(screenshot_id)
        except ScreenshotError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @app.patch("/api/scripts/{script_id}/config")
    def patch_script_config(script_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """保存脚本最近一次配置（用户持久化偏好）。

        默默落盘 + 当前 run 忽略（plan §4 B2 决策）：
        - status: ok / invalid
        - saved: 是否成功落盘
        - applied: 是否已注入当前 run（当前为 False，构造注入不支持运行时改）
        - note: GUI 文案提示
        """
        if not isinstance(payload, dict):
            return {"status": "invalid", "applied": False}
        app.state.storage.script_user_configs.upsert(script_id, dict(payload))
        return {
            "status": "ok",
            "saved": True,
            "applied": False,
            "note": "配置已保存，下次启动生效",
        }

    @app.get("/api/runs/current")
    def get_current_run() -> dict[str, Any] | None:
        """读取当前运行中的脚本记录。"""
        current = app.state.storage.runs.current()
        return _run_with_runtime_evidence(app.state.storage, current)

    @app.get("/api/runs")
    def list_runs(
        script_id: str | None = None,
        source_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """查询历史运行摘要。"""
        return app.state.storage.runs.list_history(
            script_id=script_id,
            source_type=source_type,
            status=status,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/runs/{run_id}")
    def get_run_detail(run_id: int) -> dict[str, Any]:
        """读取单次运行的配置、日志、快照和证据。"""
        run = app.state.storage.runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        detail = _run_with_runtime_evidence(app.state.storage, run)
        detail["logs"] = app.state.storage.logs.list_by_run(run_id)
        detail["snapshots"] = _list_snapshots(app.state.storage, run_id)
        detail["evidence"] = app.state.storage.evidence.list_by_run(run_id)
        workflow_id = run.get("workflow_id")
        if workflow_id is not None:
            workflow = app.state.storage.workflows.get(int(workflow_id))
            if workflow is not None:
                detail["workflow"] = _workflow_with_steps(app.state.storage, workflow)
                step_id = run.get("step_id") or run.get("workflow_step_id")
                detail["workflow_step"] = next(
                    (
                        step
                        for step in detail["workflow"]["steps"]
                        if int(step["id"]) == int(step_id)
                    ),
                    None,
                ) if step_id is not None else None
        return detail

    @app.post("/api/runs/start")
    def start_run(payload: dict[str, Any]) -> dict[str, int]:
        """启动脚本运行。"""
        request = RunRequest(
            script_id=str(payload["script_id"]),
            config=dict(payload.get("config", {})),
            source_type=RunSourceType(str(payload.get("source_type", RunSourceType.MANUAL.value))),
            workflow_id=payload.get("workflow_id"),
            workflow_step_id=payload.get("workflow_step_id"),
            task_id=_optional_str(payload.get("task_id")),
            step_id=payload.get("step_id"),
            action_id=_optional_str(payload.get("action_id")),
            retry_count=int(payload.get("retry_count", 0)),
            parent_run_id=payload.get("parent_run_id"),
        )
        return {"id": app.state.run_manager.start(request)}

    @app.post("/api/runs/{run_id}/pause")
    def pause_run(run_id: int) -> dict[str, str]:
        """暂停脚本运行。"""
        app.state.run_manager.pause(run_id)
        return {"status": "ok"}

    @app.post("/api/runs/{run_id}/resume")
    def resume_run(run_id: int) -> dict[str, str]:
        """恢复脚本运行。"""
        app.state.run_manager.resume(run_id)
        return {"status": "ok"}

    @app.post("/api/runs/{run_id}/stop")
    def stop_run(run_id: int) -> dict[str, str]:
        """停止脚本运行。"""
        app.state.run_manager.stop(run_id)
        return {"status": "ok"}

    @app.post("/api/runs/{run_id}/continue-waiting")
    def continue_waiting_run(run_id: int) -> dict[str, str]:
        """战斗安全等待超时后，继续等待一个 3 分钟窗口（AC4）。"""
        try:
            app.state.run_manager.continue_waiting(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"status": "ok"}

    @app.post("/api/runs/{run_id}/retry")
    def retry_run(run_id: int) -> dict[str, int]:
        """重试失败运行。"""
        try:
            return {"id": app.state.run_manager.retry(run_id)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/runs/{run_id}/skip")
    def skip_run(run_id: int) -> dict[str, str]:
        """跳过失败运行。"""
        try:
            app.state.run_manager.skip(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"status": "ok"}

    @app.post("/api/runs/{run_id}/manual-takeover")
    def manual_takeover_run(run_id: int) -> dict[str, str]:
        """将失败运行转入人工接管。"""
        try:
            app.state.run_manager.manual_takeover(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"status": "ok"}

    @app.get("/api/runs/{run_id}/logs")
    def list_run_logs(run_id: int) -> list[dict[str, Any]]:
        """列出指定运行记录的日志。"""
        return app.state.storage.logs.list_by_run(run_id)

    @app.get("/api/runs/{run_id}/snapshots")
    def list_run_snapshots(run_id: int) -> list[dict[str, Any]]:
        """读取指定运行记录的全部状态快照。"""
        return app.state.storage.snapshots.list_by_run(run_id)

    @app.get("/api/runs/{run_id}/evidence")
    def list_run_evidence(run_id: int) -> list[dict[str, Any]]:
        """读取某次运行的截图和证据记录。"""
        if app.state.storage.runs.get(run_id) is None:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        return app.state.storage.evidence.list_by_run(run_id)

    @app.get("/api/runs/{run_id}/evidence/latest")
    def get_latest_run_evidence(run_id: int) -> FileResponse:
        """返回某次运行最新的可读截图。"""
        evidence = app.state.storage.evidence.latest_by_run(run_id)
        path = Path(str(evidence.get("path"))) if evidence and evidence.get("path") else None
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="暂无可读取截图")
        return FileResponse(path, media_type="image/png", filename=path.name)

    @app.get("/api/workflows")
    def list_workflows() -> list[dict[str, Any]]:
        """列出全部编排任务。"""
        current_storage = app.state.storage
        return [
            _workflow_with_steps(current_storage, workflow)
            for workflow in current_storage.workflows.list_all()
        ]

    @app.post("/api/workflows")
    def create_workflow(payload: dict[str, Any]) -> dict[str, int]:
        """创建编排任务及其步骤。"""
        current_storage = app.state.storage
        workflow_id = current_storage.workflows.create(
            name=str(payload["name"]),
            group_name=str(payload["group_name"]),
            enabled=bool(payload["enabled"]),
            trigger_type=str(payload["trigger_type"]),
            trigger_config=dict(payload.get("trigger_config", {})),
            failure_policy=str(payload["failure_policy"]),
            priority=int(payload.get("priority", 0)),
            success_interval_seconds=float(payload.get("success_interval_seconds", 0)),
            failure_interval_seconds=float(payload.get("failure_interval_seconds", 0)),
            next_run_at=_optional_str(payload.get("next_run_at"))
            or _next_workflow_run_at(app.state.scheduler, payload, bool(payload["enabled"])),
        )
        for step in payload.get("steps", []):
            current_storage.workflow_steps.create(
                workflow_id=workflow_id,
                sort_order=int(step["sort_order"]),
                step_type=str(step["step_type"]),
                script_id=_optional_str(step.get("script_id")),
                config=dict(step.get("config", {})),
                condition=dict(step.get("condition", {})),
                retry_count=int(step.get("retry_count", 0)),
                failure_policy=str(step.get("failure_policy", "inherit")),
            )
        return {"id": workflow_id}

    @app.put("/api/workflows/{workflow_id}", response_model=None)
    def update_workflow(workflow_id: int, payload: dict[str, Any]) -> dict[str, str] | JSONResponse:
        """全量覆盖编排任务及其步骤（单事务原子）。"""
        current_storage = app.state.storage
        found = current_storage.workflows.update_with_steps(
            workflow_id=workflow_id,
            name=str(payload["name"]),
            group_name=str(payload["group_name"]),
            enabled=bool(payload["enabled"]),
            trigger_type=str(payload["trigger_type"]),
            trigger_config=dict(payload.get("trigger_config", {})),
            failure_policy=str(payload["failure_policy"]),
            steps=list(payload.get("steps", [])),
            priority=int(payload.get("priority", 0)),
            success_interval_seconds=float(payload.get("success_interval_seconds", 0)),
            failure_interval_seconds=float(payload.get("failure_interval_seconds", 0)),
            next_run_at=_next_workflow_run_at(app.state.scheduler, payload, bool(payload["enabled"])),
        )
        if not found:
            return JSONResponse({"detail": "编排任务不存在"}, status_code=404)
        return {"status": "ok"}

    @app.delete("/api/workflows/{workflow_id}", response_model=None)
    def delete_workflow(workflow_id: int) -> dict[str, str] | JSONResponse:
        """删除编排任务（连同步骤），有活动运行则拒绝。"""
        current_storage = app.state.storage
        if current_storage.workflows.has_active_run(workflow_id):
            return JSONResponse({"detail": "存在运行中的关联任务，无法删除"}, status_code=409)
        # 先删 steps
        current_storage.workflow_steps.delete_by_workflow(workflow_id)
        found = current_storage.workflows.delete(workflow_id)
        if not found:
            return JSONResponse({"detail": "编排任务不存在"}, status_code=404)
        return {"status": "ok"}

    @app.post("/api/workflows/{workflow_id}/run-now")
    def run_workflow_now(workflow_id: int) -> dict[str, str]:
        """立即执行指定编排任务。"""
        current_storage = app.state.storage
        workflow = _find_workflow(current_storage, workflow_id)
        if workflow is None:
            return {"status": "not_found"}
        workflow = _workflow_with_steps(current_storage, workflow)
        thread = threading.Thread(
            target=_run_workflow_in_background,
            args=(app, workflow),
            daemon=True,
        )
        thread.start()
        return {"status": "started"}

    @app.post("/api/workflows/{workflow_id}/enable", response_model=None)
    def enable_workflow(workflow_id: int) -> dict[str, str] | JSONResponse:
        """启用周期工作流。"""
        return _set_workflow_enabled(app.state.storage, app.state.scheduler, workflow_id, True)

    @app.post("/api/workflows/{workflow_id}/disable", response_model=None)
    def disable_workflow(workflow_id: int) -> dict[str, str] | JSONResponse:
        """停用周期工作流。"""
        return _set_workflow_enabled(app.state.storage, app.state.scheduler, workflow_id, False)

    @app.get("/api/workflows/{workflow_id}/schedule-preview", response_model=None)
    def workflow_schedule_preview(workflow_id: int) -> dict[str, Any] | JSONResponse:
        """返回单个工作流的下一次运行预览。"""
        workflow = _find_workflow(app.state.storage, workflow_id)
        if workflow is None:
            return JSONResponse({"detail": "编排任务不存在"}, status_code=404)
        return app.state.scheduler.preview_workflow(workflow)

    @app.get("/api/scheduler/preview")
    def scheduler_preview() -> list[dict[str, Any]]:
        """返回全部已启用工作流的调度预览。"""
        return [
            app.state.scheduler.preview_workflow(workflow)
            for workflow in app.state.storage.workflows.list_all()
            if workflow.get("enabled")
        ]

    @app.websocket("/ws/events")
    async def events_websocket(websocket: WebSocket) -> None:
        """推送近期事件并保持 WebSocket 连接。"""
        if resolved_token and websocket.query_params.get("token") != resolved_token:
            await websocket.close(code=1008)
            return
        current_event_hub = app.state.event_hub
        await current_event_hub.connect(websocket)
        try:
            current = _run_with_runtime_evidence(
                app.state.storage,
                app.state.storage.runs.current(),
            )
            after_seq_raw = websocket.query_params.get("after_seq")
            after_seq = int(after_seq_raw) if after_seq_raw else None
            bootstrap_events = current_event_hub.recent_events(after_seq=after_seq)
            snapshot_event: dict[str, Any] = {
                "type": "run_snapshot",
                "snapshot": current,
                "run_id": current.get("run_id") if current else None,
            }
            # 保留旧客户端把首条无活动事件当作日志读取的兼容字段。
            if current is None and bootstrap_events:
                first_message = bootstrap_events[0].get("message")
                if first_message is not None:
                    snapshot_event["message"] = first_message
            await websocket.send_json(snapshot_event)
            for event in bootstrap_events:
                await websocket.send_json(event)
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await current_event_hub.disconnect(websocket)

    return app


def _script_to_dict(item: ScriptDefinition, user_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """将脚本定义转换为 API 字典。"""
    return {
        "script_id": item.script_id,
        "display_name": item.display_name,
        "module_path": item.module_path,
        "class_name": item.class_name,
        "category": item.category,
        "description": item.description,
        "config_schema": [field.__dict__ for field in item.config_schema],
        "default_config": {**(item.default_config or {}), **(user_config or {})},
    }


def _optional_str(value: Any) -> str | None:
    """将可空值转换为字符串。"""
    if value is None:
        return None
    return str(value)


def _workflow_with_steps(storage: Storage, workflow: dict[str, Any]) -> dict[str, Any]:
    """为编排任务附加步骤列表。"""
    item = dict(workflow)
    workflow_id = int(item["id"])
    item["steps"] = storage.workflow_steps.list_by_workflow(workflow_id)
    return item


def _run_with_runtime_evidence(
    storage: Storage,
    run: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """把数据库 run 补齐当前快照和证据，供 API/WebSocket 共用。"""
    if run is None:
        return None
    item = dict(run)
    run_id = int(item["id"])
    item["latest_snapshot"] = storage.snapshots.latest_by_run(run_id)
    item["evidence"] = storage.evidence.list_by_run(run_id)
    return item


def _list_snapshots(storage: Storage, run_id: int) -> list[dict[str, Any]]:
    """返回历史详情可用的状态快照列表。"""
    return storage.snapshots.list_by_run(run_id)


def _run_workflow_in_background(app: FastAPI, workflow: dict[str, Any]) -> None:
    """在线程中执行编排任务，并将后台异常发布到事件流。"""
    try:
        app.state.scheduler.run_workflow_now(workflow)
    except Exception as exc:
        app.state.event_hub.publish_from_thread(
            {
                "type": "workflow_error",
                "workflow_id": workflow.get("id"),
                "message": f"编排执行失败: {exc}",
            }
        )


def _find_workflow(storage: Storage, workflow_id: int) -> dict[str, Any] | None:
    """按 ID 从编排任务列表中查找任务。"""
    for workflow in storage.workflows.list_all():
        if int(workflow["id"]) == workflow_id:
            return workflow
    return None


def _set_workflow_enabled(
    storage: Storage,
    scheduler: SchedulerService,
    workflow_id: int,
    enabled: bool,
) -> dict[str, str] | JSONResponse:
    """更新工作流启用状态。"""
    workflow = storage.workflows.get(workflow_id)
    if workflow is None:
        return JSONResponse({"detail": "编排任务不存在"}, status_code=404)
    found = storage.workflows.update(
        workflow_id=workflow_id,
        name=str(workflow["name"]),
        group_name=str(workflow["group_name"]),
        enabled=enabled,
        trigger_type=str(workflow["trigger_type"]),
        trigger_config=dict(workflow.get("trigger_config", {})),
        failure_policy=str(workflow["failure_policy"]),
        priority=int(workflow.get("priority", 0)),
        success_interval_seconds=float(workflow.get("success_interval_seconds", 0)),
        failure_interval_seconds=float(workflow.get("failure_interval_seconds", 0)),
        next_run_at=_next_workflow_run_at(scheduler, workflow, enabled),
    )
    return {"status": "ok"} if found else JSONResponse({"detail": "编排任务不存在"}, status_code=404)


def _next_workflow_run_at(
    scheduler: SchedulerService, workflow: dict[str, Any], enabled: bool,
) -> str | None:
    """校验并计算启用工作流的下一次计划时间。"""
    if not enabled or workflow["trigger_type"] == "manual":
        return None
    try:
        next_run_at = scheduler.calculate_next_run_at(workflow)
    except (TypeError, ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if next_run_at is None:
        raise HTTPException(status_code=422, detail="定时触发配置无效")
    return next_run_at
