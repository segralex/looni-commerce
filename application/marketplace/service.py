from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from domain.listings.service import ListingService
from domain.reservations.service import ReservationService
from domain.users.service import UserService


class MarketplaceWorkflowError(Exception):
    """Raised when a marketplace workflow cannot be completed."""


class MarketplaceService:
    def __init__(
        self,
        user_service: Optional[UserService] = None,
        listing_service: Optional[ListingService] = None,
        reservation_service: Optional[ReservationService] = None,
    ) -> None:
        self.user_service = user_service or UserService()
        self.listing_service = listing_service or ListingService()
        self.reservation_service = reservation_service or ReservationService()

    def create_listing_for_user(self, seller_id, title, description, category, condition, price, currency, location):
        # seller must exist and be ACTIVE
        try:
            seller = self.user_service.get_user(seller_id)
        except Exception:
            raise MarketplaceWorkflowError("seller not found")
        if seller.status.name != "ACTIVE":
            raise MarketplaceWorkflowError("seller must be ACTIVE")

        return self.listing_service.create_listing(
            seller_id, title, description, category, condition, price, currency, location
        )

    def publish_listing(self, seller_id, listing_id):
        try:
            seller = self.user_service.get_user(seller_id)
        except Exception:
            raise MarketplaceWorkflowError("seller not found")
        if seller.status.name != "ACTIVE":
            raise MarketplaceWorkflowError("seller must be ACTIVE")

        try:
            listing = self.listing_service.get_listing(listing_id)
        except Exception:
            raise MarketplaceWorkflowError("listing not found")

        if listing.seller_id != seller_id:
            raise MarketplaceWorkflowError("seller does not own listing")

        try:
            return self.listing_service.publish(listing_id)
        except Exception as e:
            raise MarketplaceWorkflowError("cannot publish listing") from e

    def create_reservation(self, buyer_id, listing_id):
        # buyer and seller must exist and be ACTIVE
        try:
            buyer = self.user_service.get_user(buyer_id)
        except Exception:
            raise MarketplaceWorkflowError("buyer not found")
        if buyer.status.name != "ACTIVE":
            raise MarketplaceWorkflowError("buyer must be ACTIVE")

        try:
            listing = self.listing_service.get_listing(listing_id)
        except Exception:
            raise MarketplaceWorkflowError("listing not found")

        seller_id = listing.seller_id
        try:
            seller = self.user_service.get_user(seller_id)
        except Exception:
            raise MarketplaceWorkflowError("seller not found")
        if seller.status.name != "ACTIVE":
            raise MarketplaceWorkflowError("seller must be ACTIVE")

        if buyer_id == seller_id:
            raise MarketplaceWorkflowError("buyer cannot be the seller")

        # listing must be PUBLISHED to reserve
        if listing.status.name != "PUBLISHED":
            raise MarketplaceWorkflowError("listing must be PUBLISHED to reserve")

        try:
            return self.reservation_service.create_reservation(listing_id, buyer_id, seller_id)
        except Exception as e:
            raise MarketplaceWorkflowError("cannot create reservation") from e

    def accept_reservation(self, reservation_id, seller_id):
        # seller must exist and be ACTIVE
        try:
            seller = self.user_service.get_user(seller_id)
        except Exception:
            raise MarketplaceWorkflowError("seller not found")
        if seller.status.name != "ACTIVE":
            raise MarketplaceWorkflowError("seller must be ACTIVE")

        try:
            reservation = self.reservation_service.get_reservation(reservation_id)
        except Exception:
            raise MarketplaceWorkflowError("reservation not found")

        if reservation.seller_id != seller_id:
            raise MarketplaceWorkflowError("seller does not own this reservation")

        if reservation.status.name != "PENDING":
            raise MarketplaceWorkflowError("reservation must be PENDING to accept")

        # ensure no other accepted reservation for the listing
        for r in self.reservation_service._store.values():
            if r.listing_id == reservation.listing_id and r.status.name == "ACCEPTED":
                raise MarketplaceWorkflowError("another reservation already accepted for this listing")

        # perform accept then reserve listing; rollback if listing reservation fails
        old_status = reservation.status
        try:
            self.reservation_service.accept(reservation_id)
        except Exception as e:
            raise MarketplaceWorkflowError("cannot accept reservation") from e

        try:
            self.listing_service.reserve(reservation.listing_id)
        except Exception as e:
            # rollback reservation to previous state
            if reservation_id in self.reservation_service._store:
                stored = self.reservation_service._store[reservation_id]
                stored.status = old_status
                stored.updated_at = datetime.now(UTC)
                self.reservation_service._store[reservation_id] = stored
            raise MarketplaceWorkflowError("cannot reserve listing; rolled back reservation") from e

        return self.reservation_service.get_reservation(reservation_id)
