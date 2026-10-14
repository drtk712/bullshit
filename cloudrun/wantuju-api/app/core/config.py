"""Runtime configuration for the Wantuju CloudRun service."""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True)
class Settings:
    cloudbase_env_id: str | None = os.getenv("CLOUDBASE_ENV_ID")
    cloudbase_apikey: str | None = os.getenv("CLOUDBASE_APIKEY")
    memefast_api_key: str = os.getenv("MEMEFAST_API_KEY", "")
    memefast_api_url: str = os.getenv("MEMEFAST_API_URL", "https://memefast.top/v1/chat/completions")
    memefast_model: str = os.getenv("MEMEFAST_MODEL", "gpt-image-2-all")
    run_env: str = os.getenv("TENCENTCLOUD_RUNENV", "")


settings = Settings()


def validation_api_key() -> str:
    """Bearer token for a future OpenAI-compatible validation model. Empty disables the header."""
    return os.getenv("VALIDATION_API_KEY", "").strip()


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
