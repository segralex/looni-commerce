from __future__ import annotations

from typing import Any, Optional
from uuid import UUID
from datetime import datetime

from domain.repositories import EntityNotFoundError, DuplicateEntityError, ReservationRepository
from domain.reservations.models import Reservation, ReservationStatus
from .database import Database


class SQLiteReservationRepository(ReservationRepository):
    def __init__(self, db: Database):
        self.db = db

    def add(self, entity: Any) -> None:
        conn = self.db.connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO reservations (id, listing_id, buyer_id, seller_id, status, expires_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    str(entity.id),
                    str(entity.listing_id),
                    str(entity.buyer_id),
                    str(entity.seller_id),
                    entity.status.value,
                    entity.expires_at.isoformat() if entity.expires_at is not None else None,
                    entity.created_at.isoformat(),
                    entity.updated_at.isoformat(),
                ),
            )
            conn.commit()
        except Exception as exc:
            raise DuplicateEntityError("Duplicate entity id") from exc

    def get(self, entity_id: UUID) -> Any:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM reservations WHERE id = ?", (str(entity_id),))
        row = cur.fetchone()
        if row is None:
            raise EntityNotFoundError("Entity not found")
        expires_at = row["expires_at"]
        return Reservation(
            id=UUID(row["id"]),
            listing_id=UUID(row["listing_id"]),
            buyer_id=UUID(row["buyer_id"]),
            seller_id=UUID(row["seller_id"]),
            status=ReservationStatus(row["status"]),
            expires_at=datetime.fromisoformat(expires_at) if expires_at is not None else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save(self, entity: Any) -> None:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM reservations WHERE id = ?", (str(entity.id),))
        if cur.fetchone() is None:
            raise EntityNotFoundError("Unknown entity id")
        cur.execute(
            "UPDATE reservations SET listing_id=?, buyer_id=?, seller_id=?, status=?, expires_at=?, created_at=?, updated_at=? WHERE id=?",
            (
                str(entity.listing_id),
                str(entity.buyer_id),
                str(entity.seller_id),
                entity.status.value,
                entity.expires_at.isoformat() if entity.expires_at is not None else None,
                entity.created_at.isoformat(),
                entity.updated_at.isoformat(),
                str(entity.id),
            ),
        )
        conn.commit()

    def all(self) -> tuple[Any, ...]:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM reservations ORDER BY rowid ASC")
        rows = cur.fetchall()
        result = []
        for row in rows:
            expires_at = row["expires_at"]
            result.append(
                Reservation(
                    id=UUID(row["id"]),
                    listing_id=UUID(row["listing_id"]),
                    buyer_id=UUID(row["buyer_id"]),
                    seller_id=UUID(row["seller_id"]),
                    status=ReservationStatus(row["status"]),
                    expires_at=datetime.fromisoformat(expires_at) if expires_at is not None else None,
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            )
        return tuple(result)
