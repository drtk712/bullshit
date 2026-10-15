"""User profile routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import require_openid
from app.core.redact import redact_secrets
from app.cloudbase.client import CloudBaseError
from app.services.share_rewards import ShareRewardService
from app.services.users import UserService


router = APIRouter(prefix="/miniapp")


class ProfileUpdateRequest(BaseModel):
    nickName: str
    avatarFileID: str


@router.get("/me")
async def me(request: Request, recordLogin: bool = False) -> dict[str, object]:
    try:
        openid = require_openid(request)
        user_service = UserService()
        user = user_service.get_profile(openid, record_login=recordLogin)
        share_reward = ShareRewardService(user_service=user_service).get_status(openid)
        return {"success": True, "data": {"user": user, "shareReward": share_reward}}
    except ValueError as exc:
        return {"success": False, "errMsg": redact_secrets(str(exc))}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=redact_secrets(str(exc))) from exc


@router.post("/profile")
async def update_profile(request: Request, payload: ProfileUpdateRequest) -> dict[str, object]:
    try:
        openid = require_openid(request)
        user = UserService().update_profile(
            openid,
            nick_name=payload.nickName,
            avatar_file_id=payload.avatarFileID,
        )
        return {"success": True, "data": {"user": user}}
    except ValueError as exc:
        return {"success": False, "errMsg": redact_secrets(str(exc))}
    except CloudBaseError as exc:
        raise HTTPException(status_code=502, detail=redact_secrets(str(exc))) from exc
