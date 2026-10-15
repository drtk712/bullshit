"""Miniapp photo upload through the server storage credential.

The CloudBase env lives on Tencent Cloud and is not linked to the mini program
appid, so ``wx.cloud.uploadFile`` cannot see the bucket. This route stores the
bytes in the environment's traditional COS bucket and returns a classic
``cloud://{envId}.{bucket}/...`` file ID.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from starlette.datastructures import UploadFile

from app.api.deps import require_openid
from app.cloudbase.client import CloudBaseError
from app.cloudbase.storage import get_storage
from app.core.redact import redact_secrets


router = APIRouter(prefix="/miniapp")
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


@router.post("/upload")
async def upload_photo(request: Request) -> dict[str, object]:
    require_openid(request)
    try:
        content = await _read_image(request)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    extension, mime = _image_type(content)
    object_id = f"uploads/{uuid4().hex}{extension}"
    try:
        file_id = await asyncio.to_thread(get_storage().upload_bytes, object_id, content, mime)
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=redact_secrets(str(exc))) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=redact_secrets(str(exc))) from exc
    if not str(file_id).startswith("cloud://"):
        raise HTTPException(status_code=502, detail="上传云存储失败")
    return {"success": True, "data": {"fileID": file_id}}


async def _read_image(request: Request) -> bytes:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type.startswith("multipart/"):
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(status_code=400, detail="缺少图片文件")
        content = await upload.read()
    elif content_type == "application/json":
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="图片数据无效") from exc
        content = _decode_base64(payload)
    elif content_type.startswith("image/") or content_type in {"", "application/octet-stream"}:
        content = await request.body()
    else:
        raise HTTPException(status_code=415, detail="不支持的上传格式")
    if not content:
        raise HTTPException(status_code=400, detail="图片为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="图片不能超过 8MB")
    return content


def _decode_base64(payload: object) -> bytes:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="图片数据无效")
    encoded = str(payload.get("contentBase64") or payload.get("image") or "").strip()
    if encoded.startswith("data:") and "," in encoded:
        encoded = encoded.split(",", 1)[1]
    if len(encoded) > MAX_UPLOAD_BYTES * 2:
        raise HTTPException(status_code=400, detail="图片不能超过 8MB")
    try:
        return base64.b64decode(encoded, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="图片数据无效") from exc


def _image_type(content: bytes) -> tuple[str, str]:
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return ".webp", "image/webp"
    raise HTTPException(status_code=400, detail="仅支持 JPG、PNG、WebP")
