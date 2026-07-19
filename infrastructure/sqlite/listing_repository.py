from __future__ import annotations

from typing import Any
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from domain.repositories import EntityNotFoundError, DuplicateEntityError, ListingRepository
from domain.listings.models import Listing, ListingStatus, ItemCondition
from .database import Database


class SQLiteListingRepository(ListingRepository):
    def __init__(self, db: Database):
        self.db = db

    def _sync_search_index(self, conn, listing: Listing) -> None:
        cur = conn.cursor()
        cur.execute("DELETE FROM listing_search_fts WHERE listing_id = ?", (str(listing.id),))
        if listing.status != ListingStatus.PUBLISHED:
            return

        cur.execute(
            """
            INSERT INTO listing_search_fts (
                listing_id,
                seller_id,
                status,
                category,
                condition,
                location,
                price,
                currency,
                title,
                description,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(listing.id),
                str(listing.seller_id),
                listing.status.value,
                listing.category,
                listing.condition.value,
                listing.location,
                str(listing.price),
                listing.currency,
                listing.title,
                listing.description,
                listing.created_at.isoformat(),
            ),
        )

    def add(self, entity: Any) -> None:
        conn = self.db.connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO listings (id, seller_id, title, description, category, condition, price, currency, location, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    str(entity.id),
                    str(entity.seller_id),
                    entity.title,
                    entity.description,
                    entity.category,
                    entity.condition.value,
                    str(entity.price),
                    entity.currency,
                    entity.location,
                    entity.status.value,
                    entity.created_at.isoformat(),
                    entity.updated_at.isoformat(),
                ),
            )
            self._sync_search_index(conn, entity)
            conn.commit()
        except Exception as exc:
            raise DuplicateEntityError("Duplicate entity id") from exc

    def get(self, entity_id: UUID) -> Any:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM listings WHERE id = ?", (str(entity_id),))
        row = cur.fetchone()
        if row is None:
            raise EntityNotFoundError("Entity not found")
        return Listing(
            id=UUID(row["id"]),
            seller_id=UUID(row["seller_id"]),
            title=row["title"],
            description=row["description"],
            category=row["category"],
            condition=ItemCondition(row["condition"]),
            price=Decimal(row["price"]),
            currency=row["currency"],
            location=row["location"],
            status=ListingStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save(self, entity: Any) -> None:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM listings WHERE id = ?", (str(entity.id),))
        if cur.fetchone() is None:
            raise EntityNotFoundError("Unknown entity id")
        cur.execute(
            "UPDATE listings SET seller_id=?, title=?, description=?, category=?, condition=?, price=?, currency=?, location=?, status=?, created_at=?, updated_at=? WHERE id=?",
            (
                str(entity.seller_id),
                entity.title,
                entity.description,
                entity.category,
                entity.condition.value,
                str(entity.price),
                entity.currency,
                entity.location,
                entity.status.value,
                entity.created_at.isoformat(),
                entity.updated_at.isoformat(),
                str(entity.id),
            ),
        )
        self._sync_search_index(conn, entity)
        conn.commit()

    def all(self) -> tuple[Any, ...]:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM listings ORDER BY rowid ASC")
        rows = cur.fetchall()
        result = []
        for row in rows:
            result.append(
                Listing(
                    id=UUID(row["id"]),
                    seller_id=UUID(row["seller_id"]),
                    title=row["title"],
                    description=row["description"],
                    category=row["category"],
                    condition=ItemCondition(row["condition"]),
                    price=Decimal(row["price"]),
                    currency=row["currency"],
                    location=row["location"],
                    status=ListingStatus(row["status"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            )
        return tuple(result)
