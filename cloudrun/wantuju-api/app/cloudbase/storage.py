"""CloudBase PG-mode cloud storage (HTTP API).

This environment runs with PostgreSQL RuntimeMode. File bytes go through the
PG Storage HTTP API at ``https://{envId}.api.tcloudbasegateway.com`` with
``Authorization: Bearer <CLOUDBASE_APIKEY>``. PostgreSQL stays the database
for users, points, tasks, and features. Object bytes are not inserted into
SQL tables or dumped through pgstore.

The bucket id is the logical name (default ``wantuju``), not a legacy COS
bucket string such as ``7761-wantuju-prod-...``. ``CLOUDBASE_PG_STORAGE_BUCKET``
wins. ``CLOUDBASE_STORAGE_BUCKET`` is used only when it does not look like a
classic COS name.

Stable ids are ``cloud://{bucket}/{objectName}`` (for this env,
``cloud://wantuju/{objectName}``) so ``get_download_urls`` can round-trip
them. Download links are the HTTPS ``fullSignedURL`` values from
``POST /v1/storages/object/sign/{bucket}``.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.cloudbase.client import CloudBaseClient, CloudBaseError


DEFAULT_PG_STORAGE_BUCKET = "wantuju"
LEGACY_COS_BUCKET = "7761-wantuju-prod-d2gf1sf2r508a56b1-1427592986"
TEMP_URL_MAX_AGE = 3600
SIGN_BATCH_LIMIT = 500
DELETE_BATCH_LIMIT = 100
_CLASSIC_COS_BUCKET = re.compile(r"^\d+-.+-\d{6,}$")
_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def storage_bucket() -> str:
    """Logical PG bucket id. A classic COS bucket string is not a bucket id."""
    for name in ("CLOUDBASE_PG_STORAGE_BUCKET", "CLOUDBASE_STORAGE_BUCKET"):
        value = os.getenv(name, "").strip()
        if value and not looks_like_classic_cos_bucket(value):
            return value
    return DEFAULT_PG_STORAGE_BUCKET


def looks_like_classic_cos_bucket(name: str) -> bool:
    text = str(name or "").strip()
    if not text or text == DEFAULT_PG_STORAGE_BUCKET:
        return False
    if text == LEGACY_COS_BUCKET or _CLASSIC_COS_BUCKET.fullmatch(text):
        return True
    return "." in text


def pg_file_id(bucket: str, object_name: str) -> str:
    return f"cloud://{bucket}/{object_name.lstrip('/')}"


def parse_storage_ref(file_id: str, *, default_bucket: str) -> tuple[str, str] | None:
    """Return ``(bucket, object_name)`` for a stored reference.

    Accepted forms:

    - ``cloud://wantuju/uploads/a.jpg`` (PG file id)
    - ``wantuju/uploads/a.jpg`` when the first segment is the configured bucket
    - ``cloud://{envId}.{legacyCosBucket}/uploads/a.jpg`` — the object path is
      kept and signed in the PG bucket. The legacy COS name is not a bucket id.
    """
    text = str(file_id or "").strip()
    if not text or "\\" in text:
        return None
    if text.startswith("cloud://"):
        rest = text[len("cloud://") :]
        slash = rest.find("/")
        if slash <= 0:
            return None
        head, object_name = rest[:slash], rest[slash + 1 :]
        if not _valid_object_name(object_name):
            return None
        if "." in head:
            bucket = default_bucket
        else:
            bucket = head
        if not bucket or looks_like_classic_cos_bucket(bucket):
            return None
        return bucket, object_name
    prefix = f"{default_bucket}/"
    if text.startswith(prefix) and _valid_object_name(text[len(prefix) :]):
        return default_bucket, text[len(prefix) :]
    return None


def _valid_object_name(object_name: str) -> bool:
    if not object_name or object_name.startswith("/"):
        return False
    parts = object_name.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def _clean_object_name(object_id: str) -> str:
    name = str(object_id or "").strip().lstrip("/")
    if not _valid_object_name(name):
        raise RuntimeError("对象路径无效")
    return name


def _content_type_for(object_name: str, content_type: str | None) -> str:
    raw = str(content_type or "").split(";", 1)[0].strip().lower()
    if raw and "/" in raw and "\r" not in raw and "\n" not in raw and " " not in raw:
        return raw
    suffix = ""
    leaf = object_name.rsplit("/", 1)[-1]
    if "." in leaf:
        suffix = "." + leaf.rsplit(".", 1)[-1].lower()
    return _MIME_BY_EXT.get(suffix, "application/octet-stream")


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _sign_rows(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if any(key in payload for key in ("fullSignedURL", "fullSignedUrl", "signedURL", "signedUrl", "path")):
            return [payload]
    return []


def _signed_https(item: dict[str, Any], base_url: str) -> str:
    full = str(item.get("fullSignedURL") or item.get("fullSignedUrl") or "")
    if full.startswith("https://"):
        return full
    signed = str(item.get("signedURL") or item.get("signedUrl") or "")
    if signed.startswith("https://"):
        return signed
    if signed.startswith("/") and base_url.startswith("https://"):
        return f"{base_url.rstrip('/')}{signed}"
    return ""


def _returned_object_name(path: str, bucket: str) -> str:
    text = str(path or "").strip().lstrip("/")
    prefix = f"{bucket}/"
    if text.startswith(prefix):
        text = text[len(prefix) :]
    return text


class CloudBaseStorage:
    def __init__(self, client: CloudBaseClient | None = None):
        self.client = client or CloudBaseClient()

    def get_download_info(self, cloud_object_ids: list[str]) -> list[dict[str, Any]]:
        default_bucket = storage_bucket()
        refs: list[tuple[str, str, str]] = []
        for raw in cloud_object_ids:
            if not isinstance(raw, str):
                continue
            parsed = parse_storage_ref(raw, default_bucket=default_bucket)
            if parsed:
                refs.append((raw, parsed[0], parsed[1]))
        if not refs:
            return []

        signed: dict[tuple[str, str], str] = {}
        errors: dict[tuple[str, str], str] = {}
        grouped: dict[str, list[str]] = {}
        for _, bucket, object_name in refs:
            names = grouped.setdefault(bucket, [])
            if object_name not in names:
                names.append(object_name)
        for bucket, names in grouped.items():
            for chunk in _chunks(names, SIGN_BATCH_LIMIT):
                payload = self._json(
                    "POST",
                    f"/v1/storages/object/sign/{quote(bucket, safe='')}",
                    {"paths": chunk, "expiresIn": TEMP_URL_MAX_AGE},
                )
                rows = _sign_rows(payload)
                seen_path = False
                for item in rows:
                    if not isinstance(item, dict):
                        continue
                    object_name = _returned_object_name(str(item.get("path") or ""), bucket)
                    if not object_name:
                        continue
                    seen_path = True
                    error = str(item.get("error") or "").strip()
                    url = _signed_https(item, self.client.base_url)
                    if error or not url:
                        errors[(bucket, object_name)] = error or "SIGN_FAILED"
                        continue
                    signed[(bucket, object_name)] = url
                if seen_path:
                    continue
                for object_name, item in zip(chunk, rows):
                    if not isinstance(item, dict):
                        continue
                    error = str(item.get("error") or "").strip()
                    url = _signed_https(item, self.client.base_url)
                    if error or not url:
                        errors[(bucket, object_name)] = error or "SIGN_FAILED"
                        continue
                    signed[(bucket, object_name)] = url

        items: list[dict[str, Any]] = []
        for raw, bucket, object_name in refs:
            url = signed.get((bucket, object_name), "")
            items.append(
                {
                    "fileID": raw,
                    "cloudObjectId": raw,
                    "downloadUrl": url,
                    "tempFileURL": url,
                    "code": errors.get((bucket, object_name), ""),
                }
            )
        return items

    def get_download_urls(self, cloud_object_ids: list[str]) -> list[str]:
        info_list = self.get_download_info(cloud_object_ids)
        url_map = {
            str(item.get("fileID") or ""): str(item.get("downloadUrl") or "")
            for item in info_list
            if str(item.get("downloadUrl") or "").startswith("https://")
        }
        if not url_map:
            return []
        return [url_map.get(file_id, "") if isinstance(file_id, str) else "" for file_id in cloud_object_ids]

    def get_download_url(self, cloud_object_id: str) -> str:
        urls = self.get_download_urls([cloud_object_id])
        return urls[0] if urls else ""

    def delete_objects(self, cloud_object_ids: list[str]) -> list[dict[str, Any]]:
        default_bucket = storage_bucket()
        grouped: dict[str, list[str]] = {}
        for raw in cloud_object_ids:
            if not isinstance(raw, str):
                continue
            parsed = parse_storage_ref(raw, default_bucket=default_bucket)
            if not parsed:
                continue
            bucket, object_name = parsed
            names = grouped.setdefault(bucket, [])
            if object_name not in names:
                names.append(object_name)
        deleted: list[dict[str, Any]] = []
        for bucket, names in grouped.items():
            for chunk in _chunks(names, DELETE_BATCH_LIMIT):
                payload = self._json(
                    "DELETE",
                    f"/v1/storages/object/{quote(bucket, safe='')}",
                    {"prefixes": chunk},
                )
                if isinstance(payload, list):
                    deleted.extend(item for item in payload if isinstance(item, dict))
                elif isinstance(payload, dict):
                    deleted.append(payload)
        return deleted

    def get_upload_info(self, object_ids: list[str]) -> list[dict[str, Any]]:
        """Signed upload URLs for the admin tool. Server uploads use ``upload_bytes``."""
        bucket = storage_bucket()
        items: list[dict[str, Any]] = []
        for object_id in object_ids:
            try:
                object_name = _clean_object_name(object_id)
            except RuntimeError as exc:
                raise CloudBaseError(str(exc)) from exc
            payload = self._call(
                "POST",
                f"/v1/storages/object/upload/sign/{quote(bucket, safe='')}/{quote(object_name, safe='/')}",
                headers={"x-upsert": "true"},
            )
            if not isinstance(payload, dict):
                raise CloudBaseError("未获取到上传授权信息")
            upload_url = str(payload.get("fullURL") or payload.get("fullUrl") or payload.get("url") or "")
            if not upload_url.startswith("https://"):
                raise CloudBaseError("未获取到上传授权信息")
            file_id = pg_file_id(bucket, object_name)
            items.append(
                {
                    "objectId": object_name,
                    "uploadUrl": upload_url,
                    "token": str(payload.get("token") or ""),
                    "cloudObjectId": file_id,
                    "fileID": file_id,
                    "downloadUrl": "",
                }
            )
        return items

    def upload_bytes(self, object_id: str, content: bytes, content_type: str | None = None) -> str:
        object_name = _clean_object_name(object_id)
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise RuntimeError("上传内容为空")
        bucket = storage_bucket()
        mime = _content_type_for(object_name, content_type)
        payload = self._call(
            "POST",
            f"/v1/storages/object/{quote(bucket, safe='')}/{quote(object_name, safe='/')}",
            body=bytes(content),
            content_type=mime,
            headers={"x-upsert": "true"},
            timeout=60,
        )
        if not isinstance(payload, dict):
            raise CloudBaseError("云存储上传返回异常")
        key = str(payload.get("Key") or payload.get("key") or "").lstrip("/")
        prefix = f"{bucket}/"
        if key.startswith(prefix):
            returned = key[len(prefix) :]
            if _valid_object_name(returned):
                object_name = returned
        return pg_file_id(bucket, object_name)

    def _json(self, method: str, path: str, payload: dict[str, Any], **headers: str) -> Any:
        return self._call(
            method,
            path,
            body=json.dumps(payload).encode("utf-8"),
            content_type="application/json",
            headers=headers or None,
        )

    def _call(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> Any:
        if not path.startswith("/"):
            path = f"/{path}"
        req_headers = {
            "Authorization": f"Bearer {self.client.apikey}",
            "Accept": "application/json",
        }
        if content_type:
            req_headers["Content-Type"] = content_type
        if headers:
            req_headers.update(headers)
        request = Request(f"{self.client.base_url}{path}", data=body, method=method, headers=req_headers)
        try:
            with urlopen(request, timeout=timeout or self.client.timeout) as response:
                content = response.read()
        except HTTPError as exc:
            detail = _error_detail(exc)
            message = f"云存储请求失败: {method} {path} ({exc.code})"
            if detail:
                message = f"{message} - {detail}"
            raise CloudBaseError(message) from exc
        except URLError as exc:
            raise CloudBaseError(f"云存储请求失败: {method} {path}") from exc
        if not content:
            return None
        try:
            data = json.loads(content.decode("utf-8"))
        except ValueError as exc:
            raise CloudBaseError(f"云存储返回非 JSON: {method} {path}") from exc
        if isinstance(data, dict):
            code = data.get("code")
            if code not in (None, "", 0, "0") and (data.get("message") or data.get("error")):
                raise CloudBaseError(f"云存储返回异常: {method} {path} ({code})")
        elif not isinstance(data, list):
            raise CloudBaseError(f"云存储返回异常: {method} {path}")
        return data


def _error_detail(exc: HTTPError) -> str:
    try:
        raw = exc.read()
    except Exception:
        return ""
    if not raw:
        return ""
    text = raw.decode("utf-8", errors="replace")[:500]
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    if isinstance(parsed, dict):
        code = str(parsed.get("code") or parsed.get("error") or "")
        message = str(parsed.get("message") or "")
        return " ".join(part for part in (code, message) if part)[:500]
    return text


@lru_cache(maxsize=1)
def get_storage() -> CloudBaseStorage:
    return CloudBaseStorage()
