"""Public callers cannot supply an openid. Admin stays on its own login."""
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.admin.routes import router as admin_router
from app.api import miniapp, users
from app.api.deps import require_openid
from app.api.miniapp import extract_openid
from app.cloudbase.client import CloudBaseError
from app.core.redact import redact_secrets


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(miniapp.router)
    app.include_router(users.router)
    app.include_router(admin_router, prefix="/admin")
    return app


def test_openid_requires_wechat_gateway_header():
    assert extract_openid({"x-wx-openid": "forged"}) == ""
    assert extract_openid({"x-wx-source": " ", "x-wx-openid": "forged"}) == ""
    assert extract_openid({"x-cloudbase-openid": "forged", "x-wx-source": "wx_client"}) == ""
    assert extract_openid({"x-wx-source": "wx_client", "x-wx-openid": " real "}) == "real"
    assert extract_openid({"x-wx-source": "miniprogram", "x-wx-from-openid": "from-user"}) == "from-user"


def test_public_domain_cannot_impersonate_and_admin_stays_open():
    client = TestClient(_app())

    forged = client.get("/miniapp/me", headers={"x-wx-openid": "attacker"})
    assert forged.status_code == 401

    legacy = client.get(
        "/miniapp/me",
        headers={"x-wx-source": "wx_client", "x-cloudbase-openid": "attacker"},
    )
    assert legacy.status_code == 401

    whoami = client.get("/miniapp/whoami", headers={"x-wx-openid": "attacker"}).json()
    assert whoami == {"openidResolved": False}

    trusted = client.get(
        "/miniapp/me",
        headers={"x-wx-source": "wx_client", "x-wx-openid": "openid-trusted"},
    )
    assert trusted.status_code == 200
    assert trusted.json()["success"] is True

    assert client.get("/admin/login").status_code == 200
    assert client.get("/health").status_code == 200


def test_whoami_returns_no_header_values():
    secret_id = "AKIDwhoami-sentinel-secret-id"
    secret_key = "whoami-sentinel-secret-key"
    session_token = "whoami-sentinel-session-token"
    access_token = "whoami-sentinel-service-access-token"
    openid = "openid-sentinel-value"
    context = (
        '{"tmpSecret":{"secretId":"%s","secretKey":"%s","token":"%s"},'
        '"serviceAccessToken":"%s"}' % (secret_id, secret_key, session_token, access_token)
    )
    client = TestClient(_app())
    response = client.get(
        "/miniapp/whoami",
        headers={
            "x-wx-source": "wx_client",
            "x-wx-openid": openid,
            "x-cloudbase-context": context,
            "x-wx-cloudbase-access-token": access_token,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"openidResolved": True}
    body = response.text
    for secret in (
        secret_id,
        secret_key,
        session_token,
        access_token,
        openid,
        "x-cloudbase-context",
        "x-wx-openid",
        "tmpSecret",
        "secretKey",
        "serviceAccessToken",
        "headerKeys",
        "wechatGateway",
    ):
        assert secret not in body


def test_credential_text_is_redacted_before_it_can_be_logged():
    raw = 'x-cloudbase-context {"tmpSecret":{"secretId":"AKIDleak","secretKey":"keyleak"}}'
    assert "AKIDleak" not in redact_secrets(raw)
    assert "keyleak" not in str(CloudBaseError(raw))


def test_require_openid_rejects_a_bare_header():
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/miniapp/me",
        "raw_path": b"/miniapp/me",
        "query_string": b"",
        "headers": [(b"x-wx-openid", b"forged")],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }
    with pytest.raises(HTTPException, match="无法获取用户身份"):
        require_openid(Request(scope))
