from __future__ import annotations

import sqlite3
from typing import Optional
from .schema import (
    CREATE_USERS,
    CREATE_LISTINGS,
    CREATE_RESERVATIONS,
    CREATE_LISTING_IMAGES,
    CREATE_LISTING_SEARCH_FTS,
)


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        if self.conn is None:
            self.conn = sqlite3.connect(self.path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._init_schema()
        return self.conn

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            "\n".join(
                [
                    CREATE_USERS,
                    CREATE_LISTINGS,
                    CREATE_RESERVATIONS,
                    CREATE_LISTING_IMAGES,
                    CREATE_LISTING_SEARCH_FTS,
                ]
            )
        )
        self._migrate_listing_images_schema(cur)
        self._bootstrap_listing_search_index(cur)
        self.conn.commit()

    def _migrate_listing_images_schema(self, cur: sqlite3.Cursor) -> None:
        cur.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'listing_images'")
        if cur.fetchone() is None:
            return

        cur.execute("PRAGMA table_info(listing_images)")
        columns = {row["name"] for row in cur.fetchall()}

        if "position" not in columns:
            cur.execute("ALTER TABLE listing_images ADD COLUMN position INTEGER")

        if "storage_key" not in columns:
            cur.execute("ALTER TABLE listing_images ADD COLUMN storage_key TEXT")

        if "thumbnail_small_key" not in columns:
            cur.execute("ALTER TABLE listing_images ADD COLUMN thumbnail_small_key TEXT")

        if "thumbnail_medium_key" not in columns:
            cur.execute("ALTER TABLE listing_images ADD COLUMN thumbnail_medium_key TEXT")

        if "thumbnail_large_key" not in columns:
            cur.execute("ALTER TABLE listing_images ADD COLUMN thumbnail_large_key TEXT")

        if "processing_status" not in columns:
            cur.execute("ALTER TABLE listing_images ADD COLUMN processing_status TEXT NOT NULL DEFAULT 'PENDING'")

        if "processing_error" not in columns:
            cur.execute("ALTER TABLE listing_images ADD COLUMN processing_error TEXT")

        if "processing_attempts" not in columns:
            cur.execute("ALTER TABLE listing_images ADD COLUMN processing_attempts INTEGER NOT NULL DEFAULT 0")

        self._normalize_listing_image_positions(cur)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_listing_images_listing_id ON listing_images (listing_id)")
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_listing_images_listing_position ON listing_images (listing_id, position)"
        )

    def _normalize_listing_image_positions(self, cur: sqlite3.Cursor) -> None:
        cur.execute(
            """
            SELECT id, listing_id, position
            FROM listing_images
            ORDER BY listing_id ASC,
                     CASE WHEN position IS NULL THEN 1 ELSE 0 END ASC,
                     position ASC,
                     rowid ASC
            """
        )
        rows = cur.fetchall()

        current_listing_id = None
        next_position = 0
        for row in rows:
            listing_id = row["listing_id"]
            if listing_id != current_listing_id:
                current_listing_id = listing_id
                next_position = 1
            else:
                next_position += 1

            cur.execute(
                "UPDATE listing_images SET position = ? WHERE id = ?",
                (next_position, row["id"]),
            )

    def _bootstrap_listing_search_index(self, cur: sqlite3.Cursor) -> None:
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
            )
            SELECT
                l.id,
                l.seller_id,
                l.status,
                l.category,
                l.condition,
                l.location,
                l.price,
                l.currency,
                l.title,
                l.description,
                l.created_at
            FROM listings l
            WHERE l.status = 'PUBLISHED'
              AND NOT EXISTS (
                    SELECT 1
                    FROM listing_search_fts f
                    WHERE f.listing_id = l.id
              )
            """
        )

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            finally:
                self.conn = None
