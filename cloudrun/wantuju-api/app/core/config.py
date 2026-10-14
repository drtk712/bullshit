"""Runtime configuration for the Wantuju CloudRun service."""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True)
class Settings:
    cloudbase_env_id: str | None = os.getenv("CLOUDBASE_ENV_ID")
    cloudbase_apikey: str | None = os.getenv("CLOUDBASE_APIKEY")
    run_env: str = os.getenv("TENCENTCLOUD_RUNENV", "")


settings = Settings()


DEFAULT_IMAGE_API_BASE_URL = "https://aigw.telecomjs.com/v1"
DEFAULT_IMAGE_MODEL = "orb_base_02_vis"


def image_api_base_url() -> str:
    """OpenAI-compatible images API origin, without a trailing slash or images path."""
    raw = os.getenv("IMAGE_API_BASE_URL", DEFAULT_IMAGE_API_BASE_URL).strip().rstrip("/")
    for suffix in ("/images/generations", "/images/edits"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
    return raw or DEFAULT_IMAGE_API_BASE_URL


def image_api_key() -> str:
    return os.getenv("IMAGE_API_KEY", "").strip()


def image_model() -> str:
    return os.getenv("IMAGE_MODEL", DEFAULT_IMAGE_MODEL).strip() or DEFAULT_IMAGE_MODEL


def validation_api_key() -> str:
    """Bearer token for a future OpenAI-compatible validation model. Empty disables the header."""
    return os.getenv("VALIDATION_API_KEY", "").strip()


def use_postgres() -> bool:
    """True when a direct PostgreSQL connection is configured.

    `PGSSLMODE` alone does not count: tests set it while the HTTP path is selected
    by deleting `DATABASE_URL`. A partial `PG*` set still counts so `database_dsn`
    can report the missing pieces.
    """
    if os.getenv("DATABASE_URL", "").strip():
        return True
    return any(
        os.getenv(name, "").strip()
        for name in ("PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGPORT")
    )


def data_backend() -> str:
    """`postgres` for the psycopg fallback, `http` for the CloudBase PostgREST default."""
    if use_postgres():
        return "postgres"
    env_id = os.getenv("CLOUDBASE_ENV_ID", "").strip()
    apikey = os.getenv("CLOUDBASE_APIKEY", "").strip()
    if env_id and apikey:
        return "http"
    return ""


def database_dsn() -> str:
    """Libpq connection string from DATABASE_URL or PG* variables.

    Read on each call so the process environment can be set before the first
    connection. An empty string means PostgreSQL is not configured.
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url

    host = os.getenv("PGHOST", "").strip()
    user = os.getenv("PGUSER", "").strip()
    dbname = os.getenv("PGDATABASE", "").strip()
    password = os.getenv("PGPASSWORD", "")
    port = os.getenv("PGPORT", "").strip()
    sslmode = os.getenv("PGSSLMODE", "").strip()
    if not any((host, user, dbname, password, port, sslmode)):
        return ""
    if not (host and user and dbname):
        raise ValueError("PostgreSQL 配置不完整：设置 DATABASE_URL，或同时设置 PGHOST、PGUSER、PGDATABASE")
    port = port or "5432"
    sslmode = sslmode or "require"
    return (
        f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}"
        f"@{host}:{port}/{quote(dbname, safe='')}?sslmode={quote(sslmode, safe='')}"
    )
