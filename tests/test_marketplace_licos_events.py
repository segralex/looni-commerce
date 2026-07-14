import sys
import os
from uuid import uuid4
from datetime import UTC

# Ensure licos-core is importable when running tests from looni-commerce
LICOS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "200_LICOS", "licos-core"))
if os.path.isdir(LICOS_ROOT) and LICOS_ROOT not in sys.path:
    sys.path.insert(0, LICOS_ROOT)

from kernel.events.store import EventStore
from kernel.integration.recorder import EventRecorder

from domain.users.service import UserService
from domain.listings.service import ListingService
from domain.reservations.service import ReservationService
from application.marketplace.service import MarketplaceService, MarketplaceWorkflowError
from domain.listings.models import ItemCondition

def test_listing_creation_records_event():
    store = EventStore()
    recorder = EventRecorder(store)
    us = UserService(); ls = ListingService(); rs = ReservationService()
    mp = MarketplaceService(user_service=us, listing_service=ls, reservation_service=rs, event_recorder=recorder)

    seller = us.create_user("S", "s@example.com"); us.activate(seller.id)
    listing = mp.create_listing_for_user(seller.id, "T", "D", "C", ItemCondition.GOOD, "1.00", "USD", "L")

    events = store.events_for_aggregate(listing.id)
    assert len(events) == 1
    assert events[0].event_type == "commerce.listing.created"
    assert events[0].aggregate_type == "Listing"
    assert events[0].aggregate_id == listing.id


def test_publish_records_event():
    store = EventStore(); recorder = EventRecorder(store)
    us = UserService(); ls = ListingService(); rs = ReservationService()
    mp = MarketplaceService(user_service=us, listing_service=ls, reservation_service=rs, event_recorder=recorder)

    seller = us.create_user("S", "s@example.com"); us.activate(seller.id)
    listing = ls.create_listing(seller.id, "T", "D", "C", ItemCondition.GOOD, "1.00", "USD", "L")
    mp.publish_listing(seller.id, listing.id)

    events = store.events_for_aggregate(listing.id)
    assert any(e.event_type == "commerce.listing.published" for e in events)


def test_reservation_creation_records_event():
    store = EventStore(); recorder = EventRecorder(store)
    us = UserService(); ls = ListingService(); rs = ReservationService()
    mp = MarketplaceService(user_service=us, listing_service=ls, reservation_service=rs, event_recorder=recorder)

    seller = us.create_user("S", "s@example.com"); buyer = us.create_user("B", "b@example.com")
    us.activate(seller.id); us.activate(buyer.id)
    listing = ls.create_listing(seller.id, "T", "D", "C", ItemCondition.GOOD, "1.00", "USD", "L")
    ls.publish(listing.id)

    res = mp.create_reservation(buyer.id, listing.id)
    events = store.events_for_aggregate(res.id)
    assert len(events) == 1
    assert events[0].event_type == "commerce.reservation.created"
    assert events[0].aggregate_type == "Reservation"


def test_accept_reservation_records_both_events_in_order():
    store = EventStore(); recorder = EventRecorder(store)
    us = UserService(); ls = ListingService(); rs = ReservationService()
    mp = MarketplaceService(user_service=us, listing_service=ls, reservation_service=rs, event_recorder=recorder)

    seller = us.create_user("S", "s@example.com"); b1 = us.create_user("B1", "b1@example.com")
    us.activate(seller.id); us.activate(b1.id)
    listing = ls.create_listing(seller.id, "T", "D", "C", ItemCondition.GOOD, "1.00", "USD", "L")
    ls.publish(listing.id)
    r = mp.create_reservation(b1.id, listing.id)

    mp.accept_reservation(r.id, seller.id)

    # reservation events
    res_events = store.events_for_aggregate(r.id)
    assert any(e.event_type == "commerce.reservation.accepted" for e in res_events)

    # listing events; ensure reserved event exists and the ordering of global store
    all_events = store.all_events()
    types = [e.event_type for e in all_events]
    # look for sequence ... reservation.accepted, listing.reserved ...
    assert "commerce.reservation.accepted" in types
    assert "commerce.listing.reserved" in types
    assert types.index("commerce.reservation.accepted") < types.index("commerce.listing.reserved")


def test_failed_workflow_emits_no_event():
    store = EventStore(); recorder = EventRecorder(store)
    us = UserService(); ls = ListingService(); rs = ReservationService()
    mp = MarketplaceService(user_service=us, listing_service=ls, reservation_service=rs, event_recorder=recorder)

    seller = us.create_user("S", "s@example.com"); b1 = us.create_user("B1", "b1@example.com")
    us.activate(seller.id); us.activate(b1.id)
    listing = ls.create_listing(seller.id, "T", "D", "C", ItemCondition.GOOD, "1.00", "USD", "L")
    ls.publish(listing.id)
    r = mp.create_reservation(b1.id, listing.id)

    # force listing.reserve to fail
    original_reserve = ls.reserve

    def fail_reserve(_):
        raise Exception("boom")

    ls.reserve = fail_reserve
    try:
        try:
            mp.accept_reservation(r.id, seller.id)
        except MarketplaceWorkflowError:
            pass
    finally:
        ls.reserve = original_reserve

    # ensure no accepted or reserved events recorded
    types = [e.event_type for e in store.all_events()]
    assert "commerce.reservation.accepted" not in types
    assert "commerce.listing.reserved" not in types