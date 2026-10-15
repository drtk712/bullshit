"""Process-wide PostgreSQL connection pool."""
from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import database_dsn
from app.db.errors import DatabaseError


_pool: ConnectionPool | None = None
_lock = threading.Lock()
_SESSION_OPTIONS = (
    "-c search_path=public -c lock_timeout=5s -c statement_timeout=30s "
    "-c idle_in_transaction_session_timeout=30s"
)


def get_pool() -> ConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            try:
                dsn = database_dsn()
            except ValueError as exc:
                raise DatabaseError(str(exc)) from exc
            if not dsn:
                raise DatabaseError(
                    "PostgreSQL 未配置：设置 DATABASE_URL，或 PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE"
                )
            try:
                _pool = ConnectionPool(
                    conninfo=dsn,
                    min_size=int(os.getenv("DB_POOL_MIN", "1")),
                    max_size=int(os.getenv("DB_POOL_MAX", "5")),
                    timeout=float(os.getenv("DB_POOL_TIMEOUT", "10")),
                    kwargs={"row_factory": dict_row, "connect_timeout": 5, "options": _SESSION_OPTIONS},
                    open=True,
                )
            except Exception as exc:
                _pool = None
                raise DatabaseError(f"PostgreSQL 连接失败: {exc}") from exc
        return _pool


def close_pool() -> None:
    global _pool
    with _lock:
        pool = _pool
        _pool = None
    if pool is not None:
        pool.close()


@contextmanager
def connection() -> Iterator:
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)
