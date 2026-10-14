"""Share reward routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.api.deps import require_openid
from app.core.redact import redact_secrets
from app.cloudbase.client import CloudBaseError
from app.services.share_rewards import CheckInAlreadyDoneError, ShareRewardLimitError, ShareRewardService


router = APIRouter(prefix="/miniapp/share-reward")


@router.get("/status")
async def status(request: Request) -> dict[str, object]:
    try:
        openid = require_openid(request)
        return {"success": True, "data": ShareRewardService().get_status(openid)}
    except ValueError as exc:
        return {"success": False, "errMsg": redact_secrets(str(exc))}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=redact_secrets(str(exc))) from exc


@router.post("/claim")
async def claim(request: Request) -> dict[str, object]:
    try:
        openid = require_openid(request)
        return {"success": True, "data": ShareRewardService().claim(openid)}
    except ShareRewardLimitError as exc:
        return {"success": False, "errMsg": redact_secrets(str(exc)), "data": exc.status}
    except ValueError as exc:
        return {"success": False, "errMsg": redact_secrets(str(exc))}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=redact_secrets(str(exc))) from exc


@router.post("/check-in")
async def check_in(request: Request) -> dict[str, object]:
    try:
        openid = require_openid(request)
        return {"success": True, "data": ShareRewardService().check_in(openid)}
    except CheckInAlreadyDoneError as exc:
        return {"success": False, "errMsg": redact_secrets(str(exc)), "data": exc.data}
    except ValueError as exc:
        return {"success": False, "errMsg": redact_secrets(str(exc))}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=redact_secrets(str(exc))) from exc
