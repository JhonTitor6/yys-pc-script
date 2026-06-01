from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ui_backend.events.hub import EventHub
from ui_backend.models import RunRequest, ScriptDefinition
from ui_backend.runs.manager import RunManager
from ui_backend.scheduler.service import SchedulerService
from ui_backend.scripts.registry import ScriptRegistry
from ui_backend.storage.database import Database
from ui_backend.storage.repositories import Storage


ALLOWED_ORIGINS = [
    "null",
    "file://",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]


def create_app(db_path: Path | str | None = None, api_token: str | None = None) -> FastAPI:
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
    run_manager = RunManager(storage=storage, registry=registry, event_hub=event_hub)
    scheduler = SchedulerService(run_manager)

    app.state.database = database
    app.state.storage = storage
    app.state.registry = registry
    app.state.event_hub = event_hub
    app.state.run_manager = run_manager
    app.state.scheduler = scheduler
    app.state.api_token = resolved_token

    @app.get("/api/scripts")
    def list_scripts() -> list[dict[str, Any]]:
        """列出可执行脚本定义。"""
        current_storage = app.state.storage
        return [
            _script_to_dict(item, user_config=current_storage.script_user_configs.get(item.script_id))
            for item in app.state.registry.list_scripts()
        ]

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
        return app.state.storage.runs.current()

    @app.post("/api/runs/start")
    def start_run(payload: dict[str, Any]) -> dict[str, int]:
        """启动脚本运行。"""
        request = RunRequest(
            script_id=str(payload["script_id"]),
            config=dict(payload.get("config", {})),
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

    @app.get("/api/runs/{run_id}/logs")
    def list_run_logs(run_id: int) -> list[dict[str, Any]]:
        """列出指定运行记录的日志。"""
        return app.state.storage.logs.list_by_run(run_id)

    @app.get("/api/runs/{run_id}/snapshots")
    def list_run_snapshots(run_id: int) -> list[dict[str, Any]]:
        """读取指定运行记录的最新状态快照。"""
        latest = app.state.storage.snapshots.latest_by_run(run_id)
        if latest is None:
            return []
        return [latest]

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

    @app.websocket("/ws/events")
    async def events_websocket(websocket: WebSocket) -> None:
        """推送近期事件并保持 WebSocket 连接。"""
        if resolved_token and websocket.query_params.get("token") != resolved_token:
            await websocket.close(code=1008)
            return
        current_event_hub = app.state.event_hub
        await current_event_hub.connect(websocket)
        try:
            for event in current_event_hub.recent_events():
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
