"""Point transaction routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.deps import require_openid
from app.core.redact import redact_secrets
from app.cloudbase.client import CloudBaseError
from app.services.transactions import TransactionService


router = APIRouter(prefix="/miniapp")


@router.get("/transactions")
async def transactions(
    request: Request,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=50),
) -> dict[str, object]:
    try:
        openid = require_openid(request)
        data = TransactionService().list_transactions(openid, page=page, page_size=pageSize)
        return {"success": True, "data": data}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=redact_secrets(str(exc))) from exc
