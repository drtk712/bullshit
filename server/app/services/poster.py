"""Poster generation helpers."""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests

from app.config import settings


logger = logging.getLogger(__name__)


def mask_url(url: str) -> str:
    """Mask a URL for logs."""
    if not url:
        return ""
    try:
        parsed = url.split("/")
        domain = parsed[2] if len(parsed) > 2 else "unknown"
        return f"{domain}/..."
    except Exception:
        return url[:20] + "..."


def generate_poster(image_url: str, job_type: str, generation_prompt: str) -> str:
    """Call the image generation model and return the model text response."""
    logger.info("[海报生成] 类型: %s, 图片: %s", job_type, mask_url(image_url))

    try:
        resp = requests.post(
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
            timeout=180,
        )
    except requests.exceptions.Timeout as exc:
        raise RuntimeError("API 请求超时（180秒），请稍后重试") from exc
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError("无法连接到 API 服务，请检查网络") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"API 请求失败: {exc}") from exc

    if resp.status_code != 200:
        error_detail = ""
        try:
            error_data = resp.json()
            error_detail = error_data.get("error", {}).get("message", "")
        except ValueError:
            error_detail = resp.text[:100]
        raise RuntimeError(f"API 返回错误（{resp.status_code}): {error_detail}")

    try:
        result = resp.json()
    except requests.exceptions.JSONDecodeError as exc:
        raise RuntimeError(f"API 返回非 JSON 格式: {resp.text[:100]}") from exc

    content = result.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError("大模型返回内容为空")

    logger.info("[海报生成] 大模型返回内容长度: %d 字符", len(content))
    return content


def extract_url_from_response(content: str) -> str:
    """Extract the generated image URL from model response text."""
    markdown_match = re.search(r"!\[.*?\]\((https?://[^\s\)]+)\)", content)
    if markdown_match:
        url = markdown_match.group(1)
        logger.info("[URL提取] Markdown 格式: %s", mask_url(url))
        return url

    url_matches = re.findall(r"https?://[^\s\"'\)<>\]]+\.(?:png|jpg|jpeg|webp)", content, re.I)
    if url_matches:
        logger.info("[URL提取] 直接链接: %s", mask_url(url_matches[0]))
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
