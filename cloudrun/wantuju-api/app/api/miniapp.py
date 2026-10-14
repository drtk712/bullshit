"""Miniapp identity and diagnostics routes.

callContainer travels the WeChat private path. That ingress verifies the user
and writes ``x-wx-openid`` (or ``x-wx-from-openid`` when the env is shared)
together with ``x-wx-source``. A public-domain request does not get those
headers from WeChat. Official guidance when public access stays on is to
treat a request as a WeChat call only when ``x-wx-source`` is present, so a
client-supplied ``x-wx-openid`` alone is ignored.

``/admin`` does not use this identity. It stays on the public host and uses
its own password cookie.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Request

from app.core.config import settings


router = APIRouter()

_WECHAT_OPENID_HEADERS = ("x-wx-openid", "x-wx-from-openid")


def cloudbase_headers(request: Request) -> dict[str, str]:
    prefixes = ("x-wx-", "x-cloudbase-", "x-tcb-")
    return {
        key: value
        for key, value in request.headers.items()
        if key.lower().startswith(prefixes)
    }


def wechat_gateway_request(headers: dict[str, str]) -> bool:
    """True when the Cloud Run WeChat ingress marked the call."""
    return bool(str(headers.get("x-wx-source") or "").strip())


def extract_openid(headers: dict[str, str]) -> str:
    if not wechat_gateway_request(headers):
        return ""
    for key in _WECHAT_OPENID_HEADERS:
        value = str(headers.get(key) or "").strip()
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
        "wechatGateway": wechat_gateway_request(headers),
        "headers": {key: "[redacted]" if "token" in key else value for key, value in headers.items()},
        "headerKeys": sorted(headers.keys()),
        "env": settings.run_env,
    }
