"""Shared route dependencies."""
from __future__ import annotations

from fastapi import HTTPException, Request

from app.api.miniapp import cloudbase_headers, extract_openid


def require_openid(request: Request) -> str:
    openid = extract_openid(cloudbase_headers(request))
    if not openid:
        raise HTTPException(status_code=401, detail="无法获取用户身份")
    return openid
