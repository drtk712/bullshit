"""OpenAI-compatible image generation: generations first, edits as fallback."""
from __future__ import annotations

import base64

import pytest
import requests

from app.core.config import image_api_base_url
from app.services import poster


PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
PNG = base64.b64decode(PNG_B64)
SOURCE = "https://cdn.example/in.jpg"
BANNED = ("quality", "size", "style", "moderation", "mode")


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


def _b64_body():
    return _Response(200, {"data": [{"b64_json": PNG_B64}]})


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


def test_generations_sends_photo_url_and_decodes_b64(monkeypatch):
    posts = []

    def post(url, **kwargs):
        posts.append((url, kwargs))
        return _b64_body()

    _install(monkeypatch, post)
    image = poster.generate_poster(SOURCE, "palm", "make a poster")

    assert image.content == PNG
    assert image.extension == ".png"
    assert posts[0][0] == "https://aigw.telecomjs.com/v1/images/generations"
    body = posts[0][1]["json"]
    assert body == {
        "model": "orb_base_02_vis",
        "prompt": "make a poster",
        "image": SOURCE,
        "n": 1,
        "response_format": "b64_json",
    }
    assert posts[0][1]["headers"]["Authorization"] == "Bearer secret"
    for name in BANNED:
        assert name not in body


def test_generations_downloads_http_url(monkeypatch):
    jpeg = b"\xff\xd8\xff\xe0rest"

    def post(url, **kwargs):
        return _Response(200, {"data": [{"url": "https://cdn.example/out.jpg"}]})

    def get(url, **kwargs):
        assert url == "https://cdn.example/out.jpg"
        return _Response(200, content=jpeg)

    _install(monkeypatch, post, get)
    image = poster.generate_poster(SOURCE, "hair", "prompt")
    assert image.content == jpeg
    assert image.extension == ".jpg"


def test_generations_accepts_data_url_and_raw_image_body(monkeypatch):
    def post_data(url, **kwargs):
        return _Response(200, {"data": [{"url": f"data:image/png;base64,{PNG_B64}"}]})

    _install(monkeypatch, post_data)
    assert poster.generate_poster(SOURCE, "palm", "prompt").content == PNG

    def post_raw(url, **kwargs):
        return _Response(200, content=PNG, headers={"Content-Type": "image/png"})

    _install(monkeypatch, post_raw)
    assert poster.generate_poster(SOURCE, "palm", "prompt").extension == ".png"


def test_unknown_image_parameter_falls_back_to_edits(monkeypatch):
    posts = []

    def post(url, **kwargs):
        posts.append((url, kwargs))
        if url.endswith("/images/generations"):
            return _Response(400, {"error": {"message": "Unknown parameter: 'image'"}})
        return _b64_body()

    def get(url, **kwargs):
        assert url == SOURCE
        return _Response(200, content=PNG)

    _install(monkeypatch, post, get)
    image = poster.generate_poster(SOURCE, "palm", "prompt")

    assert image.content == PNG
    assert [item[0] for item in posts] == [
        "https://aigw.telecomjs.com/v1/images/generations",
        "https://aigw.telecomjs.com/v1/images/edits",
    ]
    form = posts[1][1]["data"]
    uploaded = posts[1][1]["files"]["image"]
    assert form["model"] == "orb_base_02_vis"
    assert form["prompt"] == "prompt"
    assert form["n"] == "1"
    assert form["response_format"] == "b64_json"
    assert uploaded[0] == "input.png"
    assert uploaded[1] == PNG
    assert uploaded[2] == "image/png"
    assert posts[1][1]["headers"] == {"Authorization": "Bearer secret"}
    for name in BANNED:
        assert name not in form


def test_fetch_failure_retries_generations_with_data_url(monkeypatch):
    seen = []

    def post(url, **kwargs):
        image = kwargs["json"]["image"]
        seen.append(image)
        if image.startswith("https://"):
            return _Response(400, {"error": {"message": "failed to fetch image"}})
        return _b64_body()

    def get(url, **kwargs):
        return _Response(200, content=PNG)

    _install(monkeypatch, post, get)
    poster.generate_poster(SOURCE, "palm", "prompt")
    assert seen[0] == SOURCE
    assert seen[1].startswith("data:image/png;base64,")
    assert len(seen) == 2


def test_response_format_rejection_retries_without_it(monkeypatch):
    bodies = []

    def post(url, **kwargs):
        bodies.append(kwargs["json"])
        if "response_format" in kwargs["json"]:
            return _Response(400, {"error": {"message": "Unknown parameter: 'response_format'"}})
        return _b64_body()

    _install(monkeypatch, post)
    poster.generate_poster(SOURCE, "palm", "prompt")
    assert "response_format" in bodies[0]
    assert "response_format" not in bodies[1]
    assert len(bodies) == 2


def test_image_array_is_retried_once(monkeypatch):
    images = []

    def post(url, **kwargs):
        images.append(kwargs["json"]["image"])
        if isinstance(images[-1], str):
            return _Response(400, {"error": {"message": "image must be an array"}})
        return _b64_body()

    _install(monkeypatch, post)
    poster.generate_poster(SOURCE, "palm", "prompt")
    assert images == [SOURCE, [SOURCE]]


def test_auth_and_server_errors_do_not_call_edits(monkeypatch):
    def auth_post(url, **kwargs):
        return _Response(401, {"error": {"message": "invalid api key"}})

    _install(monkeypatch, auth_post)
    with pytest.raises(RuntimeError, match="401"):
        poster.generate_poster(SOURCE, "palm", "prompt")

    calls = []

    def server_post(url, **kwargs):
        calls.append(url)
        return _Response(500, {"error": {"message": "overloaded"}})

    _install(monkeypatch, server_post)
    with pytest.raises(RuntimeError, match="500"):
        poster.generate_poster(SOURCE, "palm", "prompt")
    assert calls == ["https://aigw.telecomjs.com/v1/images/generations"] * 3


def test_missing_key_and_fast_model_are_rejected(monkeypatch):
    monkeypatch.delenv("IMAGE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="IMAGE_API_KEY"):
        poster.generate_poster(SOURCE, "palm", "prompt")

    monkeypatch.setenv("IMAGE_API_KEY", "secret")
    monkeypatch.setenv("IMAGE_MODEL", "orb_fast_vis")
    with pytest.raises(RuntimeError, match="fast"):
        poster.generate_poster(SOURCE, "palm", "prompt")


def test_base_url_strips_images_path(monkeypatch):
    monkeypatch.setenv("IMAGE_API_BASE_URL", "https://gateway.example/v1/images/generations/")
    assert image_api_base_url() == "https://gateway.example/v1"

    def post(url, **kwargs):
        assert url == "https://gateway.example/v1/images/generations"
        return _b64_body()

    monkeypatch.setattr(poster.requests, "post", post)
    monkeypatch.setenv("IMAGE_API_KEY", "secret")
    monkeypatch.delenv("IMAGE_MODEL", raising=False)
    poster.generate_poster(SOURCE, "palm", "prompt")
