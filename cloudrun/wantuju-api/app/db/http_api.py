"""CloudBase PostgREST client for the env PostgreSQL database.

Ordinary reads and writes use ``/v1/rdb/rest/{table}``. Multi-row accounting
goes through ``/v1/rdb/rest/rpc/{function}`` because each HTTP request is its
own transaction. Schema changes use ``POST /v1/rdb/exec-pgsql``.

Docs:
https://docs.cloudbase.net/http-api/basic/overview
https://docs.cloudbase.net/http-api/pgdb/postgresql-restful-api
https://docs.cloudbase.net/database/postgresql/http/rpc
https://docs.cloudbase.net/http-api/pgdb/exec-pgsql
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.db.errors import DatabaseError, business_error
from app.db.repository import Database, _from_millis, row_to_doc
from app.db.rpc import RPC_FUNCTIONS
from app.db.schema import TABLES, Column, Table


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _postgrest_text(value: str) -> str:
    """Render a PostgREST literal.

    CloudBase rejects quoted strings such as ``type=eq."doodle"``. Values
    without filter-grammar characters are sent raw. Quotes stay only for
    commas, spaces, and parentheses that would split ``or()`` / ``in()``.
    """
    if value and not any(char in value for char in ' ,()"\\'):
        return value
    return _quote(value)


def _literal(column: Column, value: Any) -> str:
    if isinstance(value, bool) or column.kind == "bool":
        return "true" if bool(value) else "false"
    if column.kind == "int" or isinstance(value, int):
        return str(int(value))
    if column.kind == "ts":
        if isinstance(value, datetime):
            rendered = value.isoformat()
        else:
            rendered = _from_millis(int(value)).isoformat()
        return _postgrest_text(rendered)
    return _postgrest_text(str(value))


def _predicate(column: Column, value: Any) -> str:
    if isinstance(value, dict):
        if "$in" in value:
            return "in.(" + ",".join(_literal(column, item) for item in value["$in"]) + ")"
        for operator, token in (("$lt", "lt"), ("$lte", "lte"), ("$gt", "gt"), ("$gte", "gte")):
            if operator in value:
                return f"{token}.{_literal(column, value[operator])}"
        raise DatabaseError(f"不支持的查询条件: {column.field}")
    if value is None:
        return "is.null"
    return "eq." + _literal(column, value)


def _group(spec: Table, item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in item.items():
        if key == "$or":
            parts.append("or(" + ",".join(_group(spec, sub) for sub in value) + ")")
            continue
        if key == "$and":
            parts.append("and(" + ",".join(_group(spec, sub) for sub in value) + ")")
            continue
        column = spec.by_field.get(key)
        if column is None:
            raise DatabaseError(f"不支持的查询字段: {spec.name}.{key}")
        parts.append(f"{column.name}.{_predicate(column, value)}")
    if not parts:
        return "true"
    if len(parts) == 1:
        return parts[0]
    return "and(" + ",".join(parts) + ")"


def _sort_desc(value: Any) -> bool:
    if isinstance(value, dict):
        raw = value.get("$numberInt", value.get("$numberLong", value.get("$numberDouble", -1)))
        return int(raw) < 0
    return int(value) < 0


def compile_params(
    spec: Table,
    filt: dict[str, Any] | None,
    sort: dict[str, Any] | None,
    limit: int,
    skip: int,
) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = []
    for key, value in (filt or {}).items():
        if key == "$or":
            params.append(("or", "(" + ",".join(_group(spec, item) for item in value) + ")"))
            continue
        if key == "$and":
            params.append(("and", "(" + ",".join(_group(spec, item) for item in value) + ")"))
            continue
        column = spec.by_field.get(key)
        if column is None:
            raise DatabaseError(f"不支持的查询字段: {spec.name}.{key}")
        params.append((column.name, _predicate(column, value)))
    if sort:
        pieces: list[str] = []
        for field, direction in sort.items():
            column = spec.by_field.get(field)
            if column is None:
                raise DatabaseError(f"不支持的排序字段: {spec.name}.{field}")
            pieces.append(f"{column.name}.desc" if _sort_desc(direction) else f"{column.name}.asc")
        params.append(("order", ",".join(pieces)))
    params.append(("limit", str(int(limit))))
    params.append(("offset", str(int(skip))))
    return params


def _table(name: str) -> Table:
    spec = TABLES.get(name)
    if spec is None:
        raise DatabaseError(f"未知数据表: {name}")
    return spec


def _column_value(column: Column, value: Any) -> Any:
    if value is None:
        if column.kind == "text" and not column.nullable:
            return ""
        return None
    if column.kind == "text":
        return str(value)
    if column.kind == "int":
        return int(value)
    if column.kind == "bool":
        return bool(value)
    if column.kind == "ts":
        if isinstance(value, datetime):
            moment = value if value.tzinfo else value.replace(tzinfo=_from_millis(0).tzinfo)
            return moment.isoformat()
        return _from_millis(int(value)).isoformat()
    if column.kind == "date":
        if hasattr(value, "isoformat") and not isinstance(value, str):
            return value.isoformat()
        return str(value)
    if column.kind == "jsonb":
        return value
    raise DatabaseError(f"未知字段类型: {column.kind}")


def document_columns(spec: Table, document: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for field, value in document.items():
        if field == "_id" and not value:
            continue
        column = spec.by_field.get(field)
        if column is None:
            raise DatabaseError(f"不支持的写入字段: {spec.name}.{field}")
        body[column.name] = _column_value(column, value)
    return body


def _content_range_total(headers: dict[str, str]) -> int:
    raw = headers.get("content-range", "")
    if "/" not in raw:
        raise DatabaseError("PostgreSQL 计数失败: 缺少 Content-Range")
    total = raw.rsplit("/", 1)[-1].strip()
    if total == "*" or not total:
        raise DatabaseError("PostgreSQL 计数失败: 未返回精确总数")
    return int(total)


class RdbClient:
    def __init__(self, env_id: str | None = None, apikey: str | None = None, timeout: int = 30):
        self.env_id = (env_id or os.getenv("CLOUDBASE_ENV_ID", "")).strip()
        self.apikey = (apikey or os.getenv("CLOUDBASE_APIKEY", "")).strip()
        self.timeout = timeout
        if not self.env_id:
            raise DatabaseError("CLOUDBASE_ENV_ID 未设置")
        if not self.apikey:
            raise DatabaseError("CLOUDBASE_APIKEY 未设置")
        self.base_url = f"https://{self.env_id}.api.tcloudbasegateway.com"

    def request(
        self,
        method: str,
        path: str,
        *,
        params: list[tuple[str, str]] | None = None,
        json_body: Any = None,
        prefer: str | None = None,
    ) -> tuple[Any, dict[str, str]]:
        if not path.startswith("/"):
            path = f"/{path}"
        query = f"?{urlencode(params)}" if params else ""
        body = None if json_body is None else json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.apikey}",
        }
        if prefer:
            headers["Prefer"] = prefer
        request = Request(f"{self.base_url}{path}{query}", data=body, method=method, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                header_map = {key.lower(): value for key, value in response.headers.items()}
        except HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = ""
            primary = ""
            try:
                parsed = json.loads(detail) if detail else {}
                if isinstance(parsed, dict):
                    primary = str(parsed.get("message") or "")
            except Exception:
                primary = ""
            status = getattr(exc, "code", "")
            message = f"CloudBase PostgreSQL 请求失败: {method} {path}"
            if status:
                message = f"{message} ({status})"
            if detail:
                message = f"{message} - {detail}"
            raise DatabaseError(message, primary=primary) from exc
        except URLError as exc:
            raise DatabaseError(f"CloudBase PostgreSQL 请求失败: {method} {path} - {exc.reason}") from exc
        if not raw:
            return None, header_map
        try:
            data = json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            raise DatabaseError(f"CloudBase PostgreSQL 返回非 JSON: {method} {path}") from exc
        if isinstance(data, dict) and data.get("code") and data.get("message") and "user" not in data and "ok" not in data:
            raise DatabaseError(
                f"CloudBase PostgreSQL 返回业务错误: {method} {path} - {data}",
                primary=str(data.get("message") or ""),
            )
        return data, header_map


def execute_admin_sql(statement: str, *, role: str = "cloudbase_postgres", timeout: int = 60) -> list[Any]:
    """Run one statement as an admin role. DDL returns an empty list."""
    data, _headers = RdbClient(timeout=timeout).request(
        "POST",
        "/v1/rdb/exec-pgsql",
        params=[("role", role)],
        json_body={"sql": statement, "role": role},
    )
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "rows", "result", "Results"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    raise DatabaseError(f"exec-pgsql 返回无法识别: {str(data)[:300]}")


class HttpDatabase(Database):
    """Document-shaped access through the CloudBase PostgreSQL HTTP API."""

    def __init__(self, env_id: str | None = None, apikey: str | None = None, timeout: int = 30):
        self.client = RdbClient(env_id=env_id, apikey=apikey, timeout=timeout)

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        raise DatabaseError("HTTP 数据层没有跨请求事务。积分、退款和任务领取走 RPC 函数。")
        yield

    def call(self, name: str, payload: dict[str, Any]) -> Any:
        if name not in RPC_FUNCTIONS:
            raise DatabaseError(f"未知数据库函数: {name}")
        try:
            data, _headers = self.client.request(
                "POST",
                f"/v1/rdb/rest/rpc/{name}",
                json_body={"payload": payload},
            )
        except DatabaseError as exc:
            business = business_error(exc)
            if business is not None:
                raise business from exc
            raise
        return data

    def get_document(self, table: str, doc_id: str) -> dict[str, Any]:
        return self.find_one(table, {"_id": doc_id}) or {}

    def find_one(self, table: str, filt: dict[str, Any]) -> dict[str, Any] | None:
        rows = self.find_many(table, filt, limit=1)
        return rows[0] if rows else None

    def find_many(
        self,
        table: str,
        filt: dict[str, Any] | None = None,
        *,
        sort: dict[str, Any] | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        spec = _table(table)
        data, _headers = self.client.request(
            "GET",
            f"/v1/rdb/rest/{spec.name}",
            params=compile_params(spec, filt, sort, limit, skip),
        )
        rows = data if isinstance(data, list) else ([] if data is None else [data])
        return [row_to_doc(table, row) for row in rows]

    def count_documents(self, table: str, filt: dict[str, Any] | None = None) -> int:
        spec = _table(table)
        params = [("select", "id"), *compile_params(spec, filt, None, 1, 0)]
        _data, headers = self.client.request(
            "GET",
            f"/v1/rdb/rest/{spec.name}",
            params=params,
            prefer="count=exact",
        )
        return _content_range_total(headers)

    def insert_documents(self, table: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
        if not documents:
            return {"ids": [], "_id": None}
        spec = _table(table)
        data, _headers = self.client.request(
            "POST",
            f"/v1/rdb/rest/{spec.name}",
            json_body=[document_columns(spec, document) for document in documents],
            prefer="return=representation",
        )
        rows = data if isinstance(data, list) else [data]
        ids = [str(row["id"]) for row in rows if isinstance(row, dict) and row.get("id")]
        return {"ids": ids, "_id": ids[0] if ids else None}

    def update_document(self, table: str, doc_id: str, data: dict[str, Any]) -> dict[str, Any]:
        _table(table)
        row = self.call("wantuju_patch_document", {"table": table, "id": doc_id, "patch": data})
        if not row:
            raise DatabaseError("文档不存在")
        return row_to_doc(table, row)

    def delete_document(self, table: str, doc_id: str) -> dict[str, Any]:
        spec = _table(table)
        data, _headers = self.client.request(
            "DELETE",
            f"/v1/rdb/rest/{spec.name}",
            params=[("id", "eq." + _literal(spec.by_field["_id"], doc_id))],
            prefer="return=representation",
        )
        rows = data if isinstance(data, list) else ([] if not data else [data])
        if not rows:
            raise DatabaseError("文档不存在")
        return {"deleted": len(rows)}

    def list_documents(self, table: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        return self.find_many(table, {}, limit=limit, skip=offset)
