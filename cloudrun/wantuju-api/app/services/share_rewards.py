"""Share reward service."""
from __future__ import annotations

import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.logging import log_event, mask_openid
from app.db import Database
from app.services.users import POINT_TRANSACTIONS_COLLECTION, USERS_COLLECTION, UserService


SHARE_POINTS_LIMIT_PER_DAY = 3
logger = logging.getLogger(__name__)


class ShareRewardLimitError(ValueError):
    def __init__(self, status: dict[str, Any]):
        super().__init__("今日分享次数已达上限")
        self.status = status


class CheckInAlreadyDoneError(ValueError):
    def __init__(self, data: dict[str, Any]):
        super().__init__("今日已签到")
        self.data = data


def get_shanghai_date_string() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).date().isoformat()


def timestamp_to_shanghai_date_string(timestamp_ms: int | None) -> str:
    if not timestamp_ms:
        return ""
    return (datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc) + timedelta(hours=8)).date().isoformat()


def get_share_reward_data(user: dict[str, Any]) -> dict[str, Any]:
    today = get_shanghai_date_string()
    share_count_today = int(user.get("shareCountToday") or 0) if user.get("lastShareDate") == today else 0
    remaining_today = max(0, SHARE_POINTS_LIMIT_PER_DAY - share_count_today)
    return {
        "shareRewardPoints": 1,
        "shareLimitPerDay": SHARE_POINTS_LIMIT_PER_DAY,
        "shareCountToday": share_count_today,
        "remainingToday": remaining_today,
        "canEarnSharePoints": remaining_today > 0,
        "points": int(user.get("points") or 0),
    }


class ShareRewardService:
    def __init__(self, db: Database | None = None, user_service: UserService | None = None):
        self.db = db or Database()
        self.user_service = user_service or UserService(self.db)

    def get_status(self, openid: str) -> dict[str, Any]:
        user = self.user_service.ensure_user(openid)
        return get_share_reward_data(user)

    def claim(self, openid: str) -> dict[str, Any]:
        user = self.user_service.ensure_user(openid)
        with self.db.transaction() as tx:
            latest_user = tx.find_one(USERS_COLLECTION, {"_id": user["_id"]}, lock=True)
            if not latest_user:
                raise ValueError("用户不存在")
            status = get_share_reward_data(latest_user)
            if not status["canEarnSharePoints"]:
                raise ShareRewardLimitError(status)

            now = int(time.time() * 1000)
            today = get_shanghai_date_string()
            next_points = int(latest_user.get("points") or 0) + 1
            next_user = {
                **latest_user,
                "points": next_points,
                "totalGrantedPoints": int(latest_user.get("totalGrantedPoints") or 0) + 1,
                "shareCountToday": status["shareCountToday"] + 1,
                "lastShareDate": today,
                "lastShareAt": now,
                "updatedAt": now,
            }

            tx.update_document(
                USERS_COLLECTION,
                str(latest_user["_id"]),
                {
                    "points": next_user["points"],
                    "totalGrantedPoints": next_user["totalGrantedPoints"],
                    "shareCountToday": next_user["shareCountToday"],
                    "lastShareDate": today,
                    "lastShareAt": now,
                    "updatedAt": now,
                },
            )
            tx.insert_documents(
                POINT_TRANSACTIONS_COLLECTION,
                [
                    {
                        "openid": openid,
                        "type": "grant",
                        "amount": 1,
                        "balanceAfter": next_points,
                        "reason": "share_reward",
                        "taskId": None,
                        "createdAt": now,
                    }
                ],
            )
        log_event(
            logger,
            "share_reward_claimed",
            openid=mask_openid(openid),
            points=next_points,
            share_count=next_user["shareCountToday"],
        )
        return {"pointsGained": 1, **get_share_reward_data(next_user)}

    def check_in(self, openid: str) -> dict[str, Any]:
        user = self.user_service.ensure_user(openid)
        with self.db.transaction() as tx:
            latest_user = tx.find_one(USERS_COLLECTION, {"_id": user["_id"]}, lock=True)
            if not latest_user:
                raise ValueError("用户不存在")

            today = get_shanghai_date_string()
            last_check_in_date = timestamp_to_shanghai_date_string(latest_user.get("lastCheckInAt"))
            if last_check_in_date == today:
                raise CheckInAlreadyDoneError({
                    "checkedIn": True,
                    "points": int(latest_user.get("points") or 0),
                    "checkInAt": latest_user.get("lastCheckInAt"),
                })

            now = int(time.time() * 1000)
            next_points = int(latest_user.get("points") or 0) + 1
            next_check_in_days = int(latest_user.get("checkInDays") or 0) + 1
            next_total_granted = int(latest_user.get("totalGrantedPoints") or 0) + 1

            tx.update_document(
                USERS_COLLECTION,
                str(latest_user["_id"]),
                {
                    "points": next_points,
                    "totalGrantedPoints": next_total_granted,
                    "lastCheckInAt": now,
                    "checkInDays": next_check_in_days,
                    "updatedAt": now,
                },
            )
            tx.insert_documents(
                POINT_TRANSACTIONS_COLLECTION,
                [
                    {
                        "openid": openid,
                        "type": "grant",
                        "amount": 1,
                        "balanceAfter": next_points,
                        "reason": "daily_check_in",
                        "taskId": None,
                        "createdAt": now,
                    }
                ],
            )
        log_event(
            logger,
            "daily_check_in",
            openid=mask_openid(openid),
            points=next_points,
            check_in_days=next_check_in_days,
        )
        return {
            "checkedIn": True,
            "pointsGained": 1,
            "points": next_points,
            "checkInAt": now,
        }
