from __future__ import annotations

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_201_CREATED

from app.dependencies import get_marketplace_service
from app.schemas.users import UserCreate, UserResponse
from domain.users.models import UserStatus
from application.marketplace.service import MarketplaceService, MarketplaceWorkflowError

router = APIRouter(prefix="/users", tags=["users"])


def _to_response(user) -> UserResponse:
    return UserResponse(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        phone=user.phone,
        status=user.status.value if hasattr(user.status, "value") else str(user.status),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post("/", response_model=UserResponse, status_code=HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    marketplace_service: MarketplaceService = Depends(get_marketplace_service),
) -> UserResponse:
    try:
        user = marketplace_service.create_user(payload.display_name, payload.email, payload.phone)
    except MarketplaceWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_response(user)


@router.post("/{user_id}/activate", response_model=UserResponse)
def activate_user(
    user_id: UUID,
    marketplace_service: MarketplaceService = Depends(get_marketplace_service),
) -> UserResponse:
    try:
        user = marketplace_service.activate_user(user_id)
    except MarketplaceWorkflowError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=409, detail=message)
    return _to_response(user)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
    marketplace_service: MarketplaceService = Depends(get_marketplace_service),
) -> UserResponse:
    try:
        user = marketplace_service.get_user(user_id)
    except MarketplaceWorkflowError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_response(user)
