"""Points consume and refund stay atomic."""
from __future__ import annotations

import threading
import time

import pytest

from app.db import PointLedger


def _now() -> int:
    return int(time.time() * 1000)


def _user(db, openid: str, points: int) -> dict:
    now = _now()
    document = {
        "openid": openid,
        "points": points,
        "totalGrantedPoints": points,
        "totalUsedPoints": 0,
        "totalRefundedPoints": 0,
        "createdAt": now,
        "updatedAt": now,
        "lastLoginAt": now,
    }
    created = db.insert_documents("users", [document])
    document["_id"] = created["ids"][0]
    return document


def _job(openid: str) -> dict:
    now = _now()
    return {
        "type": "palm",
        "featureTitle": "看手相",
        "featureHomeDesc": "",
        "featureDescription": "",
        "param": {},
        "fileID": "cloud://test/a.jpg",
        "fileIDs": ["cloud://test/a.jpg"],
        "generationPrompt": "prompt",
        "status": "pending",
        "posterFileID": None,
        "resultMode": "single",
        "resultFileIDs": [],
        "errMsg": "",
        "openid": openid,
        "pointsCost": 1,
        "pointsConsumed": True,
        "pointsRefunded": False,
        "consumeTransactionId": None,
        "refundTransactionId": None,
        "createdAt": now,
        "updatedAt": now,
    }


def _points(db, openid: str) -> int:
    user = db.find_one("users", {"openid": openid})
    assert user is not None
    return int(user["points"])


def test_create_pending_job_consumes_points_and_refund_restores_them_once(db):
    _user(db, "user-1", 3)
    ledger = PointLedger(db)

    task_id, task = ledger.create_pending_job(_job("user-1"), amount=1)

    assert task["_id"] == task_id
    assert task["pointsConsumed"] is True
    assert _points(db, "user-1") == 2
    user = db.find_one("users", {"openid": "user-1"})
    assert user["totalUsedPoints"] == 1
    stored = db.get_document("feature_jobs", task_id)
    assert stored["consumeTransactionId"]
    consumes, consume_total = _transactions(db, "user-1", "consume")
    assert consume_total == 1
    assert consumes[0]["amount"] == -1
    assert consumes[0]["balanceAfter"] == 2
    assert consumes[0]["taskId"] == task_id

    ledger.refund_failed_job(task_id, "生成失败", amount=1)

    assert _points(db, "user-1") == 3
    user = db.find_one("users", {"openid": "user-1"})
    assert user["totalRefundedPoints"] == 1
    failed = db.get_document("feature_jobs", task_id)
    assert failed["status"] == "failed"
    assert failed["pointsRefunded"] is True
    assert failed["errMsg"] == "生成失败"
    refunds, refund_total = _transactions(db, "user-1", "refund")
    assert refund_total == 1
    assert refunds[0]["amount"] == 1
    assert refunds[0]["balanceAfter"] == 3

    ledger.refund_failed_job(task_id, "生成失败", amount=1)

    assert _points(db, "user-1") == 3
    _, refund_total = _transactions(db, "user-1", "refund")
    assert refund_total == 1


def test_insufficient_points_rolls_back(db):
    _user(db, "user-2", 0)
    ledger = PointLedger(db)

    with pytest.raises(ValueError, match="积分不足"):
        ledger.create_pending_job(_job("user-2"), amount=1)

    assert _points(db, "user-2") == 0
    assert db.count_documents("feature_jobs", {"openid": "user-2"}) == 0
    assert db.count_documents("point_transactions", {"openid": "user-2"}) == 0


def test_consume_existing_job_is_idempotent(db):
    _user(db, "user-3", 3)
    ledger = PointLedger(db)
    created = db.insert_documents(
        "feature_jobs",
        [{**_job("user-3"), "pointsConsumed": False, "pointsCost": 0}],
    )
    task_id = created["ids"][0]

    first = ledger.consume_existing_job(task_id, amount=1)
    second = ledger.consume_existing_job(task_id, amount=1)

    assert first["pointsConsumed"] is True
    assert second["pointsConsumed"] is True
    assert _points(db, "user-3") == 2
    _, total = _transactions(db, "user-3", "consume")
    assert total == 1


def test_ensure_user_grants_three_points_once(db):
    from app.services.users import UserService

    service = UserService(db)
    created = service.ensure_user("fresh-user")
    again = service.ensure_user("fresh-user")

    assert created["isNewUser"] is True
    assert created["points"] == 3
    assert again["isNewUser"] is False
    assert again["points"] == 3
    assert db.count_documents("point_transactions", {"openid": "fresh-user", "reason": "first_login"}) == 1


def test_adjust_points_rejects_negative_balance_and_delete_user_cascades(db):
    from app.db import UserAdminStore

    user = _user(db, "user-5", 1)
    store = UserAdminStore(db)
    with pytest.raises(ValueError, match="不能小于 0"):
        store.adjust_points(user["_id"], -2, "fix")
    assert _points(db, "user-5") == 1

    store.adjust_points(user["_id"], 2, "bonus")
    assert _points(db, "user-5") == 3
    assert db.count_documents("point_transactions", {"openid": "user-5", "type": "adjust"}) == 1

    with pytest.raises(ValueError, match="用户不存在"):
        store.adjust_points("missing-user", 1, "x")

    ledger = PointLedger(db)
    ledger.create_pending_job(_job("user-5"), amount=1)
    deleted = store.delete_user(user["_id"])
    assert deleted["transactionsDeleted"] >= 1
    assert deleted["jobsDeleted"] == 1
    assert db.find_one("users", {"openid": "user-5"}) is None
    assert db.count_documents("feature_jobs", {"openid": "user-5"}) == 0


def test_concurrent_consume_cannot_overdraw(db):
    _user(db, "user-4", 1)
    ledger = PointLedger(db)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt() -> None:
        barrier.wait()
        try:
            ledger.create_pending_job(_job("user-4"), amount=1)
        except ValueError as exc:
            result = str(exc)
        else:
            result = "ok"
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["ok", "积分不足，请先获取积分"]
    assert _points(db, "user-4") == 0
    assert db.count_documents("feature_jobs", {"openid": "user-4"}) == 1
    assert db.count_documents("point_transactions", {"openid": "user-4", "type": "consume"}) == 1


def _transactions(db, openid: str, tx_type: str) -> tuple[list[dict], int]:
    items = db.find_many(
        "point_transactions",
        {"openid": openid, "type": tx_type},
        sort={"createdAt": -1},
        limit=20,
    )
    total = db.count_documents("point_transactions", {"openid": openid, "type": tx_type})
    return items, total
