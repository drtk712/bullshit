"""Thin CloudBase HTTP API client.

This module intentionally only wraps the common HTTP concerns. Higher-level
NoSQL helpers should build paths and request bodies explicitly from the docs.
"""
from __future__ import annotations

import os
from typing import Any, Literal

import requests
from dotenv import load_dotenv

load_dotenv()


HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class CloudBaseError(Exception):
    """Base CloudBase client error."""


class CloudBaseConfigError(CloudBaseError):
    """Raised when required CloudBase environment variables are missing."""


class CloudBaseRequestError(CloudBaseError):
    """Raised when the HTTP request fails or CloudBase returns an error."""

    def __init__(self, message: str, status_code: int | None = None, response_data: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class CloudBaseClient:
    def __init__(
        self,
        env_id: str | None = None,
        access_token: str | None = None,
        timeout: int = 30,
    ):
        self.env_id = env_id or os.getenv("CLOUDBASE_ENV_ID")
        self.access_token = access_token or os.getenv("CLOUDBASE_ACCESS_TOKEN")
        self.timeout = timeout

        if not self.env_id:
            raise CloudBaseConfigError("CLOUDBASE_ENV_ID 未设置")
        if not self.access_token:
            raise CloudBaseConfigError("CLOUDBASE_ACCESS_TOKEN 未设置")

        self.base_url = f"https://{self.env_id}.api.tcloudbasegateway.com"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

    def request(self, method: HttpMethod, path: str, **kwargs) -> Any:
        """Send one CloudBase HTTP API request."""
        if not path.startswith("/"):
            path = f"/{path}"

        url = f"{self.base_url}{path}"
        headers = self.headers.copy()

        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        timeout = kwargs.pop("timeout", self.timeout)

        try:
            response = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
            response.encoding = "utf-8"
            response.raise_for_status()

            if not response.content:
                return True

            data = response.json()
            nested_error = data.get("Response", {}).get("Error") if isinstance(data, dict) else None
            if nested_error:
                raise CloudBaseRequestError(
                    f"CloudBase API 返回业务错误: {method} {path}",
                    status_code=response.status_code,
                    response_data=data,
                )
            return data
        except requests.exceptions.HTTPError as exc:
            response = exc.response
            status_code = response.status_code if response is not None else None
            response_data = None
            if response is not None:
                response.encoding = "utf-8"
                try:
                    response_data = response.json()
                except ValueError:
                    response_data = response.text[:500]
            raise CloudBaseRequestError(
                f"CloudBase API 请求失败: {method} {path}",
                status_code=status_code,
                response_data=response_data,
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise CloudBaseRequestError(f"CloudBase API 连接失败: {method} {path}") from exc
        except ValueError as exc:
            raise CloudBaseRequestError(f"CloudBase API 返回非 JSON: {method} {path}") from exc


class _CloudBaseProxy:
    """Lazy module-level client compatible with `cloudbase.request(...)`."""

    _client: CloudBaseClient | None = None

    def _get_client(self) -> CloudBaseClient:
        if self._client is None:
            self._client = CloudBaseClient()
        return self._client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get_client(), name)


cloudbase = _CloudBaseProxy()
