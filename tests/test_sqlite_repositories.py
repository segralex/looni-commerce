import os
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

LICOS_ROOT = Path(__file__).resolve().parents[3] / "200_LICOS" / "licos-core"
if LICOS_ROOT.is_dir() and str(LICOS_ROOT) not in sys.path:
    sys.path.insert(0, str(LICOS_ROOT))

from infrastructure.sqlite.database import Database
from infrastructure.sqlite.user_repository import SQLiteUserRepository
from infrastructure.sqlite.listing_repository import SQLiteListingRepository
from infrastructure.sqlite.reservation_repository import SQLiteReservationRepository

from kernel.events.store import EventStore
from kernel.integration.recorder import EventRecorder
from application.marketplace.service import MarketplaceService
from domain.listings.models import ItemCondition


def make_sqlite(path):
    db = Database(path)
    user_repo = SQLiteUserRepository(db)
    listing_repo = SQLiteListingRepository(db)
    reservation_repo = SQLiteReservationRepository(db)
    return db, user_repo, listing_repo, reservation_repo


def test_sqlite_basic_persistence_and_marketplace_integration(tmp_path):
    dbfile = tmp_path / "test_sqlite.db"
    dbpath = str(dbfile)

    # create and use repos
    db, user_repo, listing_repo, reservation_repo = make_sqlite(dbpath)

    store = EventStore()
    recorder = EventRecorder(store)
    mp = MarketplaceService(
        user_repository=user_repo,
        listing_repository=listing_repo,
        reservation_repository=reservation_repo,
        event_recorder=recorder,
    )

    # create users and listing and reservation via marketplace
    seller = mp.create_user("Seller", "seller@example.com")
    buyer = mp.create_user("Buyer", "buyer@example.com")
    mp.activate_user(seller.id)
    mp.activate_user(buyer.id)

    listing = mp.create_listing_for_user(
        seller.id, "Book", "A book", "Books", ItemCondition.GOOD, Decimal("12.50"), "USD", "Online"
    )

    # publish and reserve
    mp.publish_listing(seller.id, listing.id)
    reservation = mp.create_reservation(buyer.id, listing.id)

    # accept
    mp.accept_reservation(reservation.id, seller.id)

    # close connection and reopen to test persistence
    db.close()

    db2 = Database(dbpath)
    user_repo2 = SQLiteUserRepository(db2)
    listing_repo2 = SQLiteListingRepository(db2)
    reservation_repo2 = SQLiteReservationRepository(db2)

    # retrieve persisted entities
    u = user_repo2.get(seller.id)
    assert u.email == "seller@example.com"
    l = listing_repo2.get(listing.id)
    assert l.status.name in {"PUBLISHED", "RESERVED", "SOLD", "ARCHIVED"}
    r = reservation_repo2.get(reservation.id)
    assert r.buyer_id == buyer.id
