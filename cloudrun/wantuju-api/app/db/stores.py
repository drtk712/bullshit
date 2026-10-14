"""Feature, user, job, and points operations on PostgreSQL."""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

from app.db.repository import Database
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

    def _lock_user(self, tx, openid: str) -> dict[str, Any]:
        user = tx.find_one(self.users_collection, {"openid": openid}, lock=True)
        if not user:
            raise ValueError("用户不存在")
        return user

    def _insert_transaction(
        self,
        tx,
        *,
        openid: str,
        tx_type: str,
        amount: int,
        balance_after: int,
        reason: str,
        task_id: str | None,
        operator: str | None = None,
        now: int | None = None,
    ) -> str | None:
        document: dict[str, Any] = {
            "openid": openid,
            "type": tx_type,
            "amount": amount,
            "balanceAfter": balance_after,
            "reason": reason,
            "taskId": task_id,
            "createdAt": now if now is not None else _now_ms(),
        }
        if operator is not None:
            document["operator"] = operator
        result = tx.insert_documents(self.transactions_collection, [document])
        ids = result.get("ids") or []
        return str(ids[0]) if ids else None

    def create_pending_job(self, task_doc: dict[str, Any], amount: int = 1) -> tuple[str, dict[str, Any]]:
        with self.db.transaction() as tx:
            task = dict(task_doc)
            openid = str(task.get("openid") or "")
            if not openid:
                raise ValueError("任务缺少 openid")

            user = self._lock_user(tx, openid)
            user_id = str(user.get("_id") or "")
            current_points = int(user.get("points") or 0)
            if current_points < amount:
                raise ValueError("积分不足，请先获取积分")
            balance_after = current_points - amount
            now = _now_ms()
            tx.update_document(
                self.users_collection,
                user_id,
                {
                    "points": balance_after,
                    "totalUsedPoints": int(user.get("totalUsedPoints") or 0) + amount,
                    "updatedAt": now,
                },
            )

            task.update(
                {
                    "status": "pending",
                    "errMsg": "",
                    "pointsCost": amount,
                    "pointsConsumed": True,
                    "pointsRefunded": False,
                    "consumeTransactionId": None,
                    "refundTransactionId": None,
                    "updatedAt": now,
                }
            )
            create_result = tx.insert_documents(FEATURE_JOBS_COLLECTION, [task])
            task_id = str((create_result.get("ids") or [None])[0] or "")
            if not task_id:
                raise ValueError("创建任务失败")

            consume_transaction_id = self._insert_transaction(
                tx,
                openid=openid,
                tx_type="consume",
                amount=-amount,
                balance_after=balance_after,
                reason="create_feature_job",
                task_id=task_id,
                now=now,
            )
            tx.update_document(
                FEATURE_JOBS_COLLECTION,
                task_id,
                {
                    "consumeTransactionId": consume_transaction_id,
                    "updatedAt": now,
                },
            )
            return task_id, {**task, "_id": task_id, "consumeTransactionId": consume_transaction_id}

    def consume_existing_job(self, task_id: str, amount: int = 1) -> dict[str, Any]:
        with self.db.transaction() as tx:
            task = tx.get_document(FEATURE_JOBS_COLLECTION, task_id, lock=True)
            if not task:
                raise ValueError("任务不存在")
            if bool(task.get("pointsConsumed")):
                return task

            openid = str(task.get("openid") or "")
            if not openid:
                raise ValueError("任务缺少 openid")

            user = self._lock_user(tx, openid)
            user_id = str(user.get("_id") or "")
            current_points = int(user.get("points") or 0)
            if current_points < amount:
                raise ValueError("积分不足，请先获取积分")

            now = _now_ms()
            balance_after = current_points - amount
            tx.update_document(
                self.users_collection,
                user_id,
                {
                    "points": balance_after,
                    "totalUsedPoints": int(user.get("totalUsedPoints") or 0) + amount,
                    "updatedAt": now,
                },
            )
            consume_transaction_id = self._insert_transaction(
                tx,
                openid=openid,
                tx_type="consume",
                amount=-amount,
                balance_after=balance_after,
                reason="create_feature_job",
                task_id=task_id,
                now=now,
            )
            tx.update_document(
                FEATURE_JOBS_COLLECTION,
                task_id,
                {
                    "pointsCost": amount,
                    "pointsConsumed": True,
                    "pointsRefunded": False,
                    "consumeTransactionId": consume_transaction_id,
                    "updatedAt": now,
                },
            )
            return {
                **task,
                "pointsCost": amount,
                "pointsConsumed": True,
                "pointsRefunded": False,
                "consumeTransactionId": consume_transaction_id,
                "updatedAt": now,
            }

    def refund_failed_job(self, task_id: str, err_msg: str, amount: int = 1) -> None:
        with self.db.transaction() as tx:
            task = tx.get_document(FEATURE_JOBS_COLLECTION, task_id, lock=True)
            if not task:
                raise ValueError("任务不存在")
            refund_transaction_id = task.get("refundTransactionId")
            points_consumed = bool(task.get("pointsConsumed"))
            points_refunded = bool(task.get("pointsRefunded"))

            if points_consumed and not points_refunded:
                openid = str(task.get("openid") or "")
                user = self._lock_user(tx, openid)
                user_id = str(user.get("_id") or "")
                current_points = int(user.get("points") or 0)
                balance_after = current_points + amount
                now = _now_ms()
                tx.update_document(
                    self.users_collection,
                    user_id,
                    {
                        "points": balance_after,
                        "totalRefundedPoints": int(user.get("totalRefundedPoints") or 0) + amount,
                        "updatedAt": now,
                    },
                )
                refund_transaction_id = self._insert_transaction(
                    tx,
                    openid=openid,
                    tx_type="refund",
                    amount=amount,
                    balance_after=balance_after,
                    reason="job_failed_refund",
                    task_id=task_id,
                    now=now,
                )
                points_refunded = True

            tx.update_document(
                FEATURE_JOBS_COLLECTION,
                task_id,
                {
                    "status": "failed",
                    "errMsg": err_msg,
                    "pointsRefunded": points_refunded,
                    "refundTransactionId": refund_transaction_id,
                    "refundErrMsg": "",
                    "updatedAt": _now_ms(),
                },
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
        with self.db.transaction() as tx:
            user = tx.get_document(self.users_collection, user_id, lock=True)
            openid = str(user.get("openid") or "")
            if not openid:
                raise ValueError("用户缺少 openid，无法级联删除关联数据")
            transactions_deleted = tx.delete_where(self.transactions_collection, {"openid": openid})
            jobs_deleted = tx.delete_where(self.jobs_collection, {"openid": openid})
            tx.delete_document(self.users_collection, user_id)
        return {
            "userId": user_id,
            "openid": openid,
            "transactionsDeleted": transactions_deleted,
            "jobsDeleted": jobs_deleted,
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
        now = _now_ms()
        with self.db.transaction() as tx:
            user = tx.get_document(self.users_collection, user_id, lock=True)
            if not user:
                raise ValueError("用户不存在")
            openid = str(user.get("openid", ""))
            current_points = int(user.get("points") or 0)
            balance_after = current_points + amount
            if balance_after < 0:
                raise ValueError("调整后积分不能小于 0")

            patch: dict[str, Any] = {
                "points": balance_after,
                "updatedAt": now,
            }
            if amount > 0:
                patch["totalGrantedPoints"] = int(user.get("totalGrantedPoints") or 0) + amount
            if amount < 0:
                patch["totalUsedPoints"] = int(user.get("totalUsedPoints") or 0) + abs(amount)
            tx.update_document(self.users_collection, user_id, patch)
            return tx.insert_documents(
                self.transactions_collection,
                [
                    {
                        "openid": openid,
                        "type": "adjust",
                        "amount": amount,
                        "balanceAfter": balance_after,
                        "reason": reason,
                        "taskId": None,
                        "operator": operator,
                        "createdAt": now,
                    }
                ],
            )

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
