"""Share reward service."""
from __future__ import annotations

import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.logging import log_event, mask_openid
from app.db import Database
from app.db.repository import row_to_doc
from app.services.users import USERS_COLLECTION, UserService


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
        now = int(time.time() * 1000)
        result = self.db.call(
            "wantuju_claim_share",
            {
                "user_id": str(user["_id"]),
                "openid": openid,
                "now": now,
                "today": get_shanghai_date_string(),
            },
        )
        latest = row_to_doc(USERS_COLLECTION, (result or {}).get("user") or {})
        status = get_share_reward_data(latest)
        if not result or not result.get("ok"):
            raise ShareRewardLimitError(status)
        log_event(
            logger,
            "share_reward_claimed",
            openid=mask_openid(openid),
            points=status["points"],
            share_count=status["shareCountToday"],
        )
        return {"pointsGained": 1, **status}

    def check_in(self, openid: str) -> dict[str, Any]:
        user = self.user_service.ensure_user(openid)
        now = int(time.time() * 1000)
        result = self.db.call(
            "wantuju_check_in",
            {
                "user_id": str(user["_id"]),
                "openid": openid,
                "now": now,
                "today": get_shanghai_date_string(),
            },
        )
        latest = row_to_doc(USERS_COLLECTION, (result or {}).get("user") or {})
        if not result or not result.get("ok"):
            raise CheckInAlreadyDoneError({
                "checkedIn": True,
                "points": int(latest.get("points") or 0),
                "checkInAt": latest.get("lastCheckInAt"),
            })
        points = int(latest.get("points") or 0)
        log_event(
            logger,
            "daily_check_in",
            openid=mask_openid(openid),
            points=points,
            check_in_days=int(latest.get("checkInDays") or 0),
        )
        return {
            "checkedIn": True,
            "pointsGained": 1,
            "points": points,
            "checkInAt": latest.get("lastCheckInAt"),
        }
