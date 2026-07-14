from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_201_CREATED

from app.dependencies import get_marketplace_service
from app.schemas.reservations import ReservationCreate, ReservationResponse
from application.marketplace.service import MarketplaceService, MarketplaceWorkflowError
from domain.reservations.models import ReservationStatus
from domain.listings.models import ListingStatus

router = APIRouter(prefix="/reservations", tags=["reservations"])


def _to_response(r) -> ReservationResponse:
    return ReservationResponse(
        id=r.id,
        listing_id=r.listing_id,
        buyer_id=r.buyer_id,
        seller_id=r.seller_id,
        status=r.status.value if hasattr(r.status, "value") else str(r.status),
        expires_at=r.expires_at,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.post("/", response_model=ReservationResponse, status_code=HTTP_201_CREATED)
def create_reservation(
    payload: ReservationCreate, marketplace_service: MarketplaceService = Depends(get_marketplace_service)
) -> ReservationResponse:
    try:
        reservation = marketplace_service.create_reservation(payload.buyer_id, payload.listing_id)
    except MarketplaceWorkflowError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=409, detail=message)
    return _to_response(reservation)


@router.get("/{reservation_id}", response_model=ReservationResponse)
def get_reservation(reservation_id: UUID, marketplace_service: MarketplaceService = Depends(get_marketplace_service)):
    try:
        reservation = marketplace_service.get_reservation(reservation_id)
    except MarketplaceWorkflowError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_response(reservation)


@router.post("/{reservation_id}/accept", response_model=ReservationResponse)
def accept_reservation(
    reservation_id: UUID,
    body: dict[str, Any],
    marketplace_service: MarketplaceService = Depends(get_marketplace_service),
) -> ReservationResponse:
    seller_id = body.get("seller_id")
    if seller_id is None:
        raise HTTPException(status_code=422, detail="seller_id is required to accept reservation")
    try:
        reservation = marketplace_service.accept_reservation(reservation_id, UUID(str(seller_id)))
    except MarketplaceWorkflowError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=409, detail=message)
    return _to_response(reservation)


@router.post("/{reservation_id}/cancel", response_model=ReservationResponse)
def cancel_reservation(reservation_id: UUID, marketplace_service: MarketplaceService = Depends(get_marketplace_service)):
    try:
        reservation = marketplace_service.cancel_reservation(reservation_id)
    except MarketplaceWorkflowError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=409, detail=message)
    return _to_response(reservation)
