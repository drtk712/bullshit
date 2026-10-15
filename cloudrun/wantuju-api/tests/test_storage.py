"""PG Storage HTTP API client. Classic COS admin actions are not used."""
from __future__ import annotations

import inspect
import json
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError

import pytest

from app.cloudbase.client import CloudBaseClient, CloudBaseError
from app.cloudbase.storage import (
    CloudBaseStorage,
    looks_like_classic_cos_bucket,
    parse_storage_ref,
    pg_file_id,
    storage_bucket,
)


ENV = "wantuju-prod-d2gf1sf2r508a56b1"
BUCKET = "wantuju"
LEGACY_BUCKET = "7761-wantuju-prod-d2gf1sf2r508a56b1-1427592986"
GATEWAY = f"https://{ENV}.api.tcloudbasegateway.com"
SIGNED = f"{GATEWAY}/v1/storages/object/sign/wantuju/uploads/a.jpg?token=signed"


class _Response:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False


@pytest.fixture(autouse=True)
def _logical_bucket(monkeypatch):
    monkeypatch.delenv("CLOUDBASE_PG_STORAGE_BUCKET", raising=False)
    monkeypatch.delenv("CLOUDBASE_STORAGE_BUCKET", raising=False)


def _storage() -> CloudBaseStorage:
    return CloudBaseStorage(CloudBaseClient(env_id=ENV, apikey="test-key"))


def test_module_does_not_call_classic_admin_storage():
    import app.cloudbase.storage as storage

    source = inspect.getsource(storage)
    assert "getUploadMetadata" not in source
    assert "batchGetDownloadUrl" not in source
    assert "batchDeleteFile" not in source
    assert "tcb-api.tencentcloudapi.com" not in source


def test_classic_cos_name_is_not_the_pg_bucket(monkeypatch):
    assert storage_bucket() == BUCKET
    assert looks_like_classic_cos_bucket(LEGACY_BUCKET)
    monkeypatch.setenv("CLOUDBASE_STORAGE_BUCKET", LEGACY_BUCKET)
    assert storage_bucket() == BUCKET
    monkeypatch.setenv("CLOUDBASE_PG_STORAGE_BUCKET", LEGACY_BUCKET)
    assert storage_bucket() == BUCKET
    monkeypatch.setenv("CLOUDBASE_PG_STORAGE_BUCKET", "covers")
    assert storage_bucket() == "covers"
    monkeypatch.delenv("CLOUDBASE_PG_STORAGE_BUCKET")
    monkeypatch.setenv("CLOUDBASE_STORAGE_BUCKET", "avatars")
    assert storage_bucket() == "avatars"


def test_parse_storage_ref_round_trips_pg_file_id():
    assert pg_file_id(BUCKET, "uploads/a.jpg") == "cloud://wantuju/uploads/a.jpg"
    assert parse_storage_ref("cloud://wantuju/uploads/a.jpg", default_bucket=BUCKET) == (BUCKET, "uploads/a.jpg")
    assert parse_storage_ref("wantuju/uploads/a.jpg", default_bucket=BUCKET) == (BUCKET, "uploads/a.jpg")
    classic = f"cloud://{ENV}.{LEGACY_BUCKET}/uploads/a.jpg"
    assert parse_storage_ref(classic, default_bucket=BUCKET) == (BUCKET, "uploads/a.jpg")
    assert parse_storage_ref("cloud://wantuju/../secret", default_bucket=BUCKET) is None


def test_upload_posts_bytes_to_pg_object_api(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout=30):
        calls.append((request, timeout))
        body = json.dumps({"Id": "obj-1", "Key": "wantuju/uploads/a.jpg"}).encode()
        return _Response(body)

    monkeypatch.setattr("app.cloudbase.storage.urlopen", fake_urlopen)
    file_id = _storage().upload_bytes("uploads/a.jpg", b"jpeg", "image/jpeg")
    assert file_id == "cloud://wantuju/uploads/a.jpg"
    request, timeout = calls[0]
    assert timeout == 60
    assert request.get_method() == "POST"
    assert request.full_url == f"{GATEWAY}/v1/storages/object/wantuju/uploads/a.jpg"
    assert request.data == b"jpeg"
    assert request.get_header("Content-type") == "image/jpeg"
    assert request.get_header("X-upsert") == "true"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert "tcb-api" not in request.full_url
    assert b"getUploadMetadata" not in request.data


def test_upload_infers_jpeg_when_content_type_is_omitted(monkeypatch):
    def fake_urlopen(request, timeout=30):
        assert request.get_header("Content-type") == "image/jpeg"
        return _Response(json.dumps({"Id": "obj-2", "Key": "wantuju/posters/job.jpg"}).encode())

    monkeypatch.setattr("app.cloudbase.storage.urlopen", fake_urlopen)
    assert _storage().upload_bytes("posters/job.jpg", b"jpeg") == "cloud://wantuju/posters/job.jpg"


def test_download_urls_come_from_sign_api(monkeypatch):
    file_id = "cloud://wantuju/uploads/a.jpg"

    def fake_urlopen(request, timeout=30):
        assert request.get_method() == "POST"
        assert request.full_url == f"{GATEWAY}/v1/storages/object/sign/wantuju"
        body = json.loads(request.data.decode())
        assert body == {"paths": ["uploads/a.jpg"], "expiresIn": 3600}
        assert request.get_header("Authorization") == "Bearer test-key"
        return _Response(
            json.dumps(
                [
                    {
                        "path": "uploads/a.jpg",
                        "signedURL": "/v1/storages/object/sign/wantuju/uploads/a.jpg?token=signed",
                        "fullSignedURL": SIGNED,
                        "error": None,
                    }
                ]
            ).encode()
        )

    monkeypatch.setattr("app.cloudbase.storage.urlopen", fake_urlopen)
    storage = _storage()
    assert storage.get_download_urls([file_id]) == [SIGNED]
    info = storage.get_download_info([file_id, "wantuju/uploads/a.jpg"])
    assert info[0]["tempFileURL"] == SIGNED
    assert info[0]["fileID"] == file_id


def test_classic_file_id_is_signed_in_the_pg_bucket(monkeypatch):
    file_id = f"cloud://{ENV}.{LEGACY_BUCKET}/uploads/a.jpg"

    def fake_urlopen(request, timeout=30):
        body = json.loads(request.data.decode())
        assert request.full_url.endswith("/v1/storages/object/sign/wantuju")
        assert body["paths"] == ["uploads/a.jpg"]
        return _Response(json.dumps([{"path": "uploads/a.jpg", "fullSignedURL": SIGNED}]).encode())

    monkeypatch.setattr("app.cloudbase.storage.urlopen", fake_urlopen)
    assert _storage().get_download_urls([file_id]) == [SIGNED]


def test_sign_error_does_not_return_a_url(monkeypatch):
    def fake_urlopen(request, timeout=30):
        return _Response(
            json.dumps([{"path": "uploads/a.jpg", "fullSignedURL": SIGNED, "error": "not found"}]).encode()
        )

    monkeypatch.setattr("app.cloudbase.storage.urlopen", fake_urlopen)
    assert _storage().get_download_urls(["cloud://wantuju/uploads/a.jpg"]) == []


def test_delete_objects_uses_batch_prefixes(monkeypatch):
    def fake_urlopen(request, timeout=30):
        assert request.get_method() == "DELETE"
        assert request.full_url == f"{GATEWAY}/v1/storages/object/wantuju"
        body = json.loads(request.data.decode())
        assert body == {"prefixes": ["uploads/a.jpg", "posters/b.jpg"]}
        assert b"batchDeleteFile" not in request.data
        return _Response(
            json.dumps(
                [
                    {"name": "uploads/a.jpg", "bucket_id": "wantuju"},
                    {"name": "posters/b.jpg", "bucket_id": "wantuju"},
                ]
            ).encode()
        )

    monkeypatch.setattr("app.cloudbase.storage.urlopen", fake_urlopen)
    deleted = _storage().delete_objects(
        [
            "cloud://wantuju/uploads/a.jpg",
            "wantuju/posters/b.jpg",
            "not-a-file",
        ]
    )
    assert [item["name"] for item in deleted] == ["uploads/a.jpg", "posters/b.jpg"]


def test_upload_info_uses_signed_upload_url(monkeypatch):
    def fake_urlopen(request, timeout=30):
        assert request.get_method() == "POST"
        assert request.full_url == f"{GATEWAY}/v1/storages/object/upload/sign/wantuju/uploads/a.jpg"
        assert request.get_header("X-upsert") == "true"
        assert request.data is None
        return _Response(
            json.dumps(
                {
                    "url": "/v1/storages/object/upload/sign/wantuju/uploads/a.jpg?token=up",
                    "fullURL": f"{GATEWAY}/v1/storages/object/upload/sign/wantuju/uploads/a.jpg?token=up",
                    "token": "up",
                }
            ).encode()
        )

    monkeypatch.setattr("app.cloudbase.storage.urlopen", fake_urlopen)
    info = _storage().get_upload_info(["/uploads/a.jpg"])[0]
    assert info["fileID"] == "cloud://wantuju/uploads/a.jpg"
    assert info["cloudObjectId"] == info["fileID"]
    assert info["uploadUrl"].startswith("https://")
    assert info["token"] == "up"


def test_storage_http_error_raises_cloudbase_error(monkeypatch):
    def fake_urlopen(request, timeout=30):
        raise HTTPError(
            request.full_url,
            403,
            "forbidden",
            Message(),
            BytesIO(b'{"code":"INVALID_ACCESS_TOKEN","message":"bad token"}'),
        )

    monkeypatch.setattr("app.cloudbase.storage.urlopen", fake_urlopen)
    with pytest.raises(CloudBaseError, match="INVALID_ACCESS_TOKEN"):
        _storage().upload_bytes("uploads/a.jpg", b"jpeg", "image/jpeg")
