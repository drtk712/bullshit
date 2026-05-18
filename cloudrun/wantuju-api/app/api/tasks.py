"""Feature job task routes."""
from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query, Request

from app.api.deps import require_openid
from app.cloudbase.client import CloudBaseError
from app.services.tasks import JobCreationError, TaskService


router = APIRouter(prefix="/miniapp")


class CreateTaskRequest(BaseModel):
    type: str
    fileID: str = ""
    fileIDs: list[str] = Field(default_factory=list)
    param: dict[str, object] = Field(default_factory=dict)


@router.post("/tasks")
async def create_task(request: Request, body: CreateTaskRequest) -> dict[str, object]:
    service = TaskService()
    file_ids = body.fileIDs or ([body.fileID] if body.fileID else [])
    try:
        openid = require_openid(request)
        data = await service.create_job(
            openid,
            feature_type=body.type,
            file_id=body.fileID,
            file_ids=body.fileIDs,
            param=body.param,
        )
        return {"success": True, "data": data}
    except JobCreationError as exc:
        if exc.cleanup_uploads:
            service.cleanup_uploads(file_ids)
        return {"success": False, "errMsg": str(exc)}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/tasks/v2")
async def create_task_v2(request: Request, body: CreateTaskRequest) -> dict[str, object]:
    service = TaskService()
    file_ids = body.fileIDs or ([body.fileID] if body.fileID else [])
    try:
        openid = require_openid(request)
        data = await service.create_job_v2(
            openid,
            feature_type=body.type,
            file_id=body.fileID,
            file_ids=body.fileIDs,
            param=body.param,
        )
        return {"success": True, "data": data}
    except JobCreationError as exc:
        if exc.cleanup_uploads:
            service.cleanup_uploads(file_ids)
        return {"success": False, "errMsg": str(exc)}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/tasks")
async def tasks(
    request: Request,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=5, ge=1, le=50),
    filter: str = Query(default="all"),
) -> dict[str, object]:
    try:
        openid = require_openid(request)
        data = TaskService().list_tasks(openid, page=page, page_size=pageSize, status_filter=filter)
        return {"success": True, "data": data}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/tasks/{task_id}")
async def task_detail(request: Request, task_id: str) -> dict[str, object]:
    try:
        openid = require_openid(request)
        task = TaskService().get_task(openid, task_id)
        if not task:
            return {"success": False, "errMsg": "任务不存在"}
        return {"success": True, "data": {"task": task}}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/status")
async def task_status(request: Request, task_id: str) -> dict[str, object]:
    try:
        openid = require_openid(request)
        status = TaskService().get_task_status(openid, task_id)
        if not status:
            return {"success": False, "errMsg": "任务不存在"}
        return {"success": True, "data": status}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/shared-tasks/{task_id}")
async def shared_task(task_id: str) -> dict[str, object]:
    try:
        task = TaskService().get_shared_task(task_id)
        if not task:
            return {"success": False, "errMsg": "图片暂不可查看"}
        return {"success": True, "data": {"task": task}}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/tasks/{task_id}")
async def delete_task(request: Request, task_id: str) -> dict[str, object]:
    try:
        openid = require_openid(request)
        data = TaskService().delete_task(openid, task_id)
        return {"success": True, "data": data}
    except ValueError as exc:
        return {"success": False, "errMsg": str(exc)}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
