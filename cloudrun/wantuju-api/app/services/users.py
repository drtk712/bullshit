"""User profile service."""
from __future__ import annotations

from hashlib import sha256
import time
from typing import Any

from app.db import Database
from app.db.errors import DatabaseError
from app.db.repository import row_to_doc


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
        result = self.db.call(
            "wantuju_ensure_user",
            {
                "openid": openid,
                "record_login": record_login,
                "now": now,
                "grant_id": self._first_login_transaction_id(openid),
            },
        )
        if not isinstance(result, dict) or not isinstance(result.get("user"), dict):
            raise DatabaseError("创建用户失败")
        user = row_to_doc(USERS_COLLECTION, result["user"])
        if not result.get("ok"):
            if result.get("code") == "blocked":
                raise ValueError("账号已被限制使用")
            raise DatabaseError("创建用户失败")
        return {**user, "isNewUser": bool(result.get("isNewUser"))}

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

    def _first_login_transaction_id(self, openid: str) -> str:
        digest = sha256(openid.encode("utf-8")).hexdigest()
        return f"first_login_{digest}"
