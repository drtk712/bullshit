"""Image generation model helpers."""
from __future__ import annotations

import logging
import re
import time
from urllib.parse import urlparse

import requests

from app.core.config import settings


logger = logging.getLogger(__name__)
GENERATION_TIMEOUT_SECONDS = 300
GENERATION_MAX_ATTEMPTS = 3
RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def mask_url(url: str) -> str:
    if not url:
        return ""
    try:
        parts = url.split("/")
        domain = parts[2] if len(parts) > 2 else "unknown"
        return f"{domain}/..."
    except Exception:
        return f"{url[:20]}..."


def generate_poster(image_url: str, job_type: str, generation_prompt: str) -> str:
    if not settings.memefast_api_key:
        raise RuntimeError("MEMEFAST_API_KEY 未设置")

    logger.info("[图片处理] type=%s image=%s", job_type, mask_url(image_url))
    last_error: Exception | None = None
    for attempt in range(1, GENERATION_MAX_ATTEMPTS + 1):
        try:
            response = requests.post(
                settings.memefast_api_url,
                json={
                    "model": settings.memefast_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": image_url}},
                                {"type": "text", "text": generation_prompt},
                            ],
                        }
                    ],
                    "stream": False,
                },
                headers={
                    "Authorization": f"Bearer {settings.memefast_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=GENERATION_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                detail = ""
                try:
                    detail = response.json().get("error", {}).get("message", "")
                except ValueError:
                    detail = response.text[:100]
                last_error = RuntimeError(f"API 返回错误（{response.status_code}): {detail}")
                if response.status_code not in RETRYABLE_STATUS_CODES:
                    raise last_error
                logger.warning("[图片处理] 可重试状态 attempt=%s/%s status=%s detail=%s", attempt, GENERATION_MAX_ATTEMPTS, response.status_code, detail)
            else:
                try:
                    result = response.json()
                except requests.exceptions.JSONDecodeError:
                    last_error = RuntimeError(f"API 返回非 JSON 格式: {response.text[:100]}")
                    logger.warning("[图片处理] 非 JSON 响应 attempt=%s/%s", attempt, GENERATION_MAX_ATTEMPTS)
                else:
                    content = result.get("choices", [{}])[0].get("message", {}).get("content")
                    if content:
                        return str(content)
                    last_error = RuntimeError("大模型返回内容为空")
                    logger.warning("[图片处理] 返回内容为空 attempt=%s/%s", attempt, GENERATION_MAX_ATTEMPTS)
        except requests.exceptions.Timeout:
            last_error = RuntimeError(f"API 请求超时（{GENERATION_TIMEOUT_SECONDS}秒），请稍后重试")
            logger.warning("[图片处理] 请求超时 attempt=%s/%s", attempt, GENERATION_MAX_ATTEMPTS)
        except requests.exceptions.ConnectionError as exc:
            last_error = RuntimeError("无法连接到 API 服务，请检查网络")
            logger.warning("[图片处理] 连接失败 attempt=%s/%s: %s", attempt, GENERATION_MAX_ATTEMPTS, exc)
        except requests.exceptions.RequestException as exc:
            last_error = RuntimeError(f"API 请求失败: {exc}")
            logger.warning("[图片处理] 请求异常 attempt=%s/%s: %s", attempt, GENERATION_MAX_ATTEMPTS, exc)

        if attempt < GENERATION_MAX_ATTEMPTS:
            time.sleep(min(2 ** (attempt - 1), 4))

    raise last_error or RuntimeError("API 请求失败")


def extract_url_from_response(content: str) -> str:
    markdown_match = re.search(r"!\[.*?\]\((https?://[^\s\)]+)\)", content)
    if markdown_match:
        return markdown_match.group(1)

    url_matches = re.findall(r"https?://[^\s\"'\)<>\]]+\.(?:png|jpg|jpeg|webp)", content, re.I)
    if url_matches:
        return url_matches[0]

    raise RuntimeError("无法从响应中提取图片 URL")


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
