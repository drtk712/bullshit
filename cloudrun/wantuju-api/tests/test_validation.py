"""Validation stays off when config is null, and can send a bearer token later."""
from __future__ import annotations

import json

from app.services.tasks import TaskService, validation_request_headers


class _Storage:
    def get_download_urls(self, file_ids):
        return ["https://example.test/image.jpg" for _ in file_ids]


def test_null_and_missing_validation_skip_the_remote_call():
    service = TaskService(db=object(), storage=_Storage())
    assert service.validate_image("cloud://a", {"validation": None}) == {"passed": True, "reason": ""}
    assert service.validate_image_once("cloud://a", {}) == {"passed": True, "reason": ""}


def test_api_key_header_is_optional(monkeypatch):
    monkeypatch.delenv("VALIDATION_API_KEY", raising=False)
    assert validation_request_headers({"serviceUrl": "http://example.test"}) == {
        "Content-Type": "application/json",
    }
    assert validation_request_headers({"apiKey": "secret"})["Authorization"] == "Bearer secret"
    monkeypatch.setenv("VALIDATION_API_KEY", "from-env")
    assert validation_request_headers({})["Authorization"] == "Bearer from-env"


def test_configured_validation_sends_bearer_token(monkeypatch):
    captured = {}

    class _Response:
        status = 200

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "是"}}]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        captured["body"] = json.loads(request.data.decode())
        return _Response()

    monkeypatch.setattr("app.services.tasks.urlopen", fake_urlopen)
    service = TaskService(db=object(), storage=_Storage())
    result = service.validate_image(
        "cloud://a",
        {
            "validation": {
                "serviceUrl": "http://vision.example/v1/chat/completions",
                "model": "gpt-4o",
                "prompt": "是手掌吗",
                "apiKey": "future-key",
            }
        },
    )

    assert result["passed"] is True
    assert captured["url"] == "http://vision.example/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer future-key"
    assert captured["body"]["model"] == "gpt-4o"
