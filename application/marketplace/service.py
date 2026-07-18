from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from domain.repositories import (
    DuplicateEntityError,
    EntityNotFoundError,
    ListingRepository,
    ReservationRepository,
    UserRepository,
)
from domain.listings.models import ItemCondition, Listing, ListingStatus
from domain.listings.service import ListingService
from domain.reservations.models import Reservation, ReservationStatus
from domain.reservations.service import ReservationService
from domain.users.models import User, UserStatus
from domain.users.service import UserService


class MarketplaceWorkflowError(Exception):
    """Raised when a marketplace workflow cannot be completed."""


class MarketplaceService:
    def __init__(
        self,
        user_repository: Optional[UserRepository] = None,
        listing_repository: Optional[ListingRepository] = None,
        reservation_repository: Optional[ReservationRepository] = None,
        event_recorder: Optional[Any] = None,
        user_service: Optional[UserService] = None,
        listing_service: Optional[ListingService] = None,
        reservation_service: Optional[ReservationService] = None,
        media_service: Optional[Any] = None,
    ) -> None:
        self.user_repository = user_repository
        self.listing_repository = listing_repository
        self.reservation_repository = reservation_repository
        self.user_service = user_service or UserService()
        self.listing_service = listing_service or ListingService()
        self.reservation_service = reservation_service or ReservationService()
        self.event_recorder = event_recorder
        self.media_service = media_service

    def _use_repositories(self) -> bool:
        return (
            self.user_repository is not None
            and self.listing_repository is not None
            and self.reservation_repository is not None
        )

    def _record_event(self, event_type: str, aggregate_type: str, aggregate_id: UUID, payload: Any) -> None:
        if self.event_recorder is None:
            return
        try:
            self.event_recorder.record(event_type, aggregate_type, aggregate_id, payload)
        except Exception:
            pass

    def create_user(self, display_name: str, email: str, phone: str | None = None) -> User:
        if self._use_repositories():
            user = User(id=uuid4(), display_name=display_name, email=email, phone=phone)
            try:
                self.user_repository.add(user)
            except DuplicateEntityError as exc:
                raise MarketplaceWorkflowError("user already exists") from exc
            return user

        return self.user_service.create_user(display_name, email, phone)

    def activate_user(self, user_id: UUID) -> User:
        if self._use_repositories():
            try:
                existing = self.user_repository.get(user_id)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("user not found") from exc

            if existing.status != UserStatus.PENDING:
                raise MarketplaceWorkflowError("user must be PENDING")

            user = deepcopy(existing)
            user.status = UserStatus.ACTIVE
            user.updated_at = datetime.now(UTC)

            try:
                self.user_repository.save(user)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("user not found") from exc

            return user

        return self.user_service.activate(user_id)

    def get_user(self, user_id: UUID) -> User:
        if self._use_repositories():
            try:
                return self.user_repository.get(user_id)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("user not found") from exc
        return self.user_service.get_user(user_id)

    def get_listing(self, listing_id: UUID) -> Listing:
        if self._use_repositories():
            try:
                return self.listing_repository.get(listing_id)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("listing not found") from exc
        return self.listing_service.get_listing(listing_id)

    def get_reservation(self, reservation_id: UUID) -> Reservation:
        if self._use_repositories():
            try:
                return self.reservation_repository.get(reservation_id)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("reservation not found") from exc
        return self.reservation_service.get_reservation(reservation_id)

    def create_listing_for_user(
        self,
        seller_id: UUID,
        title: str,
        description: str,
        category: str,
        condition: ItemCondition,
        price: Decimal,
        currency: str,
        location: str,
    ) -> Listing:
        if self._use_repositories():
            try:
                seller = self.user_repository.get(seller_id)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("seller not found") from exc

            if seller.status != UserStatus.ACTIVE:
                raise MarketplaceWorkflowError("seller must be ACTIVE")

            listing = Listing(
                id=uuid4(),
                seller_id=seller_id,
                title=title,
                description=description,
                category=category,
                condition=condition,
                price=price,
                currency=currency,
                location=location,
            )
            self.listing_repository.add(listing)
            self._record_event(
                "commerce.listing.created",
                "Listing",
                listing.id,
                {
                    "id": str(listing.id),
                    "seller_id": str(listing.seller_id),
                    "title": listing.title,
                    "price": str(listing.price),
                    "currency": listing.currency,
                },
            )
            return listing

        try:
            seller = self.user_service.get_user(seller_id)
        except Exception:
            raise MarketplaceWorkflowError("seller not found")
        if seller.status.name != "ACTIVE":
            raise MarketplaceWorkflowError("seller must be ACTIVE")

        listing = self.listing_service.create_listing(
            seller_id, title, description, category, condition, price, currency, location
        )
        self._record_event(
            "commerce.listing.created",
            "Listing",
            listing.id,
            {
                "id": str(listing.id),
                "seller_id": str(listing.seller_id),
                "title": listing.title,
                "price": str(listing.price),
                "currency": listing.currency,
            },
        )
        return listing

    def publish_listing(self, seller_id: UUID, listing_id: UUID) -> Listing:
        if self._use_repositories():
            try:
                seller = self.user_repository.get(seller_id)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("seller not found") from exc

            if seller.status != UserStatus.ACTIVE:
                raise MarketplaceWorkflowError("seller must be ACTIVE")

            try:
                listing = self.listing_repository.get(listing_id)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("listing not found") from exc

            if listing.seller_id != seller_id:
                raise MarketplaceWorkflowError("seller does not own listing")
            if listing.status != ListingStatus.DRAFT:
                raise MarketplaceWorkflowError("cannot publish listing")

            # Check minimum image requirement
            if self.media_service:
                images = self.media_service.get_listing_images(listing_id)
                if len(images) < 2:
                    raise MarketplaceWorkflowError("listing must have at least 2 images to publish")

            publish_candidate = deepcopy(listing)
            publish_candidate.status = ListingStatus.PUBLISHED
            publish_candidate.updated_at = datetime.now(UTC)
            self.listing_repository.save(publish_candidate)
            published = publish_candidate
        else:
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

            # Check minimum image requirement
            if self.media_service:
                images = self.media_service.get_listing_images(listing_id)
                if len(images) < 2:
                    raise MarketplaceWorkflowError("listing must have at least 2 images to publish")

            try:
                published = self.listing_service.publish(listing_id)
            except Exception as e:
                raise MarketplaceWorkflowError("cannot publish listing") from e

        self._record_event(
            "commerce.listing.published",
            "Listing",
            published.id,
            {"id": str(published.id), "seller_id": str(published.seller_id)},
        )
        return published

    def create_reservation(self, buyer_id: UUID, listing_id: UUID) -> Reservation:
        if self._use_repositories():
            try:
                buyer = self.user_repository.get(buyer_id)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("buyer not found") from exc
            if buyer.status != UserStatus.ACTIVE:
                raise MarketplaceWorkflowError("buyer must be ACTIVE")

            try:
                listing = self.listing_repository.get(listing_id)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("listing not found") from exc

            try:
                seller = self.user_repository.get(listing.seller_id)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("seller not found") from exc
            if seller.status != UserStatus.ACTIVE:
                raise MarketplaceWorkflowError("seller must be ACTIVE")

            if buyer_id == listing.seller_id:
                raise MarketplaceWorkflowError("buyer cannot be the seller")
            if listing.status != ListingStatus.PUBLISHED:
                raise MarketplaceWorkflowError("listing must be PUBLISHED to reserve")

            reservation = Reservation(
                id=uuid4(),
                listing_id=listing_id,
                buyer_id=buyer_id,
                seller_id=seller.id,
            )
            self.reservation_repository.add(reservation)
            self._record_event(
                "commerce.reservation.created",
                "Reservation",
                reservation.id,
                {
                    "id": str(reservation.id),
                    "listing_id": str(reservation.listing_id),
                    "buyer_id": str(reservation.buyer_id),
                },
            )
            return reservation

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

        if listing.status.name != "PUBLISHED":
            raise MarketplaceWorkflowError("listing must be PUBLISHED to reserve")

        try:
            reservation = self.reservation_service.create_reservation(listing_id, buyer_id, seller_id)
        except Exception as e:
            raise MarketplaceWorkflowError("cannot create reservation") from e

        self._record_event(
            "commerce.reservation.created",
            "Reservation",
            reservation.id,
            {
                "id": str(reservation.id),
                "listing_id": str(reservation.listing_id),
                "buyer_id": str(reservation.buyer_id),
            },
        )
        return reservation

    def accept_reservation(self, reservation_id: UUID, seller_id: UUID) -> Reservation:
        if self._use_repositories():
            try:
                seller = self.user_repository.get(seller_id)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("seller not found") from exc
            if seller.status != UserStatus.ACTIVE:
                raise MarketplaceWorkflowError("seller must be ACTIVE")

            try:
                reservation = self.reservation_repository.get(reservation_id)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("reservation not found") from exc

            if reservation.seller_id != seller_id:
                raise MarketplaceWorkflowError("seller does not own this reservation")
            if reservation.status != ReservationStatus.PENDING:
                raise MarketplaceWorkflowError("reservation must be PENDING to accept")

            for existing in self.reservation_repository.all():
                if existing.listing_id == reservation.listing_id and existing.status == ReservationStatus.ACCEPTED:
                    raise MarketplaceWorkflowError("another reservation already accepted for this listing")

            old_status = reservation.status
            accepted = deepcopy(reservation)
            accepted.status = ReservationStatus.ACCEPTED
            accepted.updated_at = datetime.now(UTC)
            self.reservation_repository.save(accepted)

            try:
                listing = self.listing_repository.get(reservation.listing_id)
                reserved = deepcopy(listing)
                reserved.status = ListingStatus.RESERVED
                reserved.updated_at = datetime.now(UTC)
                self.listing_repository.save(reserved)
            except Exception as exc:
                rollback = deepcopy(accepted)
                rollback.status = old_status
                rollback.updated_at = datetime.now(UTC)
                try:
                    self.reservation_repository.save(rollback)
                except Exception:
                    pass
                raise MarketplaceWorkflowError("cannot reserve listing; rolled back reservation") from exc

            self._record_event(
                "commerce.reservation.accepted",
                "Reservation",
                reservation_id,
                {"id": str(reservation_id), "listing_id": str(reservation.listing_id)},
            )
            self._record_event(
                "commerce.listing.reserved",
                "Listing",
                reservation.listing_id,
                {"id": str(reservation.listing_id), "reserved_by": str(reservation.buyer_id)},
            )
            return self.reservation_repository.get(reservation_id)

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

        for r in self.reservation_service._store.values():
            if r.listing_id == reservation.listing_id and r.status.name == "ACCEPTED":
                raise MarketplaceWorkflowError("another reservation already accepted for this listing")

        old_status = reservation.status
        try:
            self.reservation_service.accept(reservation_id)
        except Exception as e:
            raise MarketplaceWorkflowError("cannot accept reservation") from e

        try:
            self.listing_service.reserve(reservation.listing_id)
        except Exception as e:
            if reservation_id in self.reservation_service._store:
                stored = self.reservation_service._store[reservation_id]
                stored.status = old_status
                stored.updated_at = datetime.now(UTC)
                self.reservation_service._store[reservation_id] = stored
            raise MarketplaceWorkflowError("cannot reserve listing; rolled back reservation") from e

        self._record_event(
            "commerce.reservation.accepted",
            "Reservation",
            reservation_id,
            {"id": str(reservation_id), "listing_id": str(reservation.listing_id)},
        )
        self._record_event(
            "commerce.listing.reserved",
            "Listing",
            reservation.listing_id,
            {"id": str(reservation.listing_id), "reserved_by": str(reservation.buyer_id)},
        )

        return self.reservation_service.get_reservation(reservation_id)

    def cancel_reservation(self, reservation_id: UUID) -> Reservation:
        """Cancel a reservation and restore listing availability when appropriate.

        Works with repository-backed or in-memory services.
        """
        if self._use_repositories():
            try:
                reservation = self.reservation_repository.get(reservation_id)
            except EntityNotFoundError as exc:
                raise MarketplaceWorkflowError("reservation not found") from exc

            # Only allow cancelling from PENDING or ACCEPTED
            if reservation.status not in {ReservationStatus.PENDING, ReservationStatus.ACCEPTED}:
                raise MarketplaceWorkflowError("Can only cancel PENDING or ACCEPTED reservations")

            old_status = reservation.status
            cancelled = deepcopy(reservation)
            cancelled.status = ReservationStatus.CANCELLED
            cancelled.updated_at = datetime.now(UTC)
            try:
                self.reservation_repository.save(cancelled)
            except Exception as exc:
                raise MarketplaceWorkflowError("cannot cancel reservation") from exc

            # If reservation was ACCEPTED, and no other ACCEPTED reservations exist for the listing,
            # restore listing to PUBLISHED when it is currently RESERVED.
            try:
                if old_status == ReservationStatus.ACCEPTED:
                    others = [r for r in self.reservation_repository.all() if r.listing_id == reservation.listing_id and r.status == ReservationStatus.ACCEPTED]
                    if not others:
                        listing = self.listing_repository.get(reservation.listing_id)
                        if listing.status == ListingStatus.RESERVED:
                            restored = deepcopy(listing)
                            restored.status = ListingStatus.PUBLISHED
                            restored.updated_at = datetime.now(UTC)
                            self.listing_repository.save(restored)
                            self._record_event(
                                "commerce.listing.published",
                                "Listing",
                                restored.id,
                                {"id": str(restored.id), "seller_id": str(restored.seller_id)},
                            )
            except Exception:
                # best-effort restoration; do not fail the cancel operation
                pass

            self._record_event(
                "commerce.reservation.cancelled",
                "Reservation",
                reservation_id,
                {"id": str(reservation_id), "listing_id": str(reservation.listing_id)},
            )
            return self.reservation_repository.get(reservation_id)

        # In-memory services
        try:
            reservation = self.reservation_service.get_reservation(reservation_id)
        except Exception:
            raise MarketplaceWorkflowError("reservation not found")

        if reservation.status.name not in {"PENDING", "ACCEPTED"}:
            raise MarketplaceWorkflowError("Can only cancel PENDING or ACCEPTED reservations")

        old_status = reservation.status
        try:
            result = self.reservation_service.cancel(reservation_id)
        except Exception as exc:
            raise MarketplaceWorkflowError("cannot cancel reservation") from exc

        # restore listing if needed
        try:
            if old_status.name == "ACCEPTED":
                others = [r for r in self.reservation_service._store.values() if r.listing_id == reservation.listing_id and r.status.name == "ACCEPTED"]
                if not others:
                    listing = self.listing_service.get_listing(reservation.listing_id)
                    if listing.status == ListingStatus.RESERVED:
                        listing.status = ListingStatus.PUBLISHED
                        listing.updated_at = datetime.now(UTC)
                        self.listing_service._store[listing.id] = listing
                        self._record_event(
                            "commerce.listing.published",
                            "Listing",
                            listing.id,
                            {"id": str(listing.id), "seller_id": str(listing.seller_id)},
                        )
        except Exception:
            pass

        self._record_event(
            "commerce.reservation.cancelled",
            "Reservation",
            reservation_id,
            {"id": str(reservation_id), "listing_id": str(reservation.listing_id)},
        )
        return result
