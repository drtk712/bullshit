"""Feature, user, job, and points operations on PostgreSQL."""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

from app.db.repository import Database, row_to_doc
from app.db.schema import (
    FEATURE_CONFIG_COLLECTION,
    FEATURE_JOBS_COLLECTION,
    POINT_TRANSACTIONS_COLLECTION,
    USERS_COLLECTION,
)


def _now_ms() -> int:
    return int(time.time() * 1000)


class PosterJobStore:
    collection = FEATURE_JOBS_COLLECTION

    def __init__(self, db: Database | None = None):
        self.db = db or get_database()

    def get_job(self, task_id: str) -> dict[str, Any]:
        return self.db.get_document(self.collection, task_id)

    def update_job(self, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        patch = {**data, "updatedAt": _now_ms()}
        return self.db.update_document(self.collection, task_id, patch)


class PointLedger:
    users_collection = USERS_COLLECTION
    transactions_collection = POINT_TRANSACTIONS_COLLECTION

    def __init__(self, db: Database | None = None):
        self.db = db or get_database()

    def create_pending_job(self, task_doc: dict[str, Any], amount: int = 1) -> tuple[str, dict[str, Any]]:
        row = self.db.call("wantuju_create_pending_job", {"task": dict(task_doc), "amount": amount})
        if not row:
            raise ValueError("创建任务失败")
        task = row_to_doc(FEATURE_JOBS_COLLECTION, row)
        task_id = str(task.get("_id") or "")
        if not task_id:
            raise ValueError("创建任务失败")
        return task_id, task

    def consume_existing_job(self, task_id: str, amount: int = 1) -> dict[str, Any]:
        row = self.db.call("wantuju_consume_existing_job", {"task_id": task_id, "amount": amount})
        if not row:
            raise ValueError("任务不存在")
        return row_to_doc(FEATURE_JOBS_COLLECTION, row)

    def refund_failed_job(self, task_id: str, err_msg: str, amount: int = 1) -> None:
        self.db.call(
            "wantuju_refund_failed_job",
            {"task_id": task_id, "err_msg": err_msg, "amount": amount},
        )


class FeatureConfigStore:
    collection = FEATURE_CONFIG_COLLECTION

    def __init__(self, db: Database | None = None):
        self.db = db or get_database()

    def list_features(self) -> list[dict[str, Any]]:
        docs = self.db.list_documents(self.collection, limit=200)
        return sorted(docs, key=lambda doc: (int(doc.get("order", 0) or 0), str(doc.get("_id", ""))))

    def get_feature(self, doc_id: str) -> dict[str, Any]:
        document = self.db.get_document(self.collection, doc_id)
        if not document:
            from app.db.errors import DatabaseError

            raise DatabaseError("玩法不存在")
        return document

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

    def __init__(self, db: Database | None = None):
        self.db = db or get_database()

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
            sort={"lastLoginAt": -1},
            limit=limit,
            skip=offset,
        )
        total = self.db.count_documents(self.users_collection, filter_query)
        return items, total

    def get_user(self, user_id: str) -> dict[str, Any]:
        from app.db.errors import DatabaseError

        user = self.db.get_document(self.users_collection, user_id)
        if not user:
            raise DatabaseError("用户不存在")
        return user

    def block_user(self, user_id: str, reason: str = "", operator: str = "admin") -> dict[str, Any]:
        now = _now_ms()
        return self.db.update_document(
            self.users_collection,
            user_id,
            {
                "status": "blocked",
                "blockedAt": now,
                "blockedReason": reason,
                "blockedBy": operator,
                "updatedAt": now,
            },
        )

    def unblock_user(self, user_id: str, operator: str = "admin") -> dict[str, Any]:
        now = _now_ms()
        return self.db.update_document(
            self.users_collection,
            user_id,
            {
                "status": "active",
                "unblockedAt": now,
                "unblockedBy": operator,
                "blockedReason": "",
                "updatedAt": now,
            },
        )

    def delete_user(self, user_id: str) -> dict[str, Any]:
        result = self.db.call("wantuju_delete_user", {"user_id": user_id}) or {}
        return {
            "userId": str(result.get("userId") or user_id),
            "openid": str(result.get("openid") or ""),
            "transactionsDeleted": int(result.get("transactionsDeleted") or 0),
            "jobsDeleted": int(result.get("jobsDeleted") or 0),
        }

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self.db.get_document(self.jobs_collection, task_id)

    def delete_task(self, task_id: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if str(task.get("status") or "") in {"pending", "processing"}:
            raise ValueError("进行中的任务不能删除")
        self.db.delete_document(self.jobs_collection, task_id)
        return task

    def adjust_points(self, user_id: str, amount: int, reason: str, operator: str = "admin") -> dict[str, Any]:
        return self.db.call(
            "wantuju_adjust_points",
            {
                "user_id": user_id,
                "amount": amount,
                "reason": reason,
                "operator": operator,
                "now": _now_ms(),
            },
        ) or {}

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
            sort={"createdAt": -1},
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
            if not task:
                return [], 0
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

        filter_query: dict[str, Any] = {
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
            sort={"createdAt": -1},
            limit=limit,
            skip=offset,
        )
        total = self.db.count_documents(self.jobs_collection, filter_query)
        return items, total

    def dashboard(self, active_limit: int = 12) -> dict[str, Any]:
        task_statuses = ("pending", "processing", "completed", "failed")
        task_counts = {
            status: self.db.count_documents(self.jobs_collection, {"status": status})
            for status in task_statuses
        }
        active_tasks = self.db.find_many(
            self.jobs_collection,
            {"status": {"$in": ["pending", "processing"]}},
            sort={"updatedAt": 1},
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
def get_database() -> Database:
    return Database()


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
