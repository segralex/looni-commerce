"""Schema creation for SQLite repositories."""
from __future__ import annotations

CREATE_USERS = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """
)

CREATE_LISTINGS = (
    """
    CREATE TABLE IF NOT EXISTS listings (
        id TEXT PRIMARY KEY,
        seller_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        condition TEXT NOT NULL,
        price TEXT NOT NULL,
        currency TEXT NOT NULL,
        location TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """
)

CREATE_RESERVATIONS = (
    """
    CREATE TABLE IF NOT EXISTS reservations (
        id TEXT PRIMARY KEY,
        listing_id TEXT NOT NULL,
        buyer_id TEXT NOT NULL,
        seller_id TEXT NOT NULL,
        status TEXT NOT NULL,
        expires_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """
)

CREATE_LISTING_IMAGES = (
    """
    CREATE TABLE IF NOT EXISTS listing_images (
        id TEXT PRIMARY KEY,
        listing_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        content_type TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        position INTEGER,
        storage_key TEXT,
        thumbnail_small_key TEXT,
        thumbnail_medium_key TEXT,
        thumbnail_large_key TEXT,
        processing_status TEXT NOT NULL DEFAULT 'PENDING',
        processing_error TEXT,
        processing_attempts INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """
)

CREATE_LISTING_SEARCH_FTS = (
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS listing_search_fts USING fts5(
        listing_id UNINDEXED,
        seller_id UNINDEXED,
        status UNINDEXED,
        category,
        condition UNINDEXED,
        location,
        price UNINDEXED,
        currency UNINDEXED,
        title,
        description,
        created_at UNINDEXED,
        tokenize = 'unicode61'
    );
    CREATE INDEX IF NOT EXISTS idx_listings_status ON listings (status);
    """
)

CREATE_EVENT_OUTBOX = (
    """
    CREATE TABLE IF NOT EXISTS event_outbox (
        id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        aggregate_type TEXT NOT NULL,
        aggregate_id TEXT NOT NULL,
        payload TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        correlation_id TEXT,
        causation_id TEXT,
        published INTEGER NOT NULL DEFAULT 0,
        published_at TEXT,
        retry_count INTEGER NOT NULL DEFAULT 0,
        permanently_failed INTEGER NOT NULL DEFAULT 0,
        failed_at TEXT,
        failure_reason TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_event_outbox_unpublished
        ON event_outbox (published, retry_count, occurred_at);
    CREATE INDEX IF NOT EXISTS idx_event_outbox_failed
        ON event_outbox (permanently_failed, failed_at);
    CREATE INDEX IF NOT EXISTS idx_event_outbox_event_type ON event_outbox (event_type);
    CREATE INDEX IF NOT EXISTS idx_event_outbox_aggregate_id ON event_outbox (aggregate_id);
    CREATE INDEX IF NOT EXISTS idx_event_outbox_correlation_id ON event_outbox (correlation_id);
    CREATE INDEX IF NOT EXISTS idx_event_outbox_occurred_at ON event_outbox (occurred_at);
    """
)
