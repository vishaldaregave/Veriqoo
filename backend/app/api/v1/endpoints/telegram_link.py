"""FastAPI endpoints for Telegram Account Linking."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import get_account_linking_service
from backend.app.api.errors import ErrorCode
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.telegram.account_linking import (
    AccountLinkError,
    AccountLinkingService,
    ConsumedLinkTokenError,
    ExpiredLinkTokenError,
    InvalidLinkTokenError,
)

router = APIRouter(prefix="/telegram", tags=["Telegram Integration"])


class ConsumeTelegramLinkRequest(BaseModel):
    """Payload to consume a one-time Telegram account link challenge."""
    link_token: str = Field(..., description="One-time secret linking challenge token issued by /link")


class TelegramLinkResponse(BaseModel):
    """Response payload upon successful account link establishment."""
    telegram_user_id: int
    supabase_user_id: str
    status: str
    linked_at: str


@router.post(
    "/link/consume",
    response_model=TelegramLinkResponse,
    status_code=status.HTTP_200_OK,
    summary="Consume Telegram Link Challenge",
    description="Establish a verified account link between a Telegram user and the authenticated Supabase user.",
)
def consume_link_token(
    request: ConsumeTelegramLinkRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    link_service: AccountLinkingService = Depends(get_account_linking_service),
) -> TelegramLinkResponse:
    """Validate challenge token and link initiating Telegram account to authenticated caller."""
    try:
        link = link_service.consume_link_challenge(
            token=request.link_token,
            authenticated_user=current_user,
        )
        return TelegramLinkResponse(
            telegram_user_id=link.telegram_user_id,
            supabase_user_id=link.supabase_user_id,
            status=link.status.value,
            linked_at=link.linked_at.isoformat(),
        )
    except (InvalidLinkTokenError, ExpiredLinkTokenError, ConsumedLinkTokenError, AccountLinkError) as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_REQUEST.value,
                "message": str(err),
                "details": {},
            },
        )

