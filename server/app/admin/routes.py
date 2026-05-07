"""Admin HTTP routes."""
from __future__ import annotations

import re
import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request

from app.admin.views import (
    COOKIE_NAME,
    _admin_password,
    _blank_feature,
    _dashboard_page,
    _doc_from_patch,
    _edit_page,
    _features_page,
    _form_patch,
    _login_page,
    _message,
    _redirect,
    _require_auth,
    _serializer,
    _storage_page,
    _tasks_page,
    _transactions_page,
    _user_detail_page,
    _users_page,
)
from app.cloudbase.client import CloudBaseError
from app.cloudbase.nosql import get_feature_store, get_user_store
from app.cloudbase.storage import get_storage


router = APIRouter()


@router.get("/")
async def admin_home(request: Request):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    return _redirect("/admin/dashboard")


@router.get("/dashboard")
async def dashboard(request: Request):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    try:
        features = get_feature_store().list_features()
        features_enabled = len([item for item in features if item.get("enabled")])
        summary = get_user_store().dashboard()
        return _dashboard_page(summary, len(features), features_enabled)
    except CloudBaseError as exc:
        return _dashboard_page({}, 0, 0, str(exc))


@router.get("/login")
async def login_get():
    return _login_page()


@router.post("/login")
async def login_post(request: Request):
    form = await request.form()
    password = str(form.get("password", ""))
    if not _admin_password() or password != _admin_password():
        return _login_page("密码不正确")

    response = _redirect("/admin/dashboard")
    response.set_cookie(
        COOKIE_NAME,
        _serializer().dumps("admin"),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return response


@router.get("/logout")
async def logout():
    response = _redirect("/admin/login")
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/users")
async def users(request: Request):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    filters = _page_filters(request, "openid", "nick_name")
    try:
        page = int(filters["page"])
        page_size = int(filters["page_size"])
        items, total = get_user_store().list_users(
            openid=str(filters.get("openid") or ""),
            nick_name=str(filters.get("nick_name") or ""),
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return _users_page(items, total, filters)
    except CloudBaseError as exc:
        return _users_page([], 0, filters, str(exc))


@router.get("/users/{user_id}")
async def user_detail(request: Request, user_id: str):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    try:
        store = get_user_store()
        user = store.get_user(user_id)
        return _user_detail_page(
            user,
            message=_message(request.query_params.get("status")),
        )
    except CloudBaseError as exc:
        filters = _page_filters(request, "openid", "nick_name")
        return _users_page([], 0, filters, str(exc))


def _page_filters(request: Request, *names: str) -> dict[str, Any]:
    filters: dict[str, Any] = {name: str(request.query_params.get(name, "")).strip() for name in names}
    try:
        page = max(1, int(request.query_params.get("page", "1")))
    except ValueError:
        page = 1
    try:
        page_size = min(100, max(1, int(request.query_params.get("page_size", "20"))))
    except ValueError:
        page_size = 20
    filters["page"] = page
    filters["page_size"] = page_size
    return filters


@router.get("/transactions")
async def transactions(request: Request):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    filters = _page_filters(request, "openid", "reason", "tx_type", "task_id")
    try:
        page = int(filters["page"])
        page_size = int(filters["page_size"])
        items, total = get_user_store().list_transactions(
            openid=str(filters.get("openid") or ""),
            reason=str(filters.get("reason") or ""),
            tx_type=str(filters.get("tx_type") or ""),
            task_id=str(filters.get("task_id") or ""),
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return _transactions_page(items, total, filters)
    except CloudBaseError as exc:
        return _transactions_page([], 0, filters, str(exc))


@router.get("/tasks")
async def tasks(request: Request):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    filters = _page_filters(request, "openid", "status", "feature_type", "task_id", "points_consumed", "points_refunded")
    try:
        page = int(filters["page"])
        page_size = int(filters["page_size"])
        items, total = get_user_store().list_tasks(
            openid=str(filters.get("openid") or ""),
            status=str(filters.get("status") or ""),
            feature_type=str(filters.get("feature_type") or ""),
            task_id=str(filters.get("task_id") or ""),
            points_consumed=str(filters.get("points_consumed") or ""),
            points_refunded=str(filters.get("points_refunded") or ""),
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return _tasks_page(items, total, filters)
    except CloudBaseError as exc:
        return _tasks_page([], 0, filters, str(exc))


@router.post("/tasks/preview")
async def task_preview(request: Request):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    form = await request.form()
    task_id = str(form.get("preview_task_id", "")).strip()
    field = str(form.get("field", "")).strip()
    filters = {
        "openid": str(form.get("openid", "")).strip(),
        "status": str(form.get("status", "")).strip(),
        "feature_type": str(form.get("feature_type", "")).strip(),
        "task_id": str(form.get("task_id", "")).strip(),
        "points_consumed": str(form.get("points_consumed", "")).strip(),
        "points_refunded": str(form.get("points_refunded", "")).strip(),
        "page": int(str(form.get("page", "1")).strip() or "1"),
        "page_size": int(str(form.get("page_size", "20")).strip() or "20"),
    }
    if field not in {"fileID", "posterFileID"}:
        return _tasks_page([], 0, filters, "不支持的文件字段")
    try:
        store = get_user_store()
        page = int(filters["page"])
        page_size = int(filters["page_size"])
        tasks_page, total = store.list_tasks(
            openid=str(filters.get("openid") or ""),
            status=str(filters.get("status") or ""),
            feature_type=str(filters.get("feature_type") or ""),
            task_id=str(filters.get("task_id") or ""),
            points_consumed=str(filters.get("points_consumed") or ""),
            points_refunded=str(filters.get("points_refunded") or ""),
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        task = store.get_task(task_id)
        file_id = str(task.get(field) or "")
        if not file_id:
            return _tasks_page(tasks_page, total, filters, "当前任务没有这个文件")
        if not file_id.startswith("cloud://"):
            return _tasks_page(tasks_page, total, filters, preview={"task_id": task_id, "field": field, "file_id": file_id, "url": file_id})
        url = get_storage().get_download_url(file_id)
        if not url:
            return _tasks_page(tasks_page, total, filters, "未获取到下载链接")
        return _tasks_page(
            tasks_page,
            total,
            filters,
            preview={"task_id": task_id, "field": field, "file_id": file_id, "url": url},
        )
    except CloudBaseError as exc:
        return _tasks_page([], 0, filters, str(exc))


@router.get("/storage")
async def storage_home(request: Request):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    return _storage_page()


@router.post("/storage/download-info")
async def storage_download_info(request: Request):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    form = await request.form()
    cloud_object_id = str(form.get("cloud_object_id", "")).strip()
    try:
        if not cloud_object_id.startswith("cloud://"):
            raise ValueError("Cloud Object ID 必须以 cloud:// 开头")
        info = get_storage().get_download_info([cloud_object_id])
        return _storage_page(cloud_object_id=cloud_object_id, download_info=info)
    except (CloudBaseError, ValueError) as exc:
        return _storage_page(cloud_object_id=cloud_object_id, error=str(exc))


@router.post("/storage/upload-info")
async def storage_upload_info(request: Request):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    form = await request.form()
    object_id = str(form.get("object_id", "")).strip().lstrip("/")
    try:
        if not object_id:
            raise ValueError("对象路径不能为空")
        info = get_storage().get_upload_info([object_id])
        return _storage_page(object_id=object_id, upload_info=info)
    except (CloudBaseError, ValueError) as exc:
        return _storage_page(object_id=object_id, error=str(exc))


@router.post("/users/{user_id}/points")
async def user_adjust_points(request: Request, user_id: str):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    store = get_user_store()
    form = await request.form()
    try:
        if str(form.get("confirm_user_id", "")).strip() != user_id:
            raise ValueError("确认用户 ID 必须与当前用户 ID 一致")
        amount = int(str(form.get("amount", "")).strip())
        if amount == 0:
            raise ValueError("调整数量不能为 0")
        reason = str(form.get("reason", "")).strip()
        if len(reason) < 3:
            raise ValueError("调整原因至少 3 个字符")
        operator = str(form.get("operator", "admin")).strip() or "admin"
        store.adjust_points(user_id, amount, reason, operator)
    except (CloudBaseError, ValueError) as exc:
        user = store.get_user(user_id)
        return _user_detail_page(
            user,
            error=str(exc),
        )
    return _redirect(f"/admin/users/{user_id}?status=points_adjusted")


@router.get("/features")
async def features(request: Request):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    try:
        return _features_page(
            get_feature_store().list_features(),
            message=_message(request.query_params.get("status")),
        )
    except CloudBaseError as exc:
        return _features_page([], str(exc))


@router.get("/features/new")
async def feature_new(request: Request):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    return _edit_page(_blank_feature(), is_new=True)


@router.post("/features")
async def feature_create(request: Request):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    form = dict(await request.form())
    try:
        doc_id = str(form.get("_id", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,64}", doc_id):
            raise ValueError("_id 只能包含字母、数字、连字符、下划线，长度 3-64")
        patch = _form_patch(form)
        document = _doc_from_patch(doc_id, patch)
        document["createdAt"] = int(time.time() * 1000)
        get_feature_store().create_feature(document)
    except (CloudBaseError, ValueError) as exc:
        fallback_id = str(form.get("_id", "")).strip() or f"test_{uuid4().hex[:12]}"
        try:
            doc = _doc_from_patch(fallback_id, _form_patch(form))
        except ValueError:
            doc = _blank_feature()
            doc["_id"] = fallback_id
        return _edit_page(doc, str(exc), is_new=True)
    return _redirect("/admin/features?status=created")


@router.get("/features/{doc_id}")
async def feature_edit(request: Request, doc_id: str):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    try:
        return _edit_page(get_feature_store().get_feature(doc_id))
    except CloudBaseError as exc:
        return _features_page([], str(exc))


@router.post("/features/{doc_id}")
async def feature_save(request: Request, doc_id: str):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    form = dict(await request.form())
    try:
        patch = _form_patch(form)
        get_feature_store().update_feature(doc_id, patch)
    except (CloudBaseError, ValueError) as exc:
        doc = get_feature_store().get_feature(doc_id)
        return _edit_page(doc, str(exc))
    return _redirect("/admin/features?status=saved")


@router.post("/features/{doc_id}/delete")
async def feature_delete(request: Request, doc_id: str):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    form = await request.form()
    if str(form.get("confirm_delete", "")).strip() != doc_id:
        doc = get_feature_store().get_feature(doc_id)
        return _edit_page(doc, "删除确认必须填写当前文档 ID")
    try:
        get_feature_store().delete_feature(doc_id)
    except CloudBaseError as exc:
        doc = get_feature_store().get_feature(doc_id)
        return _edit_page(doc, str(exc))
    return _redirect("/admin/features?status=deleted")
