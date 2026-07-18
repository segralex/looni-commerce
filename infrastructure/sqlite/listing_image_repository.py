from __future__ import annotations

from datetime import datetime
from uuid import UUID

from domain.listings.images import ListingImage
from domain.listings.repositories import ListingImageRepository

from .database import Database


class SQLiteListingImageRepository(ListingImageRepository):
    def __init__(self, db: Database):
        self.db = db

    def store(self, image: ListingImage) -> None:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO listing_images
            (id, listing_id, filename, content_type, size_bytes, position, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(image.id),
                str(image.listing_id),
                image.filename,
                image.content_type,
                image.size_bytes,
                image.position,
                image.created_at.isoformat(),
            ),
        )
        conn.commit()

    def get_by_id(self, image_id: UUID) -> ListingImage | None:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM listing_images WHERE id = ?", (str(image_id),))
        row = cur.fetchone()
        if row is None:
            return None
        return ListingImage(
            id=UUID(row["id"]),
            listing_id=UUID(row["listing_id"]),
            filename=row["filename"],
            content_type=row["content_type"],
            size_bytes=int(row["size_bytes"]),
            position=int(row["position"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def get_by_listing(self, listing_id: UUID) -> list[ListingImage]:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM listing_images WHERE listing_id = ? ORDER BY position ASC, rowid ASC",
            (str(listing_id),),
        )
        rows = cur.fetchall()
        return [
            ListingImage(
                id=UUID(row["id"]),
                listing_id=UUID(row["listing_id"]),
                filename=row["filename"],
                content_type=row["content_type"],
                size_bytes=int(row["size_bytes"]),
                position=int(row["position"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def delete_by_id(self, image_id: UUID) -> bool:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM listing_images WHERE id = ?", (str(image_id),))
        conn.commit()
        return cur.rowcount > 0

    def count_by_listing(self, listing_id: UUID) -> int:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS count FROM listing_images WHERE listing_id = ?", (str(listing_id),))
        row = cur.fetchone()
        return int(row["count"])