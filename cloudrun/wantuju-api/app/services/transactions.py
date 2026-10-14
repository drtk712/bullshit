"""Point transaction service."""
from __future__ import annotations

from typing import Any

from app.db import Database


POINT_TRANSACTIONS_COLLECTION = "point_transactions"


def to_public_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    return {
        "_id": transaction.get("_id"),
        "type": transaction.get("type"),
        "amount": transaction.get("amount"),
        "balanceAfter": transaction.get("balanceAfter"),
        "reason": transaction.get("reason"),
        "taskId": transaction.get("taskId") or None,
        "createdAt": transaction.get("createdAt"),
    }


class TransactionService:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def list_transactions(self, openid: str, *, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        page = max(1, int(page or 1))
        page_size = min(50, max(1, int(page_size or 10)))
        skip = (page - 1) * page_size
        filter_query = {"openid": openid}

        total = self.db.count_documents(POINT_TRANSACTIONS_COLLECTION, filter_query)
        transactions = self.db.find_many(
            POINT_TRANSACTIONS_COLLECTION,
            filter_query,
            sort={"createdAt": -1},
            limit=page_size,
            skip=skip,
        )

        return {
            "transactions": [to_public_transaction(item) for item in transactions],
            "total": total,
            "page": page,
            "pageSize": page_size,
            "hasMore": skip + page_size < total,
        }
