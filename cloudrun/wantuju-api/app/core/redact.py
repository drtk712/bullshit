"""Drop credential material before it can be returned or written to logs."""
from __future__ import annotations

_MARKERS = (
    "x-cloudbase-context",
    "x-wx-cloudbase-access-token",
    "x-cos-security-token",
    "serviceaccesstoken",
    "tmpsecret",
    "secretkey",
    "secretid",
)


def redact_secrets(text: str) -> str:
    lowered = text.lower()
    if any(marker in lowered for marker in _MARKERS):
        return "请求失败"
    return text
