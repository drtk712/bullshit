"""Document-shaped CRUD on the known PostgreSQL tables."""
from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from app.db.errors import DatabaseError
from app.db.pool import get_pool
from app.db.schema import TABLES, Column, Table


def created_id(result: dict[str, Any]) -> str | None:
    for key in ("_id", "id"):
        value = result.get(key)
        if value:
            return str(value)
    for key in ("ids", "insertedIds", "inserted_ids"):
        value = result.get(key)
        if isinstance(value, list) and value:
            return str(value[0])
    return None


def _table(name: str) -> Table:
    spec = TABLES.get(name)
    if spec is None:
        raise DatabaseError(f"未知数据表: {name}")
    return spec


def _to_millis(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = value - epoch
    return (delta.days * 86_400 + delta.seconds) * 1000 + delta.microseconds // 1000


def _from_millis(value: int) -> datetime:
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=int(value))


def adapt_write(column: Column, value: Any) -> Any:
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
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return _from_millis(int(value))
    if column.kind == "date":
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))
    if column.kind == "jsonb":
        return Jsonb(value)
    raise DatabaseError(f"未知字段类型: {column.kind}")


def adapt_read(column: Column, value: Any) -> Any:
    if value is None:
        return None
    if column.kind == "ts":
        return _to_millis(value)
    if column.kind == "date":
        return value.isoformat()
    if column.kind == "jsonb" and isinstance(value, str):
        return json.loads(value)
    if column.kind == "int" and not isinstance(value, bool):
        return int(value)
    return value


def row_to_doc(table: str, row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    spec = _table(table)
    return {column.field: adapt_read(column, row.get(column.name)) for column in spec.columns}


def _text_array_literal(values: list[str]) -> str:
    parts = []
    for value in values:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        parts.append(f'"{escaped}"')
    return "{" + ",".join(parts) + "}"


def _sort_desc(value: Any) -> bool:
    if isinstance(value, dict):
        raw = value.get("$numberInt", value.get("$numberLong", value.get("$numberDouble", -1)))
        return int(raw) < 0
    return int(value) < 0


def _field_clause(spec: Table, field: str, value: Any) -> tuple[sql.Composable, list[Any]]:
    column = spec.by_field.get(field)
    if column is None:
        raise DatabaseError(f"不支持的查询字段: {spec.name}.{field}")
    identifier = sql.Identifier(column.name)
    if isinstance(value, dict):
        if "$in" in value:
            return sql.SQL("{} = ANY(%s)").format(identifier), [list(value["$in"])]
        if "$lt" in value:
            return sql.SQL("{} < %s").format(identifier), [adapt_write(column, value["$lt"])]
        if "$lte" in value:
            return sql.SQL("{} <= %s").format(identifier), [adapt_write(column, value["$lte"])]
        if "$gt" in value:
            return sql.SQL("{} > %s").format(identifier), [adapt_write(column, value["$gt"])]
        if "$gte" in value:
            return sql.SQL("{} >= %s").format(identifier), [adapt_write(column, value["$gte"])]
        raise DatabaseError(f"不支持的查询条件: {spec.name}.{field}")
    if value is None:
        return sql.SQL("{} IS NULL").format(identifier), []
    return sql.SQL("{} = %s").format(identifier), [adapt_write(column, value)]


def _where(spec: Table, filt: dict[str, Any] | None) -> tuple[sql.Composable, list[Any]]:
    if not filt:
        return sql.SQL("TRUE"), []
    parts: list[sql.Composable] = []
    params: list[Any] = []
    for key, value in filt.items():
        if key == "$or":
            or_parts: list[sql.Composable] = []
            for item in value:
                clause, clause_params = _where(spec, item)
                or_parts.append(sql.SQL("({})").format(clause))
                params.extend(clause_params)
            if not or_parts:
                parts.append(sql.SQL("FALSE"))
            else:
                parts.append(sql.SQL("({})").format(sql.SQL(" OR ").join(or_parts)))
            continue
        if key == "$and":
            and_parts: list[sql.Composable] = []
            for item in value:
                clause, clause_params = _where(spec, item)
                and_parts.append(sql.SQL("({})").format(clause))
                params.extend(clause_params)
            parts.append(sql.SQL("({})").format(sql.SQL(" AND ").join(and_parts) if and_parts else sql.SQL("TRUE")))
            continue
        clause, clause_params = _field_clause(spec, key, value)
        parts.append(clause)
        params.extend(clause_params)
    if not parts:
        return sql.SQL("TRUE"), []
    return sql.SQL(" AND ").join(parts), params


def _order_by(spec: Table, sort: dict[str, Any] | None) -> sql.Composable:
    if not sort:
        return sql.SQL("")
    pieces: list[sql.Composable] = []
    for field, direction in sort.items():
        column = spec.by_field.get(field)
        if column is None:
            raise DatabaseError(f"不支持的排序字段: {spec.name}.{field}")
        direction_sql = sql.SQL("DESC") if _sort_desc(direction) else sql.SQL("ASC")
        pieces.append(sql.SQL("{} {}").format(sql.Identifier(column.name), direction_sql))
    return sql.SQL(" ORDER BY ") + sql.SQL(", ").join(pieces)


class Transaction:
    def __init__(self) -> None:
        self.conn = None

    def __enter__(self) -> Transaction:
        try:
            self.conn = get_pool().getconn()
        except DatabaseError:
            raise
        except Exception as exc:
            raise DatabaseError(f"PostgreSQL 连接失败: {exc}") from exc
        self.conn.autocommit = False
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if self.conn is None:
                return False
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            if self.conn is not None:
                get_pool().putconn(self.conn)
                self.conn = None
        return False

    def _execute(self, query: sql.Composable | str, params: list[Any] | tuple[Any, ...] = ()):
        try:
            return self.conn.execute(query, params)
        except psycopg.Error as exc:
            raise DatabaseError(f"PostgreSQL 请求失败: {exc}") from exc

    def get_document(self, table: str, doc_id: str, *, lock: bool = False) -> dict[str, Any]:
        return self.find_one(table, {"_id": doc_id}, lock=lock) or {}

    def find_one(self, table: str, filt: dict[str, Any], *, lock: bool = False) -> dict[str, Any] | None:
        rows = self.find_many(table, filt, limit=1, lock=lock)
        return rows[0] if rows else None

    def find_many(
        self,
        table: str,
        filt: dict[str, Any] | None = None,
        *,
        sort: dict[str, Any] | None = None,
        limit: int = 50,
        skip: int = 0,
        lock: bool = False,
    ) -> list[dict[str, Any]]:
        spec = _table(table)
        where, params = _where(spec, filt)
        query = sql.SQL("SELECT * FROM {} WHERE {}{} LIMIT %s OFFSET %s{}").format(
            sql.Identifier(spec.name),
            where,
            _order_by(spec, sort),
            sql.SQL(" FOR UPDATE") if lock else sql.SQL(""),
        )
        params.extend([int(limit), int(skip)])
        rows = self._execute(query, params).fetchall()
        return [row_to_doc(table, row) for row in rows]

    def count_documents(self, table: str, filt: dict[str, Any] | None = None) -> int:
        spec = _table(table)
        where, params = _where(spec, filt)
        query = sql.SQL("SELECT count(*)::int AS n FROM {} WHERE {}").format(sql.Identifier(spec.name), where)
        row = self._execute(query, params).fetchone()
        return int(row["n"] if row else 0)

    def insert_documents(self, table: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
        ids = [self._insert_one(table, document) for document in documents]
        return {"ids": ids, "_id": ids[0] if ids else None}

    def _insert_one(self, table: str, document: dict[str, Any]) -> str:
        spec = _table(table)
        columns: list[sql.Composable] = []
        placeholders: list[sql.Composable] = []
        params: list[Any] = []
        for field, value in document.items():
            if field == "_id" and not value:
                continue
            column = spec.by_field.get(field)
            if column is None:
                raise DatabaseError(f"不支持的写入字段: {spec.name}.{field}")
            columns.append(sql.Identifier(column.name))
            placeholders.append(sql.SQL("%s"))
            params.append(adapt_write(column, value))
        if columns:
            query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(
                sql.Identifier(spec.name),
                sql.SQL(", ").join(columns),
                sql.SQL(", ").join(placeholders),
            )
        else:
            query = sql.SQL("INSERT INTO {} DEFAULT VALUES RETURNING *").format(sql.Identifier(spec.name))
        row = self._execute(query, params).fetchone()
        return str(row_to_doc(table, row)["_id"])

    def update_document(self, table: str, doc_id: str, data: dict[str, Any]) -> dict[str, Any]:
        spec = _table(table)
        assignments: list[sql.Composable] = []
        params: list[Any] = []
        flat_fields: set[str] = set()
        nested: dict[str, list[tuple[list[str], Any]]] = {}
        for key, value in data.items():
            if "." in key:
                head, *rest = key.split(".")
                column = spec.by_field.get(head)
                if column is None or column.kind != "jsonb" or not rest:
                    raise DatabaseError(f"不支持的字段路径: {spec.name}.{key}")
                if head in flat_fields:
                    raise DatabaseError(f"不能同时替换和修改嵌套字段: {spec.name}.{head}")
                nested.setdefault(column.name, []).append((rest, value))
                continue
            column = spec.by_field.get(key)
            if column is None:
                raise DatabaseError(f"不支持的写入字段: {spec.name}.{key}")
            if column.name in nested:
                raise DatabaseError(f"不能同时替换和修改嵌套字段: {spec.name}.{key}")
            flat_fields.add(key)
            assignments.append(sql.SQL("{} = %s").format(sql.Identifier(column.name)))
            params.append(adapt_write(column, value))
        for column_name, updates in nested.items():
            expression: sql.Composable = sql.SQL("COALESCE({column}, '{{}}'::jsonb)").format(
                column=sql.Identifier(column_name)
            )
            for path, value in updates:
                expression = sql.SQL("jsonb_set({}, %s::text[], %s::jsonb, true)").format(expression)
                params.append(_text_array_literal(path))
                params.append(Jsonb(value))
            assignments.append(sql.SQL("{} = {}").format(sql.Identifier(column_name), expression))
        if "updatedAt" in spec.by_field and "updatedAt" not in flat_fields:
            assignments.append(sql.SQL("{} = now()").format(sql.Identifier(spec.by_field["updatedAt"].name)))
        if not assignments:
            raise DatabaseError("更新内容为空")
        params.append(doc_id)
        query = sql.SQL("UPDATE {} SET {} WHERE id = %s RETURNING *").format(
            sql.Identifier(spec.name),
            sql.SQL(", ").join(assignments),
        )
        row = self._execute(query, params).fetchone()
        if not row:
            raise DatabaseError("文档不存在")
        return row_to_doc(table, row)

    def delete_document(self, table: str, doc_id: str) -> dict[str, Any]:
        deleted = self.delete_where(table, {"_id": doc_id})
        if not deleted:
            raise DatabaseError("文档不存在")
        return {"deleted": deleted}

    def delete_where(self, table: str, filt: dict[str, Any]) -> int:
        spec = _table(table)
        where, params = _where(spec, filt)
        query = sql.SQL("DELETE FROM {} WHERE {}").format(sql.Identifier(spec.name), where)
        cursor = self._execute(query, params)
        return int(cursor.rowcount or 0)

    def list_documents(self, table: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        return self.find_many(table, {}, limit=limit, skip=offset)


class Database:
    @contextmanager
    def transaction(self) -> Iterator[Transaction]:
        with Transaction() as tx:
            yield tx

    def get_document(self, table: str, doc_id: str) -> dict[str, Any]:
        with self.transaction() as tx:
            return tx.get_document(table, doc_id)

    def find_one(self, table: str, filt: dict[str, Any]) -> dict[str, Any] | None:
        with self.transaction() as tx:
            return tx.find_one(table, filt)

    def find_many(
        self,
        table: str,
        filt: dict[str, Any] | None = None,
        *,
        sort: dict[str, Any] | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        with self.transaction() as tx:
            return tx.find_many(table, filt, sort=sort, limit=limit, skip=skip)

    def count_documents(self, table: str, filt: dict[str, Any] | None = None) -> int:
        with self.transaction() as tx:
            return tx.count_documents(table, filt)

    def insert_documents(self, table: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
        with self.transaction() as tx:
            return tx.insert_documents(table, documents)

    def update_document(self, table: str, doc_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self.transaction() as tx:
            return tx.update_document(table, doc_id, data)

    def delete_document(self, table: str, doc_id: str) -> dict[str, Any]:
        with self.transaction() as tx:
            return tx.delete_document(table, doc_id)

    def list_documents(self, table: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self.transaction() as tx:
            return tx.list_documents(table, limit=limit, offset=offset)
