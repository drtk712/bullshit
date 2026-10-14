"""CloudBase PostgREST client: query shape, RPC errors, and migration dispatch."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from email.message import EmailMessage
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import unquote

import pytest

from app.db.errors import DatabaseError
from app.db.http_api import HttpDatabase, compile_params, execute_admin_sql
from app.db.schema import TABLES


class _Headers(dict):
    def items(self):
        return super().items()


class _Response:
    def __init__(self, body: bytes, headers: dict[str, str]):
        self._body = body
        self.headers = _Headers(headers)

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False


def test_recovery_filter_compiles_to_postgrest_or():
    params = dict(
        compile_params(
            TABLES["feature_jobs"],
            {
                "$or": [
                    {"status": "pending"},
                    {"status": "processing", "updatedAt": {"$lt": 1_700_000_000_000}},
                ]
            },
            {"createdAt": 1},
            50,
            0,
        )
    )
    assert params["or"].startswith("(status.eq.")
    assert "and(status.eq." in params["or"]
    assert "updated_at.lt." in params["or"]
    assert params["order"] == "created_at.asc"
    assert params["limit"] == "50"


def test_in_filter_uses_postgrest_list():
    params = dict(
        compile_params(
            TABLES["feature_jobs"],
            {"status": {"$in": ["pending", "processing"]}},
            None,
            12,
            0,
        )
    )
    assert params["status"] == 'in.("pending","processing")'


def test_database_url_keeps_psycopg_fallback():
    from app.core.config import data_backend
    from app.db.repository import Database

    assert data_backend() == "postgres"
    assert not isinstance(Database(), HttpDatabase)


def test_http_is_the_default_without_a_dsn(monkeypatch):
    from app.core.config import data_backend
    from app.db.repository import Database

    monkeypatch.delenv("DATABASE_URL", raising=False)
    for name in ("PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGPORT"):
        monkeypatch.delenv(name, raising=False)
    assert data_backend() == "http"
    database = Database()
    assert isinstance(database, HttpDatabase)


def test_find_many_maps_rows_and_sends_bearer_token(monkeypatch):
    captured: dict = {}

    def fake_urlopen(request, timeout=30):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        body = json.dumps(
            [
                {
                    "id": "job-1",
                    "openid": "user-1",
                    "type": "palm",
                    "status": "pending",
                    "points_consumed": False,
                    "created_at": "2026-10-14T00:00:00+00:00",
                    "param": {"a": 1},
                }
            ]
        ).encode()
        return _Response(body, {})

    monkeypatch.setattr("app.db.http_api.urlopen", fake_urlopen)
    rows = HttpDatabase(env_id="env", apikey="test-key").find_many(
        "feature_jobs",
        {"openid": "user-1"},
        sort={"createdAt": -1},
        limit=10,
    )
    assert rows[0]["_id"] == "job-1"
    assert rows[0]["openid"] == "user-1"
    assert rows[0]["pointsConsumed"] is False
    assert rows[0]["param"] == {"a": 1}
    expected_ms = int(datetime(2026, 10, 14, tzinfo=timezone.utc).timestamp() * 1000)
    assert rows[0]["createdAt"] == expected_ms
    target = unquote(captured["url"])
    assert "/v1/rdb/rest/feature_jobs" in target
    assert 'openid=eq."user-1"' in target
    assert "order=created_at.desc" in target
    assert captured["auth"] == "Bearer test-key"


def test_count_reads_content_range(monkeypatch):
    def fake_urlopen(request, timeout=30):
        assert request.get_header("Prefer") == "count=exact"
        return _Response(b"[]", {"Content-Range": "*/4"})

    monkeypatch.setattr("app.db.http_api.urlopen", fake_urlopen)
    assert HttpDatabase(env_id="env", apikey="test-key").count_documents("users", {"openid": "u"}) == 4


def test_rpc_business_error_becomes_value_error(monkeypatch):
    def fake_urlopen(request, timeout=30):
        payload = json.dumps({"code": "P0001", "message": "积分不足，请先获取积分"}).encode()
        raise HTTPError(request.full_url, 400, "Bad Request", EmailMessage(), BytesIO(payload))

    monkeypatch.setattr("app.db.http_api.urlopen", fake_urlopen)
    with pytest.raises(ValueError, match="积分不足"):
        HttpDatabase(env_id="env", apikey="test-key").call(
            "wantuju_create_pending_job",
            {"task": {"openid": "u"}, "amount": 1},
        )


def test_unknown_rpc_is_rejected_locally():
    with pytest.raises(DatabaseError, match="未知数据库函数"):
        HttpDatabase(env_id="env", apikey="test-key").call("drop_database", {})


def test_exec_pgsql_posts_sql_and_role(monkeypatch):
    captured: dict = {}

    def fake_urlopen(request, timeout=30):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode())
        captured["auth"] = request.get_header("Authorization")
        return _Response(b"[]", {})

    monkeypatch.setattr("app.db.http_api.urlopen", fake_urlopen)
    assert execute_admin_sql("SELECT 1", role="cloudbase_postgres") == []
    assert captured["body"] == {"sql": "SELECT 1", "role": "cloudbase_postgres"}
    assert "/v1/rdb/exec-pgsql" in captured["url"]
    assert "role=cloudbase_postgres" in captured["url"]
    assert captured["auth"] == "Bearer test-key"


def test_http_migration_skips_files_already_recorded(monkeypatch):
    from app.db import migrate

    calls: list[str] = []
    files = sorted(path.name for path in migrate.MIGRATIONS_DIR.glob("*.sql"))

    def fake_execute(statement: str, *, role: str = "cloudbase_postgres", timeout: int = 60):
        calls.append(statement.strip().splitlines()[0])
        assert role == "cloudbase_postgres"
        if statement.strip().upper().startswith("SELECT"):
            return [{"version": name} for name in files]
        return []

    monkeypatch.setattr("app.db.http_api.execute_admin_sql", fake_execute)
    assert migrate._apply_http() == []
    assert any("schema_migrations" in call for call in calls)
    assert any(call.upper().startswith("SELECT") for call in calls)
    assert not any(call.upper().startswith("INSERT") for call in calls)
