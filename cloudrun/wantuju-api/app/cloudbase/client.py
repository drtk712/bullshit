"""Small CloudBase HTTP client for the Wantuju CloudRun service."""
from __future__ import annotations

import json
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import settings


HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class CloudBaseError(Exception):
    """Raised when CloudBase HTTP API cannot complete a request."""

    def __init__(self, message: str) -> None:
        from app.core.redact import redact_secrets

        super().__init__(redact_secrets(message))


class CloudBaseClient:
    def __init__(self, env_id: str | None = None, apikey: str | None = None, timeout: int = 30):
        self.env_id = env_id or settings.cloudbase_env_id
        self.apikey = apikey or settings.cloudbase_apikey
        self.timeout = timeout

        if not self.env_id:
            raise CloudBaseError("CLOUDBASE_ENV_ID 未设置")
        if not self.apikey:
            raise CloudBaseError("CLOUDBASE_APIKEY 未设置")

        self.base_url = f"https://{self.env_id}.api.tcloudbasegateway.com"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.apikey}",
        }

    def request(self, method: HttpMethod, path: str, **kwargs: Any) -> Any:
        if not path.startswith("/"):
            path = f"/{path}"

        params = kwargs.pop("params", None)
        query = f"?{urlencode(params)}" if params else ""
        payload = kwargs.pop("json", None)
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self.base_url}{path}{query}",
            data=body,
            method=method,
            headers=self.headers,
        )

        try:
            with urlopen(request, timeout=kwargs.pop("timeout", self.timeout)) as response:
                content = response.read()
            if not content:
                return True
            data = json.loads(content.decode("utf-8"))
            if isinstance(data, dict):
                nested_error = data.get("Response", {}).get("Error")
                if nested_error:
                    raise CloudBaseError(f"CloudBase API 返回业务错误: {method} {path} - {nested_error}")
                if data.get("code") and data.get("message"):
                    raise CloudBaseError(f"CloudBase API 返回业务错误: {method} {path} - {data}")
            return data
        except HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")[:500]
            except Exception:
                detail = ""
            status = getattr(exc, "code", "")
            message = f"CloudBase API 请求失败: {method} {path}"
            if status:
                message = f"{message} ({status})"
            if detail:
                message = f"{message} - {detail}"
            raise CloudBaseError(message) from exc
        except URLError as exc:
            raise CloudBaseError(f"CloudBase API 请求失败: {method} {path} - {exc.reason}") from exc
        except ValueError as exc:
            raise CloudBaseError(f"CloudBase API 返回非 JSON: {method} {path}") from exc
