"""Traditional CloudBase COS storage.

PostgreSQL on this environment is only the database. Object bytes go to the
environment's legacy COS bucket (EnvInfo Storages), the same bucket the old
system used. The gateway route ``/v1/storages/get-objects-upload-info`` on a
PG environment answers with the default PG bucket (``cloud://wantuju/...``),
which ``wx.cloud.getTempFileURL`` cannot resolve.

The upload path is the one ``@cloudbase/node-sdk`` ``uploadFile`` uses when
``CLOUDBASE_APIKEY`` is set: ``POST https://{env}.{region}.tcb-api.tencentcloudapi.com/admin``
with ``action=storage.getUploadMetadata`` and ``Authorization: Bearer``.
That returns a classic ``cloud://{envId}.{bucket}/{path}`` file ID and a COS
PUT URL for the EnvInfo bucket. Download and delete use the matching admin
actions ``storage.batchGetDownloadUrl`` and ``storage.batchDeleteFile``.

PG storage (``storage.buckets``, ``/v1/storages/object/{bucket}``,
``/v1/storages/bucket/``) is not used.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.cloudbase.client import CloudBaseClient, CloudBaseError


DEFAULT_STORAGE_BUCKET = "7761-wantuju-prod-d2gf1sf2r508a56b1-1427592986"
DEFAULT_REGION = "ap-shanghai"
TEMP_URL_MAX_AGE = 3600


def storage_bucket() -> str:
    return os.getenv("CLOUDBASE_STORAGE_BUCKET", DEFAULT_STORAGE_BUCKET).strip() or DEFAULT_STORAGE_BUCKET


def storage_region() -> str:
    return os.getenv("CLOUDBASE_REGION", DEFAULT_REGION).strip() or DEFAULT_REGION


def classic_file_id(file_id: str, *, env_id: str, bucket: str) -> str:
    """Accept only ``cloud://{env}.{traditionalBucket}/path``."""
    prefix = f"cloud://{env_id}.{bucket}/"
    if not isinstance(file_id, str) or not file_id.startswith(prefix) or file_id == prefix:
        raise RuntimeError("云存储返回的不是传统云存储 fileID")
    return file_id


class CloudBaseStorage:
    def __init__(self, client: CloudBaseClient | None = None):
        self.client = client or CloudBaseClient()

    def get_download_info(self, cloud_object_ids: list[str]) -> list[dict[str, Any]]:
        objects = [item for item in cloud_object_ids if isinstance(item, str) and item.startswith("cloud://")]
        if not objects:
            return []
        payload = self._admin(
            "storage.batchGetDownloadUrl",
            {"file_list": [{"fileid": item, "max_age": TEMP_URL_MAX_AGE} for item in objects]},
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        raw = []
        if isinstance(data, dict):
            raw = data.get("download_list") or data.get("fileList") or []
        elif isinstance(data, list):
            raw = data
        if not isinstance(raw, list):
            return []
        items: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            file_id = str(item.get("fileID") or item.get("fileid") or item.get("fileId") or "")
            url = str(
                item.get("tempFileURL")
                or item.get("tempFileUrl")
                or item.get("download_url")
                or item.get("downloadUrl")
                or ""
            )
            items.append(
                {
                    "fileID": file_id,
                    "cloudObjectId": file_id,
                    "downloadUrl": url,
                    "tempFileURL": url,
                    "code": item.get("code") or "",
                }
            )
        return items

    def get_download_urls(self, cloud_object_ids: list[str]) -> list[str]:
        info_list = self.get_download_info(cloud_object_ids)
        url_map: dict[str, str] = {}
        ordered_urls: list[str] = []
        for item in info_list:
            file_id = str(item.get("fileID") or "")
            url = str(item.get("downloadUrl") or "")
            if url.startswith("https://"):
                ordered_urls.append(url)
            if file_id and url.startswith("https://"):
                url_map[file_id] = url
        if url_map:
            return [url_map.get(file_id, "") for file_id in cloud_object_ids]
        return ordered_urls[: len(cloud_object_ids)]

    def get_download_url(self, cloud_object_id: str) -> str:
        urls = self.get_download_urls([cloud_object_id])
        return urls[0] if urls else ""

    def delete_objects(self, cloud_object_ids: list[str]) -> list[dict[str, Any]]:
        objects = [item for item in cloud_object_ids if isinstance(item, str) and item.startswith("cloud://")]
        if not objects:
            return []
        payload = self._admin("storage.batchDeleteFile", {"fileid_list": objects})
        data = payload.get("data") if isinstance(payload, dict) else None
        raw = data.get("delete_list") if isinstance(data, dict) else data
        return raw if isinstance(raw, list) else []

    def get_upload_info(self, object_ids: list[str]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for object_id in object_ids:
            path = str(object_id or "").lstrip("/")
            if not path:
                continue
            payload = self._admin("storage.getUploadMetadata", {"path": path, "method": "put"})
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, dict):
                raise RuntimeError("未获取到上传授权信息")
            file_id = classic_file_id(
                str(data.get("fileId") or data.get("fileID") or ""),
                env_id=self.client.env_id,
                bucket=storage_bucket(),
            )
            upload_url = str(data.get("url") or data.get("uploadUrl") or "")
            authorization = str(data.get("authorization") or "")
            token = str(data.get("token") or "")
            cloud_object_meta = str(data.get("cosFileId") or data.get("cosFileID") or data.get("cloudObjectMeta") or "")
            if not upload_url or not authorization or not token or not cloud_object_meta:
                raise RuntimeError("上传授权信息不完整")
            if storage_bucket() not in upload_url and storage_bucket() not in file_id:
                raise RuntimeError("上传地址不在传统云存储桶")
            items.append(
                {
                    "objectId": path,
                    "uploadUrl": upload_url,
                    "authorization": authorization,
                    "token": token,
                    "cloudObjectMeta": cloud_object_meta,
                    "cloudObjectId": file_id,
                    "fileID": file_id,
                    "downloadUrl": str(data.get("download_url") or data.get("downloadUrl") or ""),
                }
            )
        return items

    def upload_bytes(self, object_id: str, content: bytes, content_type: str | None = None) -> str:
        del content_type  # COS signature from getUploadMetadata does not include Content-Type.
        info_list = self.get_upload_info([object_id])
        if not info_list:
            raise RuntimeError("未获取到上传授权信息")
        info = info_list[0]
        # Same PUT headers as node-sdk uploadFile when method is "put".
        headers = {
            "Signature": info["authorization"],
            "authorization": info["authorization"],
            "x-cos-security-token": info["token"],
            "x-cos-meta-fileid": info["cloudObjectMeta"],
            "key": quote(str(info["objectId"]), safe="/"),
        }
        request = Request(info["uploadUrl"], data=content, method="PUT", headers=headers)
        try:
            with urlopen(request, timeout=60):
                pass
        except (HTTPError, URLError) as exc:
            raise RuntimeError("上传云存储失败") from exc
        return str(info["cloudObjectId"])

    def _admin(self, action: str, fields: dict[str, Any]) -> dict[str, Any]:
        env_id = self.client.env_id
        region = storage_region()
        url = f"https://{env_id}.{region}.tcb-api.tencentcloudapi.com/admin?env={quote(env_id, safe='')}"
        body = {"action": action, "envName": env_id, **fields}
        request = Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.client.apikey}",
                "X-TCB-Region": region,
            },
        )
        try:
            with urlopen(request, timeout=self.client.timeout) as response:
                content = response.read()
        except HTTPError as exc:
            raise CloudBaseError(f"传统云存储请求失败: {action} ({exc.code})") from exc
        except URLError as exc:
            raise CloudBaseError(f"传统云存储请求失败: {action}") from exc
        try:
            data = json.loads(content.decode("utf-8")) if content else {}
        except ValueError as exc:
            raise CloudBaseError(f"传统云存储返回非 JSON: {action}") from exc
        if not isinstance(data, dict):
            raise CloudBaseError(f"传统云存储返回异常: {action}")
        if data.get("code"):
            raise CloudBaseError(f"传统云存储返回异常: {action}")
        return data


@lru_cache(maxsize=1)
def get_storage() -> CloudBaseStorage:
    return CloudBaseStorage()
