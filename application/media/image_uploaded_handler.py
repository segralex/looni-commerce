"""Background handler for ImageUploaded events."""
from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from collections.abc import Callable
from uuid import UUID

from application.media.thumbnail_service import ThumbnailService
from domain.listings.repositories import ListingImageRepository
from domain.media.events import ImageUploaded
from domain.media.processing import sanitize_processing_error
from domain.storage import StorageProvider

logger = logging.getLogger(__name__)


class ImageUploadedHandler:
    MAX_PROCESSING_ATTEMPTS = 3

    def __init__(
        self,
        image_repo: ListingImageRepository,
        storage: StorageProvider,
        thumbnail_service: ThumbnailService,
        retry_delays: tuple[float, ...] = (0.0, 0.05, 0.1),
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.image_repo = image_repo
        self.storage = storage
        self.thumbnail_service = thumbnail_service
        self.retry_delays = retry_delays
        self.sleeper = sleeper

    def handle(self, event: ImageUploaded) -> None:
        image_id = UUID(event.image_id)
        claimed = self.image_repo.claim_for_processing(image_id, self.MAX_PROCESSING_ATTEMPTS)
        if claimed is None:
            logger.info(
                "image event skipped",
                extra={
                    "event_id": event.event_id,
                    "image_id": event.image_id,
                    "listing_id": event.listing_id,
                },
            )
            return

        attempt = claimed.processing_attempts
        while claimed is not None:
            started = time.perf_counter()
            source_path = None
            generated_keys: dict[str, str] = {}
            try:
                with self.storage.open(event.original_storage_key) as source, tempfile.NamedTemporaryFile(delete=False) as tmp:
                    source_path = tmp.name
                    tmp.write(source.read())

                generated_keys = self.thumbnail_service.generate_and_store(source_path, event.image_id, claimed.content_type)
                thumbnails = generated_keys
                ready = self.image_repo.mark_ready(image_id, thumbnails)
                duration_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "image processing completed",
                    extra={
                        "event_id": event.event_id,
                        "image_id": event.image_id,
                        "listing_id": event.listing_id,
                        "processing_attempt": attempt,
                        "processing_status": "READY",
                        "duration_ms": duration_ms,
                    },
                )
                if ready is not None:
                    return
                self._cleanup_generated_assets(event.original_storage_key, generated_keys)
                return
            except FileNotFoundError:
                if self.image_repo.get(image_id) is None:
                    logger.info(
                        "deleted image skipped",
                        extra={
                            "event_id": event.event_id,
                            "image_id": event.image_id,
                            "listing_id": event.listing_id,
                            "processing_attempt": attempt,
                        },
                    )
                    return
                safe_error = "Storage operation failed"
            except Exception as exc:
                safe_error = sanitize_processing_error(exc)
            finally:
                if source_path is not None:
                    Path(source_path).unlink(missing_ok=True)

            failed = self.image_repo.mark_failed(image_id, safe_error)
            if failed is None:
                self._cleanup_generated_assets(event.original_storage_key, generated_keys)
                logger.info(
                    "deleted image skipped",
                    extra={
                        "event_id": event.event_id,
                        "image_id": event.image_id,
                        "listing_id": event.listing_id,
                        "processing_attempt": attempt,
                    },
                )
                return

            logger.warning(
                "image processing failed",
                extra={
                    "event_id": event.event_id,
                    "image_id": event.image_id,
                    "listing_id": event.listing_id,
                    "processing_attempt": attempt,
                    "processing_status": "FAILED",
                },
            )

            if attempt >= self.MAX_PROCESSING_ATTEMPTS:
                logger.error(
                    "retry limit reached",
                    extra={
                        "event_id": event.event_id,
                        "image_id": event.image_id,
                        "listing_id": event.listing_id,
                        "processing_attempt": attempt,
                    },
                )
                return

            delay_index = min(attempt - 1, len(self.retry_delays) - 1)
            delay = self.retry_delays[delay_index]
            logger.info(
                "retry scheduled",
                extra={
                    "event_id": event.event_id,
                    "image_id": event.image_id,
                    "listing_id": event.listing_id,
                    "processing_attempt": attempt,
                    "duration_ms": int(delay * 1000),
                },
            )
            self.sleeper(delay)
            claimed = self.image_repo.claim_for_processing(image_id, self.MAX_PROCESSING_ATTEMPTS)
            if claimed is None:
                self._cleanup_generated_assets(event.original_storage_key, generated_keys)
                return
            attempt = claimed.processing_attempts

    def _cleanup_generated_assets(self, original_storage_key: str, generated_keys: dict[str, str]) -> None:
        self.storage.delete(original_storage_key)
        for storage_key in generated_keys.values():
            self.storage.delete(storage_key)
