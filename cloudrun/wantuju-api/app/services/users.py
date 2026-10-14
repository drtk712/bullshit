"""User profile service."""
from __future__ import annotations

from hashlib import sha256
import time
from typing import Any

from app.db import Database


USERS_COLLECTION = "users"
POINT_TRANSACTIONS_COLLECTION = "point_transactions"


def mask_openid(openid: str) -> str:
    return f"******{str(openid or '')[-4:]}"


def to_public_user(user: dict[str, Any], openid: str) -> dict[str, Any]:
    return {
        "openidMasked": mask_openid(openid),
        "points": user.get("points", 0),
        "isNewUser": bool(user.get("isNewUser")),
        "createdAt": user.get("createdAt"),
        "lastLoginAt": user.get("lastLoginAt"),
        "lastCheckInAt": user.get("lastCheckInAt"),
        "checkInDays": user.get("checkInDays") or 0,
        "nickName": user.get("nickName") or "",
        "avatarFileID": user.get("avatarFileID") or "",
        "profileCompleted": bool(user.get("profileCompleted")),
        "profileCompletedAt": user.get("profileCompletedAt") or None,
    }


def assert_user_usable(user: dict[str, Any]) -> None:
    if str(user.get("status") or "active") == "blocked":
        raise ValueError("账号已被限制使用")


class UserService:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def ensure_user(self, openid: str, *, record_login: bool = False) -> dict[str, Any]:
        now = int(time.time() * 1000)
        user = self.db.find_one(USERS_COLLECTION, {"openid": openid})
        if user:
            assert_user_usable(user)
            if record_login:
                self.db.update_document(USERS_COLLECTION, str(user["_id"]), {"updatedAt": now, "lastLoginAt": now})
                return {**user, "updatedAt": now, "lastLoginAt": now, "isNewUser": False}
            return {**user, "isNewUser": False}

        user_data = {
            "openid": openid,
            "points": 3,
            "totalGrantedPoints": 3,
            "totalUsedPoints": 0,
            "totalRefundedPoints": 0,
            "createdAt": now,
            "updatedAt": now,
            "lastLoginAt": now,
        }
        try:
            with self.db.transaction() as tx:
                create_result = tx.insert_documents(USERS_COLLECTION, [user_data])
                user_id = self._created_id(create_result)
                self._create_first_login_transaction(tx, openid, now)
            return {"_id": user_id, **user_data, "isNewUser": True}
        except Exception:
            existing_user = self.db.find_one(USERS_COLLECTION, {"openid": openid})
            if existing_user:
                assert_user_usable(existing_user)
                return {**existing_user, "isNewUser": False}
            raise

    def get_profile(self, openid: str, *, record_login: bool = False) -> dict[str, Any]:
        user = self.ensure_user(openid, record_login=record_login)
        return to_public_user(user, openid)

    def update_profile(self, openid: str, *, nick_name: str, avatar_file_id: str) -> dict[str, Any]:
        user = self.ensure_user(openid)
        nick_name = str(nick_name or "").strip()
        avatar_file_id = str(avatar_file_id or "").strip()

        if not nick_name:
            raise ValueError("请填写昵称")
        if len(nick_name) > 24:
            raise ValueError("昵称不能超过 24 个字符")
        if not avatar_file_id.startswith("cloud://"):
            raise ValueError("请选择头像")

        now = int(time.time() * 1000)
        profile_completed_at = user.get("profileCompletedAt") or now
        patch = {
            "nickName": nick_name,
            "avatarFileID": avatar_file_id,
            "profileCompleted": True,
            "profileCompletedAt": profile_completed_at,
            "updatedAt": now,
        }
        self.db.update_document(USERS_COLLECTION, str(user["_id"]), patch)
        return to_public_user({**user, **patch}, openid)

    def _created_id(self, result: dict[str, Any]) -> str | None:
        for key in ("_id", "id"):
            value = result.get(key)
            if value:
                return str(value)
        ids = result.get("ids")
        if isinstance(ids, list) and ids:
            return str(ids[0])
        inserted_ids = result.get("insertedIds") or result.get("inserted_ids")
        if isinstance(inserted_ids, list) and inserted_ids:
            return str(inserted_ids[0])
        return None

    def _create_first_login_transaction(self, tx, openid: str, now: int) -> None:
        # Savepoint so a duplicate grant id does not abort the user insert.
        tx.conn.execute("SAVEPOINT first_login_grant")
        try:
            tx.insert_documents(
                POINT_TRANSACTIONS_COLLECTION,
                [
                    {
                        "_id": self._first_login_transaction_id(openid),
                        "openid": openid,
                        "type": "grant",
                        "amount": 3,
                        "balanceAfter": 3,
                        "reason": "first_login",
                        "taskId": None,
                        "createdAt": now,
                    }
                ],
            )
        except Exception:
            # The user document is the source of truth for the initial balance.
            # A duplicate id here means the idempotent first-login grant already exists.
            tx.conn.execute("ROLLBACK TO SAVEPOINT first_login_grant")

    def _first_login_transaction_id(self, openid: str) -> str:
        digest = sha256(openid.encode("utf-8")).hexdigest()
        return f"first_login_{digest}"
