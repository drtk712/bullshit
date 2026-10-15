"""Traditional COS upload metadata, not the PG storage bucket."""
from __future__ import annotations

import json

import pytest

from app.cloudbase.client import CloudBaseClient
from app.cloudbase.storage import CloudBaseStorage, classic_file_id


ENV = "wantuju-prod-d2gf1sf2r508a56b1"
BUCKET = "7761-wantuju-prod-d2gf1sf2r508a56b1-1427592986"


class _Response:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False


def _storage() -> CloudBaseStorage:
    return CloudBaseStorage(CloudBaseClient(env_id=ENV, apikey="test-key"))


def test_classic_file_id_rejects_pg_bucket():
    assert classic_file_id(f"cloud://{ENV}.{BUCKET}/uploads/a.jpg", env_id=ENV, bucket=BUCKET).endswith("/uploads/a.jpg")
    with pytest.raises(RuntimeError):
        classic_file_id("cloud://wantuju/uploads/a.jpg", env_id=ENV, bucket=BUCKET)


def test_upload_calls_legacy_metadata_then_puts_to_cos(monkeypatch):
    calls: list = []

    def fake_urlopen(request, timeout=30):
        calls.append(request)
        if "tcb-api.tencentcloudapi.com/admin" in request.full_url:
            body = json.dumps(
                {
                    "data": {
                        "url": f"https://{BUCKET}.cos.ap-shanghai.myqcloud.com/uploads/a.jpg",
                        "token": "temp-token",
                        "authorization": "q-sign-algorithm=sha1",
                        "fileId": f"cloud://{ENV}.{BUCKET}/uploads/a.jpg",
                        "cosFileId": "meta-id",
                        "download_url": f"https://{BUCKET}.tcb.qcloud.la/uploads/a.jpg?sign=1",
                    }
                }
            ).encode()
            return _Response(body)
        return _Response(b"")

    monkeypatch.setattr("app.cloudbase.storage.urlopen", fake_urlopen)
    file_id = _storage().upload_bytes("uploads/a.jpg", b"jpeg", "image/jpeg")
    assert file_id == f"cloud://{ENV}.{BUCKET}/uploads/a.jpg"
    assert len(calls) == 2
    meta = json.loads(calls[0].data.decode())
    assert meta["action"] == "storage.getUploadMetadata"
    assert meta["path"] == "uploads/a.jpg"
    assert meta["method"] == "put"
    assert meta["envName"] == ENV
    assert calls[0].get_header("Authorization") == "Bearer test-key"
    assert "/v1/storages" not in calls[0].full_url
    assert calls[1].get_method() == "PUT"
    assert calls[1].get_header("X-cos-meta-fileid") == "meta-id"
    assert BUCKET in calls[1].full_url


def test_pg_file_id_is_not_uploaded(monkeypatch):
    calls: list = []

    def fake_urlopen(request, timeout=30):
        calls.append(request)
        body = json.dumps(
            {
                "data": {
                    "url": "https://example.invalid/uploads/a.jpg",
                    "token": "temp-token",
                    "authorization": "q-sign",
                    "fileId": "cloud://wantuju/uploads/a.jpg",
                    "cosFileId": "meta-id",
                }
            }
        ).encode()
        return _Response(body)

    monkeypatch.setattr("app.cloudbase.storage.urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="传统云存储"):
        _storage().upload_bytes("uploads/a.jpg", b"jpeg")
    assert len(calls) == 1


def test_download_urls_come_from_batch_get_download_url(monkeypatch):
    def fake_urlopen(request, timeout=30):
        body = json.loads(request.data.decode())
        assert body["action"] == "storage.batchGetDownloadUrl"
        assert body["file_list"][0]["fileid"].startswith("cloud://")
        return _Response(
            json.dumps(
                {
                    "data": {
                        "download_list": [
                            {
                                "fileID": body["file_list"][0]["fileid"],
                                "download_url": f"https://{BUCKET}.tcb.qcloud.la/uploads/a.jpg?sign=1",
                            }
                        ]
                    }
                }
            ).encode()
        )

    monkeypatch.setattr("app.cloudbase.storage.urlopen", fake_urlopen)
    file_id = f"cloud://{ENV}.{BUCKET}/uploads/a.jpg"
    assert _storage().get_download_urls([file_id]) == [f"https://{BUCKET}.tcb.qcloud.la/uploads/a.jpg?sign=1"]
