"""CloudBase cloud storage HTTP helpers."""
from __future__ import annotations

import mimetypes
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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

    def get_download_urls(self, cloud_object_ids: list[str]) -> list[str]:
        info_list = self.get_download_info(cloud_object_ids)
        url_map: dict[str, str] = {}
        ordered_urls: list[str] = []
        for item in info_list:
            file_id = str(item.get("fileID") or item.get("cloudObjectId") or item.get("cloudObjectID") or "")
            url = str(
                item.get("url")
                or item.get("downloadUrl")
                or item.get("download_url")
                or item.get("tempFileURL")
                or item.get("tempFileUrl")
                or ""
            )
            if url:
                ordered_urls.append(url)
            if file_id and url:
                url_map[file_id] = url

        if url_map:
            return [url_map.get(file_id, "") for file_id in cloud_object_ids]
        return ordered_urls[:len(cloud_object_ids)]

    def get_download_url(self, cloud_object_id: str) -> str:
        urls = self.get_download_urls([cloud_object_id])
        return urls[0] if urls else ""

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

        request = Request(upload_url, data=content, method="PUT", headers=headers)
        try:
            with urlopen(request, timeout=60):
                pass
        except (HTTPError, URLError) as exc:
            raise RuntimeError("上传云存储失败") from exc
        return cloud_object_id


@lru_cache(maxsize=1)
def get_storage() -> CloudBaseStorage:
    return CloudBaseStorage()
