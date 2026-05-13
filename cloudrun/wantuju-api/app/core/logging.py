"""Logging helpers for CloudRun runtime."""
from __future__ import annotations

import logging
import sys
import time
from typing import Any

from fastapi import Request

from app.api.miniapp import cloudbase_headers, extract_openid


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )


def mask_openid(openid: str | None) -> str:
    value = str(openid or "")
    if len(value) <= 10:
        return value or "-"
    return f"{value[:6]}...{value[-4:]}"


def compact_error(error: Exception | str, limit: int = 180) -> str:
    text = str(error or "").replace("\n", " ").strip()
    return text[:limit]


def request_openid(request: Request) -> str:
    return extract_openid(cloudbase_headers(request))


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    parts = [f"event={event}"]
    for key, value in fields.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    logger.info(" ".join(parts))


async def request_log_middleware(request: Request, call_next):
    logger = logging.getLogger("app.request")
    started = time.perf_counter()
    openid = request_openid(request)
    path = request.url.path

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.exception(
            "event=http_error method=%s path=%s openid=%s duration_ms=%s error=%s",
            request.method,
            path,
            mask_openid(openid),
            duration_ms,
            compact_error(exc),
        )
        raise

    duration_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "event=http method=%s path=%s status=%s openid=%s duration_ms=%s",
        request.method,
        path,
        response.status_code,
        mask_openid(openid),
        duration_ms,
    )
    return response
