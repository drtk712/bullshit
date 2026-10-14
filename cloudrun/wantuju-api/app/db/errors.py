"""Database errors for the PostgreSQL data layer."""
from __future__ import annotations

from app.cloudbase.client import CloudBaseError


class DatabaseError(CloudBaseError):
    """Raised when PostgreSQL cannot complete a data-layer request.

    Subclasses CloudBaseError so existing API and admin handlers keep mapping
    data-layer failures to the same responses they used for the document API.
    """

    def __init__(self, message: str, *, primary: str | None = None) -> None:
        from app.core.redact import redact_secrets

        super().__init__(message)
        self.primary = redact_secrets(primary or "")


# Messages raised by the plpgsql functions. Callers still see ValueError.
BUSINESS_ERRORS = (
    "用户缺少 openid，无法级联删除关联数据",
    "积分不足，请先获取积分",
    "调整后积分不能小于 0",
    "任务缺少 openid",
    "创建任务失败",
    "用户不存在",
    "任务不存在",
)


def business_error(exc: BaseException) -> ValueError | None:
    """Return the domain ValueError when a driver error is one of the known messages."""
    primary = getattr(exc, "primary", "") or ""
    if primary in BUSINESS_ERRORS:
        return ValueError(primary)
    text = str(exc)
    for message in BUSINESS_ERRORS:
        if message in text:
            return ValueError(message)
    return None
