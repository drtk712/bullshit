"""OpenAI-compatible image generation.

The user's photo is sent as an input image. Official Images API generations
are text-to-image, while edits take a multipart ``image`` file. Several
gateways also accept ``image`` on ``/images/generations`` as an HTTPS URL or
a base64 data URL. This client tries that first and falls back to
``/images/edits`` when the generations endpoint rejects an input image.

Responses may be ``data[0].b64_json`` or ``data[0].url``. No fast model,
quality, or mode parameter is sent.
"""
from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from app.core.config import image_api_base_url, image_api_key, image_model


logger = logging.getLogger(__name__)
GENERATION_TIMEOUT_SECONDS = 300
GENERATION_MAX_ATTEMPTS = 3
RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class GeneratedImage:
    content: bytes
    extension: str


@dataclass
class _Outcome:
    image: GeneratedImage | None = None
    error: Exception | None = None
    stop: bool = False
    drop_format: bool = False
    retry_base64: bool = False
    use_edits: bool = False


def mask_url(url: str) -> str:
    if not url:
        return ""
    try:
        parts = url.split("/")
        domain = parts[2] if len(parts) > 2 else "unknown"
        return f"{domain}/..."
    except Exception:
        return f"{url[:20]}..."


def generate_poster(image_url: str, job_type: str, generation_prompt: str) -> GeneratedImage:
    """Generate one image from the user's photo and the feature prompt."""
    key = image_api_key()
    if not key:
        raise RuntimeError("IMAGE_API_KEY 未设置")
    model = _checked_model()
    logger.info("[图片处理] type=%s model=%s image=%s", job_type, model, mask_url(image_url))

    use_format = True
    outcome = _generations(key, model, generation_prompt, image_url, response_format=True)
    if outcome.image:
        return outcome.image
    if outcome.stop:
        raise outcome.error or RuntimeError("图片生成失败")
    if outcome.drop_format:
        use_format = False
        outcome = _generations(key, model, generation_prompt, image_url, response_format=False)
        if outcome.image:
            return outcome.image
        if outcome.stop:
            raise outcome.error or RuntimeError("图片生成失败")

    source: bytes | None = None
    if outcome.retry_base64:
        source = download_image_bytes(image_url)
        outcome = _generations(
            key,
            model,
            generation_prompt,
            _data_url(source, image_url),
            response_format=use_format,
        )
        if outcome.image:
            return outcome.image
        if outcome.stop:
            raise outcome.error or RuntimeError("图片生成失败")
        if outcome.drop_format and use_format:
            use_format = False
            outcome = _generations(
                key,
                model,
                generation_prompt,
                _data_url(source, image_url),
                response_format=False,
            )
            if outcome.image:
                return outcome.image
            if outcome.stop:
                raise outcome.error or RuntimeError("图片生成失败")

    if source is None:
        source = download_image_bytes(image_url)
    logger.info("[图片处理] generations 不能接收输入图，改走 images/edits")
    edited = _edits(key, model, generation_prompt, source, image_url, response_format=use_format)
    if edited.image:
        return edited.image
    if edited.drop_format and use_format:
        edited = _edits(key, model, generation_prompt, source, image_url, response_format=False)
        if edited.image:
            return edited.image
    raise edited.error or outcome.error or RuntimeError("图片生成失败")


def download_image_bytes(url: str) -> bytes:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.content


def guess_ext_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".png"


def _checked_model() -> str:
    model = image_model()
    if "fast" in model.lower():
        raise RuntimeError("IMAGE_MODEL 不能使用 fast 变体")
    return model


def _endpoint(path: str) -> str:
    return f"{image_api_base_url()}/{path.lstrip('/')}"


def _auth_headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def _payload(model: str, prompt: str, image: str | list[str], *, response_format: bool) -> dict[str, object]:
    body: dict[str, object] = {
        "model": model,
        "prompt": prompt,
        "image": image,
        "n": 1,
    }
    if response_format:
        body["response_format"] = "b64_json"
    return body


def _generations(
    key: str,
    model: str,
    prompt: str,
    image: str,
    *,
    response_format: bool,
) -> _Outcome:
    outcome = _post_json(
        _endpoint("images/generations"),
        key,
        _payload(model, prompt, image, response_format=response_format),
    )
    if outcome.image or outcome.stop or not _wants_image_array(outcome):
        return outcome
    logger.info("[图片处理] generations 要求 image 为数组，重试一次")
    return _post_json(
        _endpoint("images/generations"),
        key,
        _payload(model, prompt, [image], response_format=response_format),
    )


def _edits(
    key: str,
    model: str,
    prompt: str,
    source: bytes,
    image_url: str,
    *,
    response_format: bool,
) -> _Outcome:
    extension = _ext_from_bytes(source) or guess_ext_from_url(image_url)
    mime = _mime_for_ext(extension)
    form = {"model": model, "prompt": prompt, "n": "1"}
    if response_format:
        form["response_format"] = "b64_json"
    files = {"image": (f"input{extension}", source, mime)}
    return _post_multipart(_endpoint("images/edits"), key, form, files)


def _post_json(url: str, key: str, body: dict[str, object]) -> _Outcome:
    def send() -> requests.Response:
        return requests.post(
            url,
            json=body,
            headers={**_auth_headers(key), "Content-Type": "application/json"},
            timeout=GENERATION_TIMEOUT_SECONDS,
        )

    return _exchange(send)


def _post_multipart(url: str, key: str, form: dict[str, str], files: dict) -> _Outcome:
    def send() -> requests.Response:
        return requests.post(
            url,
            data=form,
            files=files,
            headers=_auth_headers(key),
            timeout=GENERATION_TIMEOUT_SECONDS,
        )

    return _exchange(send)


def _exchange(send) -> _Outcome:
    last_error: Exception | None = None
    for attempt in range(1, GENERATION_MAX_ATTEMPTS + 1):
        try:
            response = send()
        except requests.exceptions.Timeout:
            last_error = RuntimeError(f"API 请求超时（{GENERATION_TIMEOUT_SECONDS}秒），请稍后重试")
            logger.warning("[图片处理] 请求超时 attempt=%s/%s", attempt, GENERATION_MAX_ATTEMPTS)
        except requests.exceptions.ConnectionError as exc:
            last_error = RuntimeError("无法连接到图片 API，请检查网络")
            logger.warning("[图片处理] 连接失败 attempt=%s/%s: %s", attempt, GENERATION_MAX_ATTEMPTS, exc)
        except requests.exceptions.RequestException as exc:
            last_error = RuntimeError(f"API 请求失败: {exc}")
            logger.warning("[图片处理] 请求异常 attempt=%s/%s: %s", attempt, GENERATION_MAX_ATTEMPTS, exc)
        else:
            parsed = _outcome_from_response(response)
            retryable = response.status_code >= 500 or _should_retry_status(response.status_code)
            if parsed.image or parsed.stop or not retryable:
                return parsed
            last_error = parsed.error
            logger.warning(
                "[图片处理] 可重试状态 attempt=%s/%s status=%s",
                attempt,
                GENERATION_MAX_ATTEMPTS,
                response.status_code,
            )
        if attempt < GENERATION_MAX_ATTEMPTS:
            time.sleep(min(2 ** (attempt - 1), 4))
    return _Outcome(error=last_error or RuntimeError("API 请求失败"), stop=True)


def _outcome_from_response(response: requests.Response) -> _Outcome:
    if response.status_code == 200:
        content_type = response.headers.get("Content-Type", "")
        if content_type.startswith("image/"):
            return _Outcome(image=GeneratedImage(response.content, _ext_from_mime(content_type)))
        try:
            payload = response.json()
        except ValueError:
            return _Outcome(error=RuntimeError(f"API 返回非 JSON 格式: {response.text[:100]}"), retry_base64=True)
        image = _image_from_payload(payload)
        if image:
            return _Outcome(image=image)
        return _Outcome(error=RuntimeError("图片响应为空"), retry_base64=True)

    message = _error_message(response)
    kind = _classify(response.status_code, message)
    error = RuntimeError(f"API 返回错误（{response.status_code}): {message}")
    return _Outcome(
        error=error,
        stop=kind == "auth",
        drop_format=kind == "drop-format",
        retry_base64=kind == "base64",
        use_edits=kind == "edits",
    )


def _image_from_payload(payload: object) -> GeneratedImage | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return None
    item = data[0]
    encoded = item.get("b64_json")
    if isinstance(encoded, str) and encoded.strip():
        raw = base64.b64decode(encoded)
        return GeneratedImage(raw, _ext_from_bytes(raw))
    url = item.get("url")
    if isinstance(url, str) and url.startswith("data:"):
        raw = _decode_data_url(url)
        return GeneratedImage(raw, _ext_from_bytes(raw))
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        raw = download_image_bytes(url)
        return GeneratedImage(raw, _ext_from_bytes(raw) or guess_ext_from_url(url))
    return None


def _error_message(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return (response.text or "")[:300]
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error)[:300]
        if isinstance(error, str):
            return error[:300]
        if data.get("message"):
            return str(data["message"])[:300]
    return (response.text or "")[:300]


def _classify(status: int, message: str) -> str:
    text = message.lower()
    if status in {401, 403}:
        return "auth"
    if status in RETRYABLE_STATUS_CODES:
        return "retry"
    format_rejected = "response_format" in text and _mentions_rejection(text)
    image_rejected = status in {404, 405} or (status in {400, 415, 422} and _mentions_image_param(text))
    if image_rejected:
        return "edits"
    if format_rejected:
        return "drop-format"
    if status in {400, 415, 422}:
        return "base64"
    return "retry" if status >= 500 else "base64"


def _mentions_rejection(text: str) -> bool:
    return any(
        phrase in text
        for phrase in (
            "unknown",
            "unexpected",
            "unsupported",
            "not support",
            "unrecognized",
            "additional propert",
            "invalid parameter",
            "不支持",
            "未知",
            "无法识别",
        )
    )


def _mentions_image_param(text: str) -> bool:
    return "image" in text and _mentions_rejection(text)


def _wants_image_array(outcome: _Outcome) -> bool:
    if outcome.error is None or outcome.use_edits or outcome.stop:
        return False
    text = str(outcome.error).lower()
    return "image" in text and ("array" in text or "数组" in text)


def _should_retry_status(status: int) -> bool:
    return status in RETRYABLE_STATUS_CODES


def _data_url(content: bytes, source_url: str) -> str:
    extension = _ext_from_bytes(content) or guess_ext_from_url(source_url)
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{_mime_for_ext(extension)};base64,{encoded}"


def _decode_data_url(value: str) -> bytes:
    encoded = value.split(",", 1)[1] if "," in value else value
    return base64.b64decode(encoded)


def _mime_for_ext(extension: str) -> str:
    return {".jpg": "image/jpeg", ".webp": "image/webp"}.get(extension, "image/png")


def _ext_from_mime(content_type: str) -> str:
    lowered = content_type.lower()
    if "jpeg" in lowered or "jpg" in lowered:
        return ".jpg"
    if "webp" in lowered:
        return ".webp"
    return ".png"


def _ext_from_bytes(raw: bytes) -> str:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if raw.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(raw) >= 12 and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return ".webp"
    return ""
