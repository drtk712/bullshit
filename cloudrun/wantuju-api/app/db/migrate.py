"""Apply ordered SQL migrations on startup."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.core.config import data_backend, database_dsn, use_postgres
from app.db.errors import DatabaseError


logger = logging.getLogger(__name__)
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def apply_migrations(dsn: str | None = None) -> list[str]:
    """Apply unapplied *.sql files in filename order. Returns newly applied names.

    A direct DSN uses psycopg. Otherwise the CloudBase HTTP API runs each
    statement through ``POST /v1/rdb/exec-pgsql`` as ``cloudbase_postgres``.
    """
    if dsn:
        return _apply_psycopg(dsn)
    if use_postgres():
        try:
            return _apply_psycopg(database_dsn())
        except ValueError as exc:
            raise DatabaseError(str(exc)) from exc
    if data_backend() == "http":
        return _apply_http()
    raise DatabaseError(
        "数据层未配置：设置 CLOUDBASE_ENV_ID 和 CLOUDBASE_APIKEY，或 DATABASE_URL"
    )


def _apply_psycopg(conninfo: str) -> list[str]:
    """Apply unapplied *.sql files in filename order. Returns newly applied names."""
    if not conninfo:
        raise DatabaseError(
            "PostgreSQL 未配置：设置 DATABASE_URL，或 PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE"
        )

    applied: list[str] = []
    try:
        with psycopg.connect(conninfo, autocommit=False, row_factory=dict_row, connect_timeout=5) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS public.schema_migrations (
                  version text PRIMARY KEY,
                  applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            conn.commit()
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                version = path.name
                existing = conn.execute(
                    "SELECT version FROM public.schema_migrations WHERE version = %s",
                    (version,),
                ).fetchone()
                if existing:
                    continue
                script = path.read_text(encoding="utf-8")
                for statement in split_sql(script):
                    try:
                        conn.execute(statement)
                    except psycopg.Error as exc:
                        conn.rollback()
                        raise DatabaseError(f"迁移 {version} 失败: {exc}\nSQL: {statement[:400]}") from exc
                conn.execute(
                    "INSERT INTO public.schema_migrations (version) VALUES (%s)",
                    (version,),
                )
                conn.commit()
                applied.append(version)
                logger.info("[数据库迁移] 已应用 %s", version)
    except DatabaseError:
        raise
    except psycopg.Error as exc:
        raise DatabaseError(f"PostgreSQL 迁移失败: {exc}") from exc
    return applied


def _ddl_hint(statement: str) -> str:
    head = statement.lstrip().upper()
    if head.startswith(("CREATE", "ALTER", "DROP", "GRANT", "REVOKE", "DO", "NOTIFY")):
        return (
            " 若 cloudbase_postgres 不能执行这段 DDL，请在控制台 SQL 编辑器"
            "（角色 cloudbase_admin）按文件名顺序执行 app/db/migrations/*.sql。"
            " 见 https://docs.cloudbase.net/http-api/pgdb/exec-pgsql 和"
            " https://docs.cloudbase.net/en/authentication-v2/auth/auth-pg"
        )
    return ""


def _migration_versions(rows: list[Any]) -> set[str]:
    found: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            version = row.get("version") or row.get("Version")
            if version:
                found.add(str(version))
        elif isinstance(row, str):
            found.add(row)
    return found


def _apply_http() -> list[str]:
    from app.db.http_api import execute_admin_sql

    applied: list[str] = []
    execute_admin_sql(
        """
        CREATE TABLE IF NOT EXISTS public.schema_migrations (
          version text PRIMARY KEY,
          applied_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        role="cloudbase_postgres",
    )
    existing = _migration_versions(
        execute_admin_sql("SELECT version FROM public.schema_migrations", role="cloudbase_postgres")
    )
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.name
        if version in existing:
            continue
        for statement in split_sql(path.read_text(encoding="utf-8")):
            try:
                execute_admin_sql(statement, role="cloudbase_postgres")
            except DatabaseError as exc:
                raise DatabaseError(f"迁移 {version} 失败: {exc}{_ddl_hint(statement)}") from exc
        safe_version = version.replace("'", "''")
        execute_admin_sql(
            f"INSERT INTO public.schema_migrations (version) VALUES ('{safe_version}')",
            role="cloudbase_postgres",
        )
        applied.append(version)
        logger.info("[数据库迁移] 已应用 %s", version)
    return applied


def split_sql(script: str) -> list[str]:
    """Split a SQL script on semicolons, keeping dollar-quoted bodies intact."""
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    length = len(script)
    dollar: str | None = None
    in_single = False
    while i < length:
        if dollar is not None:
            if script.startswith(dollar, i):
                buf.append(dollar)
                i += len(dollar)
                dollar = None
                continue
            buf.append(script[i])
            i += 1
            continue
        if in_single:
            buf.append(script[i])
            if script[i] == "'":
                if i + 1 < length and script[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_single = False
            i += 1
            continue
        if script.startswith("--", i):
            newline = script.find("\n", i)
            if newline == -1:
                break
            i = newline + 1
            continue
        ch = script[i]
        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue
        if ch == "$":
            match = re.match(r"\$[A-Za-z0-9_]*\$", script[i:])
            if match:
                dollar = match.group(0)
                buf.append(dollar)
                i += len(dollar)
                continue
        if ch == ";":
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


if __name__ == "__main__":
    versions = apply_migrations()
    if versions:
        print("applied", ", ".join(versions))
    else:
        print("schema already current")
