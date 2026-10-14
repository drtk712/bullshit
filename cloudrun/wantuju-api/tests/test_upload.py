"""Photo upload goes through the server storage client and returns a cloud file ID."""
from __future__ import annotations

import base64

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import uploads


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-bytes"
WECHAT = {"x-wx-source": "wx_client", "x-wx-openid": "uploader"}


class _Storage:
    def __init__(self):
        self.calls = []

    def upload_bytes(self, object_id, content, content_type=None):
        self.calls.append((object_id, content, content_type))
        return f"cloud://wantuju/{object_id}"


def _client(monkeypatch) -> tuple[TestClient, _Storage]:
    storage = _Storage()
    monkeypatch.setattr(uploads, "get_storage", lambda: storage)
    app = FastAPI()
    app.include_router(uploads.router)
    return TestClient(app), storage


def test_raw_bytes_are_stored_and_return_file_id(monkeypatch):
    client, storage = _client(monkeypatch)
    response = client.post("/miniapp/upload", content=JPEG, headers={**WECHAT, "content-type": "image/jpeg"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["fileID"] == f"cloud://wantuju/{storage.calls[0][0]}"
    assert storage.calls[0][0].startswith("uploads/")
    assert storage.calls[0][0].endswith(".jpg")
    assert storage.calls[0][1] == JPEG
    assert storage.calls[0][2] == "image/jpeg"


def test_multipart_and_base64_are_accepted(monkeypatch):
    client, storage = _client(monkeypatch)
    multipart = client.post(
        "/miniapp/upload",
        files={"file": ("photo.png", PNG, "image/png")},
        headers=WECHAT,
    )
    assert multipart.status_code == 200
    assert multipart.json()["data"]["fileID"].endswith(".png")

    encoded = client.post(
        "/miniapp/upload",
        json={"contentBase64": base64.b64encode(PNG).decode("ascii")},
        headers=WECHAT,
    )
    assert encoded.status_code == 200
    assert storage.calls[-1][1] == PNG
    assert storage.calls[-1][2] == "image/png"


def test_upload_requires_wechat_identity_and_rejects_non_images(monkeypatch):
    client, storage = _client(monkeypatch)
    denied = client.post("/miniapp/upload", content=JPEG, headers={"content-type": "image/jpeg", "x-wx-openid": "forged"})
    assert denied.status_code == 401
    assert storage.calls == []

    rejected = client.post(
        "/miniapp/upload",
        content=b"not-an-image",
        headers={**WECHAT, "content-type": "application/octet-stream"},
    )
    assert rejected.status_code == 400
    assert storage.calls == []
