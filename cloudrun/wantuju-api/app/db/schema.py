"""Column maps between document-shaped records and PostgreSQL tables."""
from __future__ import annotations

from dataclasses import dataclass


FEATURE_CONFIG_COLLECTION = "feature_configs"
USERS_COLLECTION = "users"
POINT_TRANSACTIONS_COLLECTION = "point_transactions"
FEATURE_JOBS_COLLECTION = "feature_jobs"


@dataclass(frozen=True)
class Column:
    field: str
    name: str
    kind: str
    nullable: bool = True


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    by_field: dict[str, Column]
    by_name: dict[str, Column]


def _table(name: str, columns: list[Column]) -> Table:
    frozen = tuple(columns)
    return Table(
        name=name,
        columns=frozen,
        by_field={column.field: column for column in frozen},
        by_name={column.name: column for column in frozen},
    )


def _col(field: str, name: str, kind: str, *, nullable: bool = True) -> Column:
    return Column(field=field, name=name, kind=kind, nullable=nullable)


TABLES: dict[str, Table] = {
    FEATURE_CONFIG_COLLECTION: _table(
        FEATURE_CONFIG_COLLECTION,
        [
            _col("_id", "id", "text", nullable=False),
            _col("type", "type", "text", nullable=False),
            _col("enabled", "enabled", "bool", nullable=False),
            _col("order", "sort_order", "int"),
            _col("param", "param", "jsonb", nullable=False),
            _col("public", "public", "jsonb", nullable=False),
            _col("ui", "ui", "jsonb", nullable=False),
            _col("validation", "validation", "jsonb"),
            _col("generation", "generation", "jsonb"),
            _col("test", "test", "jsonb"),
            _col("createdAt", "created_at", "ts", nullable=False),
            _col("updatedAt", "updated_at", "ts", nullable=False),
        ],
    ),
    USERS_COLLECTION: _table(
        USERS_COLLECTION,
        [
            _col("_id", "id", "text", nullable=False),
            _col("openid", "openid", "text", nullable=False),
            _col("points", "points", "int", nullable=False),
            _col("totalGrantedPoints", "total_granted_points", "int", nullable=False),
            _col("totalUsedPoints", "total_used_points", "int", nullable=False),
            _col("totalRefundedPoints", "total_refunded_points", "int", nullable=False),
            _col("nickName", "nick_name", "text", nullable=False),
            _col("avatarFileID", "avatar_file_id", "text", nullable=False),
            _col("profileCompleted", "profile_completed", "bool", nullable=False),
            _col("profileCompletedAt", "profile_completed_at", "ts"),
            _col("status", "status", "text", nullable=False),
            _col("blockedAt", "blocked_at", "ts"),
            _col("blockedReason", "blocked_reason", "text", nullable=False),
            _col("blockedBy", "blocked_by", "text", nullable=False),
            _col("unblockedAt", "unblocked_at", "ts"),
            _col("unblockedBy", "unblocked_by", "text", nullable=False),
            _col("shareCountToday", "share_count_today", "int", nullable=False),
            _col("lastShareDate", "last_share_date", "date"),
            _col("lastShareAt", "last_share_at", "ts"),
            _col("lastCheckInAt", "last_check_in_at", "ts"),
            _col("checkInDays", "check_in_days", "int", nullable=False),
            _col("lastLoginAt", "last_login_at", "ts"),
            _col("createdAt", "created_at", "ts", nullable=False),
            _col("updatedAt", "updated_at", "ts", nullable=False),
        ],
    ),
    POINT_TRANSACTIONS_COLLECTION: _table(
        POINT_TRANSACTIONS_COLLECTION,
        [
            _col("_id", "id", "text", nullable=False),
            _col("openid", "openid", "text", nullable=False),
            _col("type", "type", "text", nullable=False),
            _col("amount", "amount", "int", nullable=False),
            _col("balanceAfter", "balance_after", "int", nullable=False),
            _col("reason", "reason", "text", nullable=False),
            _col("taskId", "task_id", "text"),
            _col("operator", "operator", "text"),
            _col("createdAt", "created_at", "ts", nullable=False),
        ],
    ),
    FEATURE_JOBS_COLLECTION: _table(
        FEATURE_JOBS_COLLECTION,
        [
            _col("_id", "id", "text", nullable=False),
            _col("openid", "openid", "text", nullable=False),
            _col("type", "type", "text", nullable=False),
            _col("flow", "flow", "text"),
            _col("featureTitle", "feature_title", "text", nullable=False),
            _col("featureHomeDesc", "feature_home_desc", "text", nullable=False),
            _col("featureDescription", "feature_description", "text", nullable=False),
            _col("param", "param", "jsonb", nullable=False),
            _col("validation", "validation", "jsonb"),
            _col("fileID", "file_id", "text", nullable=False),
            _col("fileIDs", "file_ids", "jsonb", nullable=False),
            _col("generationPrompt", "generation_prompt", "text", nullable=False),
            _col("status", "status", "text", nullable=False),
            _col("posterFileID", "poster_file_id", "text"),
            _col("resultMode", "result_mode", "text", nullable=False),
            _col("resultFileIDs", "result_file_ids", "jsonb", nullable=False),
            _col("errMsg", "err_msg", "text", nullable=False),
            _col("refundErrMsg", "refund_err_msg", "text", nullable=False),
            _col("pointsCost", "points_cost", "int", nullable=False),
            _col("pointsConsumed", "points_consumed", "bool", nullable=False),
            _col("pointsRefunded", "points_refunded", "bool", nullable=False),
            _col("consumeTransactionId", "consume_transaction_id", "text"),
            _col("refundTransactionId", "refund_transaction_id", "text"),
            _col("sourceFileID", "source_file_id", "text"),
            _col("sourceFileIDs", "source_file_ids", "jsonb"),
            _col("processingLeaseToken", "processing_lease_token", "text"),
            _col("processingLeaseAt", "processing_lease_at", "ts"),
            _col("createdAt", "created_at", "ts", nullable=False),
            _col("updatedAt", "updated_at", "ts", nullable=False),
        ],
    ),
}
