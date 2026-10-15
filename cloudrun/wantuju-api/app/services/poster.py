"""OpenAI-compatible image generation.

Live calls against the telecom gateway showed that ``/images/generations``
accepts an ``image`` field and still ignores it. Image-to-image therefore
always downloads the user's photo and posts it as multipart ``image`` to
``/images/edits``. ``/images/generations`` is only used when there is no
input photo.

Responses are usually ``data[0].b64_json`` PNG bodies of several megabytes
and can take well over half a minute. The client waits at least two minutes,
then converts the result to a smaller JPEG before it is stored. No fast
model, quality, or mode parameter is sent.
"""
from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urlparse

import requests
from PIL import Image, ImageOps

from app.core.config import image_api_base_url, image_api_key, image_model


logger = logging.getLogger(__name__)
GENERATION_TIMEOUT_SECONDS = 180
GENERATION_MAX_ATTEMPTS = 2
RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
STORED_JPEG_QUALITY = 85
STORED_MAX_EDGE = 2048


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
    image_tokens: int | None = None


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
    """Generate one image. A photo URL uses edits; an empty URL uses generations."""
    key = image_api_key()
    if not key:
        raise RuntimeError("IMAGE_API_KEY 未设置")
    model = _checked_model()
    if (image_url or "").strip():
        logger.info("[图片处理] type=%s model=%s edits image=%s", job_type, model, mask_url(image_url))
        return _edit_photo(key, model, generation_prompt, image_url)
    logger.info("[图片处理] type=%s model=%s generations 无输入图", job_type, model)
    return _generate_text(key, model, generation_prompt)


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


def _edit_photo(key: str, model: str, prompt: str, image_url: str) -> GeneratedImage:
    source = download_image_bytes(image_url)
    if not source:
        raise RuntimeError("用户照片为空")
    outcome = _edits(key, model, prompt, source, image_url, response_format=True)
    if outcome.drop_format and outcome.image is None and not outcome.stop:
        outcome = _edits(key, model, prompt, source, image_url, response_format=False)
    if outcome.image is None:
        raise outcome.error or RuntimeError("图片生成失败")
    _require_input_image(outcome)
    return _prepare_for_storage(outcome.image)


def _generate_text(key: str, model: str, prompt: str) -> GeneratedImage:
    outcome = _generations(key, model, prompt, response_format=True)
    if outcome.drop_format and outcome.image is None and not outcome.stop:
        outcome = _generations(key, model, prompt, response_format=False)
    if outcome.image is None:
        raise outcome.error or RuntimeError("图片生成失败")
    return _prepare_for_storage(outcome.image)


def _require_input_image(outcome: _Outcome) -> None:
    if outcome.image_tokens is None:
        return
    if outcome.image_tokens <= 0:
        raise RuntimeError("图片网关未使用输入照片")


def _checked_model() -> str:
    model = image_model()
    if "fast" in model.lower():
        raise RuntimeError("IMAGE_MODEL 不能使用 fast 变体")
    return model


def _endpoint(path: str) -> str:
    return f"{image_api_base_url()}/{path.lstrip('/')}"


def _auth_headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def _generations(key: str, model: str, prompt: str, *, response_format: bool) -> _Outcome:
    body: dict[str, object] = {"model": model, "prompt": prompt, "n": 1}
    if response_format:
        body["response_format"] = "b64_json"
    return _post_json(_endpoint("images/generations"), key, body)


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
    return _post_multipart(_endpoint("images/edits"), key, form, files, require_image_tokens=True)


def _post_json(url: str, key: str, body: dict[str, object]) -> _Outcome:
    def send() -> requests.Response:
        return requests.post(
            url,
            json=body,
            headers={**_auth_headers(key), "Content-Type": "application/json"},
            timeout=GENERATION_TIMEOUT_SECONDS,
        )

    return _exchange(send, require_image_tokens=False)


def _post_multipart(
    url: str,
    key: str,
    form: dict[str, str],
    files: dict,
    *,
    require_image_tokens: bool,
) -> _Outcome:
    def send() -> requests.Response:
        return requests.post(
            url,
            data=form,
            files=files,
            headers=_auth_headers(key),
            timeout=GENERATION_TIMEOUT_SECONDS,
        )

    return _exchange(send, require_image_tokens=require_image_tokens)


def _exchange(send, *, require_image_tokens: bool) -> _Outcome:
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
            parsed = _outcome_from_response(response, require_image_tokens=require_image_tokens)
            retryable = response.status_code >= 500 or response.status_code in RETRYABLE_STATUS_CODES
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


def _outcome_from_response(response: requests.Response, *, require_image_tokens: bool) -> _Outcome:
    if response.status_code == 200:
        content_type = response.headers.get("Content-Type", "")
        if content_type.startswith("image/"):
            return _Outcome(image=GeneratedImage(response.content, _ext_from_mime(content_type)))
        try:
            payload = response.json()
        except ValueError:
            return _Outcome(error=RuntimeError(f"API 返回非 JSON 格式: {response.text[:100]}"), stop=True)
        image = _image_from_payload(payload)
        if image is None:
            return _Outcome(error=RuntimeError("图片响应为空"), stop=True)
        tokens = _image_tokens(payload) if require_image_tokens else None
        if require_image_tokens and tokens is not None and tokens <= 0:
            return _Outcome(error=RuntimeError("图片网关未使用输入照片"), stop=True)
        return _Outcome(image=image, image_tokens=tokens)

    message = _error_message(response)
    kind = _classify(response.status_code, message)
    error = RuntimeError(f"API 返回错误（{response.status_code}): {message}")
    return _Outcome(
        error=error,
        stop=kind == "auth",
        drop_format=kind == "drop-format",
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
        try:
            raw = base64.b64decode(encoded)
        except (ValueError, TypeError):
            return None
        return GeneratedImage(raw, _ext_from_bytes(raw) or ".png")
    url = item.get("url")
    if isinstance(url, str) and url.startswith("data:"):
        raw = _decode_data_url(url)
        return GeneratedImage(raw, _ext_from_bytes(raw) or ".png")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        raw = download_image_bytes(url)
        return GeneratedImage(raw, _ext_from_bytes(raw) or guess_ext_from_url(url))
    return None


def _image_tokens(payload: object) -> int | None:
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    details = usage.get("input_tokens_details")
    if not isinstance(details, dict) or "image_tokens" not in details:
        return None
    try:
        return int(details["image_tokens"])
    except (TypeError, ValueError):
        return None


def _prepare_for_storage(image: GeneratedImage) -> GeneratedImage:
    try:
        with Image.open(BytesIO(image.content)) as raw:
            converted = ImageOps.exif_transpose(raw)
            if converted.mode in {"RGBA", "LA"} or (converted.mode == "P" and "transparency" in converted.info):
                rgba = converted.convert("RGBA")
                background = Image.new("RGB", rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.getchannel("A"))
                converted = background
            elif converted.mode != "RGB":
                converted = converted.convert("RGB")
            width, height = converted.size
            long_edge = max(width, height)
            if long_edge > STORED_MAX_EDGE:
                scale = STORED_MAX_EDGE / long_edge
                converted = converted.resize(
                    (max(1, round(width * scale)), max(1, round(height * scale))),
                    Image.Resampling.LANCZOS,
                )
            buffer = BytesIO()
            converted.save(buffer, format="JPEG", quality=STORED_JPEG_QUALITY, optimize=True)
    except Exception as exc:
        logger.warning("[图片处理] 结果压缩失败，按原图保存: %s", exc)
        return image
    stored = buffer.getvalue()
    logger.info("[图片处理] 结果 %s bytes -> jpeg %s bytes", len(image.content), len(stored))
    return GeneratedImage(stored, ".jpg")


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
    if "response_format" in text and _mentions_rejection(text):
        return "drop-format"
    return "retry" if status >= 500 else "stop"


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
