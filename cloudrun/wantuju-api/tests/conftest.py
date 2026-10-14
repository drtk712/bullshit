"""Local PostgreSQL fixtures. Refuses non-local databases."""
from __future__ import annotations

import os
from urllib.parse import urlparse

import pytest


def _local_test_url() -> str:
    url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://wantuju:wantuju@127.0.0.1:5432/wantuju?sslmode=disable",
    )
    parsed = urlparse(url)
    host = parsed.hostname or ""
    dbname = parsed.path.lstrip("/").split("?")[0]
    if host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError(f"Refusing to run tests against non-local database host {host!r}")
    if dbname.startswith("postgres-"):
        raise RuntimeError("Refusing to run tests against a CloudBase database name")
    return url


os.environ["DATABASE_URL"] = _local_test_url()
os.environ.setdefault("CLOUDBASE_ENV_ID", "test-env")
os.environ.setdefault("CLOUDBASE_APIKEY", "test-key")
os.environ["PGSSLMODE"] = "disable"


@pytest.fixture(scope="session")
def migrated():
    from app.db.migrate import apply_migrations
    from app.db.pool import close_pool

    close_pool()
    apply_migrations()
    yield
    close_pool()


@pytest.fixture(autouse=True)
def clean_tables(migrated):
    from app.db.pool import connection

    with connection() as conn:
        conn.execute(
            "TRUNCATE TABLE public.users, public.point_transactions, public.feature_jobs, public.feature_configs"
        )


@pytest.fixture
def db(migrated):
    from app.db import Database

    return Database()
