"""Miniapp identity and diagnostics routes."""
from __future__ import annotations

import time

from fastapi import APIRouter, Request

from app.core.config import settings


router = APIRouter()


def cloudbase_headers(request: Request) -> dict[str, str]:
    prefixes = ("x-wx-", "x-cloudbase-", "x-tcb-")
    return {
        key: value
        for key, value in request.headers.items()
        if key.lower().startswith(prefixes)
    }


def extract_openid(headers: dict[str, str]) -> str:
    for key in (
        "x-wx-openid",
        "x-wx-from-openid",
        "x-cloudbase-openid",
        "x-tcb-openid",
    ):
        value = headers.get(key)
        if value:
            return value
    return ""


@router.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "wantuju-api",
        "timestamp": time.time(),
    }


@router.get("/miniapp/whoami")
async def whoami(request: Request) -> dict[str, object]:
    headers = cloudbase_headers(request)
    return {
        "openid": extract_openid(headers),
        "headers": headers,
        "headerKeys": sorted(headers.keys()),
        "env": settings.run_env,
    }
