"""CloudBase cloud storage HTTP API helpers."""
from __future__ import annotations

from functools import lru_cache
from typing import Any
import mimetypes

import requests
from app.cloudbase.client import CloudBaseClient


class CloudBaseStorage:
    def __init__(self, client: CloudBaseClient | None = None):
        self.client = client or CloudBaseClient()

    def get_download_info(self, cloud_object_ids: list[str]) -> list[dict[str, Any]]:
        objects = [
            {"cloudObjectId": item}
            for item in cloud_object_ids
            if isinstance(item, str) and item.startswith("cloud://")
        ]
        if not objects:
            return []
        response = self.client.request("POST", "/v1/storages/get-objects-download-info", json=objects)
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            for key in ("data", "fileList", "list"):
                value = response.get(key)
                if isinstance(value, list):
                    return value
        return []

    def get_download_url(self, cloud_object_id: str) -> str:
        for item in self.get_download_info([cloud_object_id]):
            for key in ("url", "downloadUrl", "tempFileURL", "tempFileUrl"):
                value = item.get(key)
                if value:
                    return str(value)
        return ""

    def delete_objects(self, cloud_object_ids: list[str]) -> list[dict[str, Any]]:
        objects = [
            {"cloudObjectId": item}
            for item in cloud_object_ids
            if isinstance(item, str) and item.startswith("cloud://")
        ]
        if not objects:
            return []
        response = self.client.request("POST", "/v1/storages/delete-objects", json=objects)
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            for key in ("data", "fileList", "list"):
                value = response.get(key)
                if isinstance(value, list):
                    return value
        return []

    def get_upload_info(self, object_ids: list[str]) -> list[dict[str, Any]]:
        objects = [{"objectId": item} for item in object_ids if item]
        if not objects:
            return []
        response = self.client.request("POST", "/v1/storages/get-objects-upload-info", json=objects)
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            for key in ("data", "fileList", "list"):
                value = response.get(key)
                if isinstance(value, list):
                    return value
        return []

    def upload_bytes(self, object_id: str, content: bytes, content_type: str | None = None) -> str:
        info_list = self.get_upload_info([object_id])
        if not info_list:
            raise RuntimeError("未获取到上传授权信息")
        info = info_list[0]
        upload_url = str(info.get("uploadUrl") or "")
        authorization = str(info.get("authorization") or "")
        token = str(info.get("token") or "")
        cloud_object_meta = str(info.get("cloudObjectMeta") or "")
        cloud_object_id = str(info.get("cloudObjectId") or "")
        if not upload_url or not authorization or not cloud_object_meta or not cloud_object_id:
            raise RuntimeError("上传授权信息不完整")

        guessed_type = content_type or mimetypes.guess_type(object_id)[0] or "application/octet-stream"
        headers = {
            "Authorization": authorization,
            "x-cos-meta-fileid": cloud_object_meta,
            "Content-Type": guessed_type,
        }
        if token:
            headers["x-cos-security-token"] = token

        response = requests.put(upload_url, data=content, headers=headers, timeout=60)
        response.raise_for_status()
        return cloud_object_id


@lru_cache(maxsize=1)
def get_storage() -> CloudBaseStorage:
    return CloudBaseStorage()
