#!/usr/bin/env python3
"""Simple CLI demo that exercises the marketplace workflow and prints LICOS events.

This demo uses the in-repo domain and application services plus LICOS EventRecorder
located in the sibling `200_LICOS/licos-core` workspace directory.
"""
from decimal import Decimal
import os
import sys
from uuid import uuid4
from datetime import UTC

# Make licos-core importable when running from this repo
LICOS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "200_LICOS", "licos-core"))
if os.path.isdir(LICOS_ROOT) and LICOS_ROOT not in sys.path:
    sys.path.insert(0, LICOS_ROOT)

# Make the looni-commerce repo root importable so `domain` and `application` packages resolve
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from kernel.events.store import EventStore
from kernel.integration.recorder import EventRecorder

from domain.users.service import UserService
from domain.listings.service import ListingService
from domain.reservations.service import ReservationService
from application.marketplace.service import MarketplaceService
from domain.search.service import SearchService
from domain.search.models import SearchQuery
from domain.listings.models import ItemCondition


def checkmark(ok: bool) -> str:
    return "✓" if ok else "✗"


def main() -> None:
    print("====================================")
    print("LOONI COMMERCE DEMO")
    print("====================================\n")

    # 1-3 create store, recorder, marketplace service
    store = EventStore()
    recorder = EventRecorder(store)
    us = UserService()
    ls = ListingService()
    rs = ReservationService()
    mp = MarketplaceService(user_service=us, listing_service=ls, reservation_service=rs, event_recorder=recorder)

    # 4-7 create and activate seller and buyer
    print("Creating seller...")
    seller = us.create_user("Seller", "seller@example.com")
    us.activate(seller.id)
    print(checkmark(True), "\n")

    print("Creating buyer...")
    buyer = us.create_user("Buyer", "buyer@example.com")
    us.activate(buyer.id)
    print(checkmark(True), "\n")

    # 8 Create listing
    print("Creating listing...")
    listing = mp.create_listing_for_user(
        seller.id,
        "Example Item",
        "An example listing used in demo.",
        "examples",
        ItemCondition.GOOD,
        Decimal("9.99"),
        "USD",
        "DemoTown",
    )
    print(checkmark(True), "\n")

    # 9 Publish listing
    print("Publishing listing...")
    mp.publish_listing(seller.id, listing.id)
    print(checkmark(True), "\n")

    # 10 Search returns published listing
    print("Searching...\n")
    ss = SearchService()
    results = ss.search([ls.get_listing(listing.id)], SearchQuery())
    print(f"Found {len(results)} listing\n")

    # 11 Create reservation
    print("Creating reservation...")
    reservation = mp.create_reservation(buyer.id, listing.id)
    print(checkmark(True), "\n")

    # 12 Accept reservation
    print("Accepting reservation...")
    mp.accept_reservation(reservation.id, seller.id)
    print(checkmark(True), "\n")

    # 13 Print final listing status
    final_listing = ls.get_listing(listing.id)
    print("Listing Status:")
    print(final_listing.status.name, "\n")

    # 14 Print final reservation status
    final_res = rs.get_reservation(reservation.id)
    print("Reservation Status:")
    print(final_res.status.name, "\n")

    # 15 Print events in chronological order
    print("Recorded LICOS Events\n")
    for i, e in enumerate(store.all_events(), start=1):
        print(f"{i}.")
        print(e.event_type)
        print()

    print("Demo completed successfully.")


if __name__ == "__main__":
    main()
