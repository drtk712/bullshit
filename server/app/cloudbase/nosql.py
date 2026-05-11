"""CloudBase NoSQL REST helpers."""
from __future__ import annotations

import os
import time
from functools import lru_cache
from typing import Any
from urllib.parse import quote

from app.cloudbase.client import CloudBaseClient


FEATURE_CONFIG_COLLECTION = "feature_configs"
USERS_COLLECTION = "users"
POINT_TRANSACTIONS_COLLECTION = "point_transactions"
FEATURE_JOBS_COLLECTION = "feature_jobs"


def from_ejson(value: Any) -> Any:
    """Decode the strict EJSON shapes returned by list endpoints."""
    if isinstance(value, list):
        return [from_ejson(item) for item in value]
    if not isinstance(value, dict):
        return value

    if set(value) == {"$numberInt"}:
        return int(value["$numberInt"])
    if set(value) == {"$numberLong"}:
        return int(value["$numberLong"])
    if set(value) == {"$numberDouble"}:
        raw = value["$numberDouble"]
        number = float(raw)
        return int(number) if number.is_integer() else number
    if set(value) == {"$date"}:
        date_value = value["$date"]
        if isinstance(date_value, dict) and "$numberLong" in date_value:
            return int(date_value["$numberLong"])
        return date_value

    return {key: from_ejson(item) for key, item in value.items()}


class CloudBaseNoSQL:
    def __init__(
        self,
        client: CloudBaseClient | None = None,
        instance: str | None = None,
        database: str | None = None,
    ):
        self.client = client or CloudBaseClient()
        self.instance = instance or os.getenv("CLOUDBASE_DB_INSTANCE", "flexdb")
        self.database = database or os.getenv("CLOUDBASE_DB_NAME", "tnt-gizs5ya5s")
        self.command_instance = os.getenv("CLOUDBASE_COMMAND_DB_INSTANCE", "(default)")
        self.command_database = os.getenv("CLOUDBASE_COMMAND_DB_NAME", "(default)")

    @property
    def base_path(self) -> str:
        instance = quote(self.instance, safe="()")
        database = quote(self.database, safe="()")
        return f"/v1/database/instances/{instance}/databases/{database}"

    @property
    def command_base_path(self) -> str:
        instance = quote(self.command_instance, safe="()")
        database = quote(self.command_database, safe="()")
        return f"/v1/database/instances/{instance}/databases/{database}"

    def _collection_path(self, collection: str) -> str:
        return f"{self.base_path}/collections/{quote(collection, safe='')}/documents"

    def begin_transaction(self) -> str:
        response = self.client.request("POST", f"{self.command_base_path}/transactions", json={})
        if isinstance(response, dict):
            for key in ("transactionId", "id"):
                value = response.get(key)
                if value:
                    return str(value)
            data = response.get("data")
            if isinstance(data, dict):
                for key in ("transactionId", "id"):
                    value = data.get(key)
                    if value:
                        return str(value)
        raise RuntimeError("开启数据库事务失败：未返回 transactionId")

    def commit_transaction(self, transaction_id: str) -> Any:
        return self.client.request("POST", f"{self.command_base_path}/transactions/{quote(transaction_id, safe='')}/commit", json={})

    def rollback_transaction(self, transaction_id: str) -> Any:
        return self.client.request("POST", f"{self.command_base_path}/transactions/{quote(transaction_id, safe='')}/rollback", json={})

    def run_commands(self, commands: list[dict[str, Any]], transaction_id: str | None = None) -> list[Any]:
        body: dict[str, Any] = {"commands": commands}
        if transaction_id:
            body["transactionId"] = transaction_id
        response = self.client.request("POST", f"{self.command_base_path}/commands", json=body)
        if isinstance(response, dict):
            for key in ("results", "data", "list"):
                value = response.get(key)
                if isinstance(value, list):
                    return [from_ejson(item) for item in value]
        if isinstance(response, list):
            return [from_ejson(item) for item in response]
        return []

    def _first_batch(self, result: Any) -> list[dict[str, Any]]:
        if isinstance(result, dict) and isinstance(result.get("cursor"), dict):
            batch = result["cursor"].get("firstBatch")
            if isinstance(batch, list):
                return [item for item in batch if isinstance(item, dict)]
        if isinstance(result, list):
            if len(result) == 1 and isinstance(result[0], dict) and isinstance(result[0].get("cursor"), dict):
                return self._first_batch(result[0])
            return [item for item in result if isinstance(item, dict)]
        if isinstance(result, dict) and result.get("_id"):
            return [result]
        return []

    def list_documents(self, collection: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        response = self.client.request(
            "GET",
            self._collection_path(collection),
            params={"limit": limit, "offset": offset},
        )
        return from_ejson(response.get("list", []))

    def find_many(
        self,
        collection: str,
        filter_query: dict[str, Any] | None = None,
        *,
        sort: dict[str, Any] | None = None,
        limit: int = 50,
        skip: int = 0,
        transaction_id: str | None = None,
    ) -> list[dict[str, Any]]:
        command: dict[str, Any] = {
            "find": collection,
            "filter": filter_query or {},
            "limit": {"$numberInt": str(limit)},
            "skip": {"$numberInt": str(skip)},
        }
        if sort:
            command["sort"] = sort
        results = self.run_commands([command], transaction_id=transaction_id)
        return self._first_batch(results[0]) if results else []

    def count_documents(self, collection: str, filter_query: dict[str, Any] | None = None) -> int:
        results = self.run_commands(
            [
                {
                    "count": collection,
                    "query": filter_query or {},
                }
            ]
        )
        if not results:
            return 0
        first = results[0]
        if isinstance(first, list) and first:
            first = first[0]
        if isinstance(first, dict):
            for key in ("n", "count", "total"):
                value = first.get(key)
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.isdigit():
                    return int(value)
                if isinstance(value, dict) and "$numberInt" in value:
                    return int(value["$numberInt"])
                if isinstance(value, dict) and "$numberLong" in value:
                    return int(value["$numberLong"])
        return 0

    def find_one(self, collection: str, filter_query: dict[str, Any], transaction_id: str | None = None) -> dict[str, Any] | None:
        docs = self.find_many(collection, filter_query, limit=1, transaction_id=transaction_id)
        if not docs:
            return None
        return docs[0]

    def get_document(self, collection: str, doc_id: str, transaction_id: str | None = None) -> dict[str, Any]:
        path = f"{self._collection_path(collection)}/{quote(doc_id, safe='')}"
        kwargs: dict[str, Any] = {}
        if transaction_id:
            kwargs["params"] = {"transactionId": transaction_id}
        return from_ejson(self.client.request("GET", path, **kwargs))

    def insert_documents(self, collection: str, documents: list[dict[str, Any]], transaction_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"data": documents}
        if transaction_id:
            body["transactionId"] = transaction_id
        return self.client.request("POST", self._collection_path(collection), json=body)

    def update_document(self, collection: str, doc_id: str, data: dict[str, Any], transaction_id: str | None = None) -> dict[str, Any]:
        path = f"{self._collection_path(collection)}/{quote(doc_id, safe='')}"
        body: dict[str, Any] = {"data": data}
        if transaction_id:
            body["transactionId"] = transaction_id
        return self.client.request("PATCH", path, json=body)

    def delete_document(self, collection: str, doc_id: str) -> dict[str, Any]:
        path = f"{self._collection_path(collection)}/{quote(doc_id, safe='')}"
        return self.client.request("DELETE", path)


class PosterJobStore:
    collection = FEATURE_JOBS_COLLECTION

    def __init__(self, db: CloudBaseNoSQL | None = None):
        self.db = db or CloudBaseNoSQL()

    def get_job(self, task_id: str) -> dict[str, Any]:
        return self.db.get_document(self.collection, task_id)

    def update_job(self, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        patch = {**data, "updatedAt": int(time.time() * 1000)}
        return self.db.update_document(self.collection, task_id, patch)


class PointLedger:
    users_collection = USERS_COLLECTION
    transactions_collection = POINT_TRANSACTIONS_COLLECTION

    def __init__(self, db: CloudBaseNoSQL | None = None):
        self.db = db or CloudBaseNoSQL()

    def _get_user_by_openid_in_transaction(self, openid: str, transaction_id: str) -> dict[str, Any]:
        user = self.db.find_one(self.users_collection, {"openid": openid}, transaction_id=transaction_id)
        if user:
            return user
        raise ValueError("用户不存在")

    def _rollback_safely(self, transaction_id: str) -> None:
        try:
            self.db.rollback_transaction(transaction_id)
        except Exception:
            pass

    def _create_transaction(
        self,
        *,
        openid: str,
        tx_type: str,
        amount: int,
        balance_after: int,
        reason: str,
        task_id: str,
        transaction_id: str | None = None,
    ) -> str | None:
        result = self.db.insert_documents(
            self.transactions_collection,
            [
                {
                    "openid": openid,
                    "type": tx_type,
                    "amount": amount,
                    "balanceAfter": balance_after,
                    "reason": reason,
                    "taskId": task_id,
                    "createdAt": int(time.time() * 1000),
                }
            ],
            transaction_id=transaction_id,
        )
        ids = result.get("ids") or result.get("insertedIds") or result.get("inserted_ids")
        if isinstance(ids, list) and ids:
            return str(ids[0])
        if isinstance(result.get("_id"), str):
            return str(result["_id"])
        return None

    def accept_job(self, task_id: str, amount: int = 1) -> tuple[dict[str, Any], bool]:
        transaction_id = self.db.begin_transaction()
        try:
            task = self.db.get_document(FEATURE_JOBS_COLLECTION, task_id, transaction_id=transaction_id)
            status = str(task.get("status") or "")
            openid = str(task.get("openid") or "")
            skip_points = bool(task.get("skipPointsDeduction"))

            if status in {"pending", "processing", "completed"}:
                self.db.commit_transaction(transaction_id)
                return task, False
            if status != "init":
                raise ValueError(f"任务状态不可接管: {status or 'unknown'}")
            if not openid:
                raise ValueError("任务缺少 openid")

            consume_transaction_id = None
            if not skip_points:
                user = self._get_user_by_openid_in_transaction(openid, transaction_id)
                user_id = str(user.get("_id") or "")
                current_points = int(user.get("points") or 0)
                if current_points < amount:
                    raise ValueError("积分不足，请先获取积分")
                balance_after = current_points - amount
                self.db.update_document(
                    self.users_collection,
                    user_id,
                    {
                        "points": balance_after,
                        "totalUsedPoints": int(user.get("totalUsedPoints") or 0) + amount,
                        "updatedAt": int(time.time() * 1000),
                    },
                    transaction_id=transaction_id,
                )
                consume_transaction_id = self._create_transaction(
                    openid=openid,
                    tx_type="consume",
                    amount=-amount,
                    balance_after=balance_after,
                    reason="create_feature_job",
                    task_id=task_id,
                    transaction_id=transaction_id,
                )

            patch = {
                "status": "pending",
                "errMsg": "",
                "pointsConsumed": not skip_points,
                "pointsRefunded": False,
                "consumeTransactionId": consume_transaction_id,
                "updatedAt": int(time.time() * 1000),
            }
            self.db.update_document(FEATURE_JOBS_COLLECTION, task_id, patch, transaction_id=transaction_id)
            self.db.commit_transaction(transaction_id)
            return {**task, **patch}, True
        except Exception:
            self._rollback_safely(transaction_id)
            raise

    def refund_failed_job(self, task_id: str, err_msg: str, amount: int = 1) -> None:
        transaction_id = self.db.begin_transaction()
        try:
            task = self.db.get_document(FEATURE_JOBS_COLLECTION, task_id, transaction_id=transaction_id)
            refund_transaction_id = task.get("refundTransactionId")
            points_consumed = bool(task.get("pointsConsumed"))
            points_refunded = bool(task.get("pointsRefunded"))

            if points_consumed and not points_refunded:
                openid = str(task.get("openid") or "")
                user = self._get_user_by_openid_in_transaction(openid, transaction_id)
                user_id = str(user.get("_id") or "")
                current_points = int(user.get("points") or 0)
                balance_after = current_points + amount
                self.db.update_document(
                    self.users_collection,
                    user_id,
                    {
                        "points": balance_after,
                        "totalRefundedPoints": int(user.get("totalRefundedPoints") or 0) + amount,
                        "updatedAt": int(time.time() * 1000),
                    },
                    transaction_id=transaction_id,
                )
                refund_transaction_id = self._create_transaction(
                    openid=openid,
                    tx_type="refund",
                    amount=amount,
                    balance_after=balance_after,
                    reason="job_failed_refund",
                    task_id=task_id,
                    transaction_id=transaction_id,
                )
                points_refunded = True

            self.db.update_document(
                FEATURE_JOBS_COLLECTION,
                task_id,
                {
                    "status": "failed",
                    "errMsg": err_msg,
                    "pointsRefunded": points_refunded,
                    "refundTransactionId": refund_transaction_id,
                    "refundErrMsg": "",
                    "updatedAt": int(time.time() * 1000),
                },
                transaction_id=transaction_id,
            )
            self.db.commit_transaction(transaction_id)
        except Exception:
            self._rollback_safely(transaction_id)
            raise


class FeatureConfigStore:
    collection = FEATURE_CONFIG_COLLECTION

    def __init__(self, db: CloudBaseNoSQL | None = None):
        self.db = db or CloudBaseNoSQL()

    def list_features(self) -> list[dict[str, Any]]:
        docs = self.db.list_documents(self.collection)
        return sorted(docs, key=lambda d: (int(d.get("order", 0)), str(d.get("_id", ""))))

    def get_feature(self, doc_id: str) -> dict[str, Any]:
        return self.db.get_document(self.collection, doc_id)

    def create_feature(self, document: dict[str, Any]) -> dict[str, Any]:
        return self.db.insert_documents(self.collection, [document])

    def update_feature(self, doc_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return self.db.update_document(self.collection, doc_id, data)

    def delete_feature(self, doc_id: str) -> dict[str, Any]:
        return self.db.delete_document(self.collection, doc_id)


class UserAdminStore:
    users_collection = USERS_COLLECTION
    transactions_collection = POINT_TRANSACTIONS_COLLECTION
    jobs_collection = FEATURE_JOBS_COLLECTION

    def __init__(self, db: CloudBaseNoSQL | None = None):
        self.db = db or CloudBaseNoSQL()

    def list_users(
        self,
        *,
        openid: str = "",
        nick_name: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        filter_query = {
            key: value
            for key, value in {
                "openid": openid,
                "nickName": nick_name,
            }.items()
            if value
        }
        items = self.db.find_many(
            self.users_collection,
            filter_query,
            sort={"lastLoginAt": {"$numberInt": "-1"}},
            limit=limit,
            skip=offset,
        )
        total = self.db.count_documents(self.users_collection, filter_query)
        return items, total

    def get_user(self, user_id: str) -> dict[str, Any]:
        return self.db.get_document(self.users_collection, user_id)

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self.db.get_document(self.jobs_collection, task_id)

    def adjust_points(
        self,
        user_id: str,
        amount: int,
        reason: str,
        operator: str = "admin",
    ) -> dict[str, Any]:
        user = self.get_user(user_id)
        openid = str(user.get("openid", ""))
        current_points = int(user.get("points") or 0)
        balance_after = current_points + amount
        if balance_after < 0:
            raise ValueError("调整后积分不能小于 0")

        now = int(time.time() * 1000)
        patch: dict[str, Any] = {
            "points": balance_after,
            "updatedAt": now,
        }
        if amount > 0:
            patch["totalGrantedPoints"] = int(user.get("totalGrantedPoints") or 0) + amount
        if amount < 0:
            patch["totalUsedPoints"] = int(user.get("totalUsedPoints") or 0) + abs(amount)

        self.db.update_document(self.users_collection, user_id, patch)
        transaction = {
            "openid": openid,
            "type": "adjust",
            "amount": amount,
            "balanceAfter": balance_after,
            "reason": reason,
            "taskId": None,
            "operator": operator,
            "createdAt": now,
        }
        return self.db.insert_documents(self.transactions_collection, [transaction])

    def list_transactions(
        self,
        openid: str = "",
        reason: str = "",
        tx_type: str = "",
        task_id: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        filter_query = {
            key: value
            for key, value in {
                "openid": openid,
                "reason": reason,
                "type": tx_type,
                "taskId": task_id,
            }.items()
            if value
        }
        items = self.db.find_many(
            self.transactions_collection,
            filter_query,
            sort={"createdAt": {"$numberInt": "-1"}},
            limit=limit,
            skip=offset,
        )
        total = self.db.count_documents(self.transactions_collection, filter_query)
        return items, total

    def list_tasks(
        self,
        openid: str = "",
        status: str = "",
        feature_type: str = "",
        task_id: str = "",
        points_consumed: str = "",
        points_refunded: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        if task_id:
            task = self.get_task(task_id)
            if openid and str(task.get("openid") or "") != openid:
                return [], 0
            if status and str(task.get("status") or "") != status:
                return [], 0
            if feature_type and str(task.get("type") or "") != feature_type:
                return [], 0
            if points_consumed in {"true", "false"} and bool(task.get("pointsConsumed")) != (points_consumed == "true"):
                return [], 0
            if points_refunded in {"true", "false"} and bool(task.get("pointsRefunded")) != (points_refunded == "true"):
                return [], 0
            return [task], 1

        filter_query = {
            key: value
            for key, value in {
                "openid": openid,
                "status": status,
                "type": feature_type,
            }.items()
            if value
        }
        if points_consumed in {"true", "false"}:
            filter_query["pointsConsumed"] = points_consumed == "true"
        if points_refunded in {"true", "false"}:
            filter_query["pointsRefunded"] = points_refunded == "true"
        items = self.db.find_many(
            self.jobs_collection,
            filter_query,
            sort={"createdAt": {"$numberInt": "-1"}},
            limit=limit,
            skip=offset,
        )
        total = self.db.count_documents(self.jobs_collection, filter_query)
        return items, total

    def dashboard(self, active_limit: int = 12) -> dict[str, Any]:
        task_statuses = ("init", "pending", "processing", "completed", "failed")
        task_counts = {
            status: self.db.count_documents(self.jobs_collection, {"status": status})
            for status in task_statuses
        }
        active_tasks = self.db.find_many(
            self.jobs_collection,
            {"status": {"$in": ["init", "pending", "processing"]}},
            sort={"updatedAt": {"$numberInt": "1"}},
            limit=active_limit,
        )
        return {
            "usersTotal": self.db.count_documents(self.users_collection, {}),
            "profileCompleted": self.db.count_documents(self.users_collection, {"profileCompleted": True}),
            "tasksTotal": sum(task_counts.values()),
            "taskCounts": task_counts,
            "activeTasks": active_tasks,
        }


@lru_cache(maxsize=1)
def get_feature_store() -> FeatureConfigStore:
    return FeatureConfigStore()


@lru_cache(maxsize=1)
def get_user_store() -> UserAdminStore:
    return UserAdminStore()


@lru_cache(maxsize=1)
def get_poster_job_store() -> PosterJobStore:
    return PosterJobStore()


@lru_cache(maxsize=1)
def get_point_ledger() -> PointLedger:
    return PointLedger()
