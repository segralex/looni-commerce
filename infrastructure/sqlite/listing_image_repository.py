from __future__ import annotations

from datetime import datetime
from uuid import UUID

from domain.listings.images import ListingImage
from domain.listings.repositories import ListingImageRepository
from domain.media.processing import ImageProcessingStatus, infer_processing_status

from .database import Database


class SQLiteListingImageRepository(ListingImageRepository):
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _hydrate(row) -> ListingImage:
        thumbnail_small = row["thumbnail_small_key"] if "thumbnail_small_key" in row.keys() else None
        thumbnail_medium = row["thumbnail_medium_key"] if "thumbnail_medium_key" in row.keys() else None
        thumbnail_large = row["thumbnail_large_key"] if "thumbnail_large_key" in row.keys() else None
        status_value = row["processing_status"] if "processing_status" in row.keys() else None
        attempts = int(row["processing_attempts"]) if "processing_attempts" in row.keys() and row["processing_attempts"] is not None else 0
        error = row["processing_error"] if "processing_error" in row.keys() else None
        if status_value is None:
            processing_status = infer_processing_status(all([thumbnail_small, thumbnail_medium, thumbnail_large]))
        else:
            processing_status = ImageProcessingStatus(status_value)
        return ListingImage(
            id=UUID(row["id"]),
            listing_id=UUID(row["listing_id"]),
            filename=row["filename"],
            content_type=row["content_type"],
            size_bytes=int(row["size_bytes"]),
            position=int(row["position"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            thumbnail_small=thumbnail_small,
            thumbnail_medium=thumbnail_medium,
            thumbnail_large=thumbnail_large,
            processing_status=processing_status,
            processing_error=error,
            processing_attempts=attempts,
        )

    def _get_listing_rows(self, conn, listing_id: UUID):
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM listing_images WHERE listing_id = ? ORDER BY position ASC, rowid ASC",
            (str(listing_id),),
        )
        return cur.fetchall()

    def _compact_listing_positions(self, conn, listing_id: UUID) -> None:
        rows = self._get_listing_rows(conn, listing_id)
        for index, row in enumerate(rows, start=1):
            conn.execute(
                "UPDATE listing_images SET position = ? WHERE id = ?",
                (index, row["id"]),
            )

    def store(
        self,
        image: ListingImage,
        storage_key: str | None = None,
        thumbnail_small_key: str | None = None,
        thumbnail_medium_key: str | None = None,
        thumbnail_large_key: str | None = None,
    ) -> None:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO listing_images
            (
                id,
                listing_id,
                filename,
                content_type,
                size_bytes,
                position,
                storage_key,
                thumbnail_small_key,
                thumbnail_medium_key,
                thumbnail_large_key,
                processing_status,
                processing_error,
                processing_attempts,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(image.id),
                str(image.listing_id),
                image.filename,
                image.content_type,
                image.size_bytes,
                image.position,
                storage_key,
                thumbnail_small_key,
                thumbnail_medium_key,
                thumbnail_large_key,
                image.processing_status.value,
                image.processing_error,
                image.processing_attempts,
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
        return self._hydrate(row)

    def get_by_listing(self, listing_id: UUID) -> list[ListingImage]:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM listing_images WHERE listing_id = ? ORDER BY position ASC, rowid ASC",
            (str(listing_id),),
        )
        rows = cur.fetchall()
        return [self._hydrate(row) for row in rows]

    def get_storage_key(self, image_id: UUID) -> str | None:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT storage_key FROM listing_images WHERE id = ?", (str(image_id),))
        row = cur.fetchone()
        if row is None:
            return None
        return row["storage_key"]

    def get_thumbnail_key(self, image_id: UUID, size: str) -> str | None:
        column = {
            "small": "thumbnail_small_key",
            "medium": "thumbnail_medium_key",
            "large": "thumbnail_large_key",
        }.get(size)
        if column is None:
            raise ValueError("thumbnail size must be one of: small, medium, large")

        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute(f"SELECT {column} FROM listing_images WHERE id = ?", (str(image_id),))
        row = cur.fetchone()
        if row is None:
            return None
        return row[column]

    def delete_by_id(self, image_id: UUID) -> bool:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT listing_id FROM listing_images WHERE id = ?", (str(image_id),))
        row = cur.fetchone()
        if row is None:
            return False

        listing_id = UUID(row["listing_id"])
        try:
            cur.execute("DELETE FROM listing_images WHERE id = ?", (str(image_id),))
            self._compact_listing_positions(conn, listing_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return True

    def get(self, image_id: UUID) -> ListingImage | None:
        return self.get_by_id(image_id)

    def claim_for_processing(self, image_id: UUID, max_attempts: int) -> ListingImage | None:
        conn = self.db.connect()
        cur = conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            cur.execute("SELECT * FROM listing_images WHERE id = ?", (str(image_id),))
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                return None

            image = self._hydrate(row)
            if image.processing_status == ImageProcessingStatus.READY:
                conn.rollback()
                return None
            if image.processing_status == ImageProcessingStatus.PROCESSING:
                conn.rollback()
                return None
            if image.processing_attempts >= max_attempts:
                conn.rollback()
                return None

            next_attempt = image.processing_attempts + 1
            cur.execute(
                """
                UPDATE listing_images
                SET processing_status = 'PROCESSING',
                    processing_attempts = ?
                WHERE id = ?
                """,
                (next_attempt, str(image_id)),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        claimed = self.get_by_id(image_id)
        return claimed

    def mark_ready(self, image_id: UUID, thumbnails: dict[str, str]) -> ListingImage | None:
        conn = self.db.connect()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE listing_images
                SET thumbnail_small_key = ?,
                    thumbnail_medium_key = ?,
                    thumbnail_large_key = ?,
                    processing_status = 'READY',
                    processing_error = NULL
                WHERE id = ?
                """,
                (
                    thumbnails.get("small"),
                    thumbnails.get("medium"),
                    thumbnails.get("large"),
                    str(image_id),
                ),
            )
            if cur.rowcount == 0:
                conn.rollback()
                return None
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return self.get_by_id(image_id)

    def mark_failed(self, image_id: UUID, error: str) -> ListingImage | None:
        conn = self.db.connect()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE listing_images
                SET processing_status = 'FAILED',
                    processing_error = ?
                WHERE id = ?
                """,
                (error, str(image_id)),
            )
            if cur.rowcount == 0:
                conn.rollback()
                return None
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return self.get_by_id(image_id)

    def count_ready_by_listing(self, listing_id: UUID) -> int:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS count FROM listing_images WHERE listing_id = ? AND processing_status = 'READY'",
            (str(listing_id),),
        )
        row = cur.fetchone()
        return int(row["count"])

    def reorder_for_listing(
        self,
        listing_id: UUID,
        ordered_image_ids: list[UUID],
    ) -> list[ListingImage]:
        if len(ordered_image_ids) != len(set(ordered_image_ids)):
            raise ValueError("image_ids must not contain duplicates")

        conn = self.db.connect()
        current_rows = self._get_listing_rows(conn, listing_id)
        current_ids = [UUID(row["id"]) for row in current_rows]
        if current_ids or ordered_image_ids:
            if len(current_ids) != len(ordered_image_ids) or set(current_ids) != set(ordered_image_ids):
                raise ValueError("image_ids must contain every current image exactly once")

        try:
            temp_offset = 100
            for index, image_id in enumerate(ordered_image_ids, start=1):
                conn.execute(
                    "UPDATE listing_images SET position = ? WHERE id = ? AND listing_id = ?",
                    (temp_offset + index, str(image_id), str(listing_id)),
                )
            for index, image_id in enumerate(ordered_image_ids, start=1):
                conn.execute(
                    "UPDATE listing_images SET position = ? WHERE id = ? AND listing_id = ?",
                    (index, str(image_id), str(listing_id)),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        return self.get_by_listing(listing_id)

    def count_by_listing(self, listing_id: UUID) -> int:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS count FROM listing_images WHERE listing_id = ?", (str(listing_id),))
        row = cur.fetchone()
        return int(row["count"])