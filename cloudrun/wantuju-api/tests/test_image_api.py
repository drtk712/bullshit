"""Image-to-image uses multipart edits. Generations is text-only."""
from __future__ import annotations

import base64
from io import BytesIO

import pytest
import requests
from PIL import Image

from app.services import poster


PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
PNG = base64.b64decode(PNG_B64)
SOURCE = "https://cdn.example/in.jpg"
BANNED = ("quality", "size", "style", "moderation", "mode", "fast")


class _Response:
    def __init__(self, status_code: int, payload=None, content: bytes = b"", headers=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.content = content
        self.headers = headers or {}
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


def _png(width: int, height: int, mode: str = "RGB") -> bytes:
    color = (20, 40, 60, 128) if mode == "RGBA" else (20, 40, 60)
    buffer = BytesIO()
    Image.new(mode, (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _b64_body(raw: bytes, tokens: int | None = 1024):
    payload = {"data": [{"b64_json": base64.b64encode(raw).decode("ascii")}]}
    if tokens is not None:
        payload["usage"] = {"input_tokens_details": {"image_tokens": tokens}}
    return _Response(200, payload)


def _install(monkeypatch, post, get=None):
    monkeypatch.setenv("IMAGE_API_KEY", "secret")
    monkeypatch.delenv("IMAGE_MODEL", raising=False)
    monkeypatch.delenv("IMAGE_API_BASE_URL", raising=False)
    monkeypatch.setattr(poster.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(poster.requests, "post", post)
    if get is None:
        def get(*_args, **_kwargs):
            raise AssertionError("unexpected download")
    monkeypatch.setattr(poster.requests, "get", get)


def test_timeout_covers_observed_latency():
    assert poster.GENERATION_TIMEOUT_SECONDS >= 120


def test_photo_always_uses_edits_and_stores_jpeg(monkeypatch):
    posts = []

    def post(url, **kwargs):
        posts.append((url, kwargs))
        return _b64_body(PNG, tokens=1024)

    def get(url, **kwargs):
        assert url == SOURCE
        return _Response(200, content=PNG)

    _install(monkeypatch, post, get)
    image = poster.generate_poster(SOURCE, "palm", "make a poster")

    assert image.extension == ".jpg"
    assert image.content.startswith(b"\xff\xd8\xff")
    assert len(posts) == 1
    assert posts[0][0] == "https://aigw.telecomjs.com/v1/images/edits"
    form = posts[0][1]["data"]
    uploaded = posts[0][1]["files"]["image"]
    assert form["model"] == "orb_base_02_vis"
    assert form["prompt"] == "make a poster"
    assert form["n"] == "1"
    assert form["response_format"] == "b64_json"
    assert "image" not in form
    assert uploaded[1] == PNG
    assert posts[0][1]["headers"] == {"Authorization": "Bearer secret"}
    assert posts[0][1]["timeout"] >= 120
    for name in BANNED:
        assert name not in form


def test_zero_image_tokens_rejects_ignored_input(monkeypatch):
    def post(url, **kwargs):
        assert url.endswith("/images/edits")
        return _b64_body(PNG, tokens=0)

    def get(url, **kwargs):
        return _Response(200, content=PNG)

    _install(monkeypatch, post, get)
    with pytest.raises(RuntimeError, match="未使用输入照片"):
        poster.generate_poster(SOURCE, "palm", "prompt")


def test_missing_usage_still_accepts_edits(monkeypatch):
    def post(url, **kwargs):
        return _b64_body(PNG, tokens=None)

    def get(url, **kwargs):
        return _Response(200, content=PNG)

    _install(monkeypatch, post, get)
    image = poster.generate_poster(SOURCE, "palm", "prompt")
    assert image.extension == ".jpg"


def test_large_png_is_scaled_before_storage(monkeypatch):
    wide = _png(3000, 20)

    def post(url, **kwargs):
        return _b64_body(wide, tokens=1024)

    def get(url, **kwargs):
        return _Response(200, content=PNG)

    _install(monkeypatch, post, get)
    image = poster.generate_poster(SOURCE, "palm", "prompt")
    with Image.open(BytesIO(image.content)) as stored:
        assert stored.format == "JPEG"
        assert max(stored.size) <= poster.STORED_MAX_EDGE


def test_no_photo_uses_generations_without_image_field(monkeypatch):
    bodies = []

    def post(url, **kwargs):
        bodies.append((url, kwargs["json"]))
        return _b64_body(_png(8, 8), tokens=None)

    _install(monkeypatch, post)
    image = poster.generate_poster("", "text", "a poster")
    assert image.extension == ".jpg"
    assert bodies[0][0].endswith("/images/generations")
    assert "image" not in bodies[0][1]
    assert bodies[0][1]["model"] == "orb_base_02_vis"


def test_response_format_rejection_retries_edits(monkeypatch):
    forms = []

    def post(url, **kwargs):
        forms.append(kwargs["data"])
        if "response_format" in kwargs["data"]:
            return _Response(400, {"error": {"message": "Unknown parameter: 'response_format'"}})
        return _b64_body(PNG, tokens=1024)

    def get(url, **kwargs):
        return _Response(200, content=PNG)

    _install(monkeypatch, post, get)
    poster.generate_poster(SOURCE, "palm", "prompt")
    assert "response_format" in forms[0]
    assert "response_format" not in forms[1]


def test_auth_and_server_errors_stay_on_edits(monkeypatch):
    def get(url, **kwargs):
        return _Response(200, content=PNG)

    def auth_post(url, **kwargs):
        return _Response(401, {"error": {"message": "invalid api key"}})

    _install(monkeypatch, auth_post, get)
    with pytest.raises(RuntimeError, match="401"):
        poster.generate_poster(SOURCE, "palm", "prompt")

    calls = []

    def server_post(url, **kwargs):
        calls.append(url)
        return _Response(500, {"error": {"message": "overloaded"}})

    _install(monkeypatch, server_post, get)
    with pytest.raises(RuntimeError, match="500"):
        poster.generate_poster(SOURCE, "palm", "prompt")
    assert calls == ["https://aigw.telecomjs.com/v1/images/edits"] * poster.GENERATION_MAX_ATTEMPTS


def test_missing_key_and_fast_model_are_rejected(monkeypatch):
    monkeypatch.delenv("IMAGE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="IMAGE_API_KEY"):
        poster.generate_poster(SOURCE, "palm", "prompt")

    monkeypatch.setenv("IMAGE_API_KEY", "secret")
    monkeypatch.setenv("IMAGE_MODEL", "orb_fast_vis")
    with pytest.raises(RuntimeError, match="fast"):
        poster.generate_poster(SOURCE, "palm", "prompt")
