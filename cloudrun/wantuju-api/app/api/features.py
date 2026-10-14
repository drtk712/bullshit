"""Feature configuration routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.cloudbase.client import CloudBaseError
from app.core.redact import redact_secrets
from app.services.features import FeatureService


router = APIRouter(prefix="/miniapp")


@router.get("/features")
async def features(type: str | None = Query(default=None)) -> dict[str, object]:
    try:
        service = FeatureService()
        if type:
            feature = service.get_enabled_feature(type)
            if feature:
                return {"success": True, "data": {"feature": feature}}
            return {"success": False, "errMsg": "功能暂不可用"}

        return {"success": True, "data": {"features": service.list_enabled_features()}}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=redact_secrets(str(exc))) from exc
