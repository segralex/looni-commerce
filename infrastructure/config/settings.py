"""Application settings resolved from environment variables."""
from __future__ import annotations

import os
from pathlib import Path


class Settings:
    """Reads configuration from environment variables with sensible defaults."""

    @property
    def repository_backend(self) -> str:
        return os.environ.get("LOONI_REPOSITORY_BACKEND", "memory")

    @property
    def database_path(self) -> Path:
        raw = os.environ.get("LOONI_DATABASE_PATH", "data/looni-commerce.db")
        return Path(raw)

    @property
    def storage_path(self) -> Path:
        raw = os.environ.get("LOONI_STORAGE_PATH", "data/storage")
        return Path(raw)

    @property
    def log_level(self) -> str:
        return os.environ.get("LOONI_LOG_LEVEL", "INFO").upper()

    @property
    def json_logs(self) -> bool:
        raw = os.environ.get("LOONI_JSON_LOGS", "true").lower()
        return raw not in ("0", "false", "no", "off")

    @property
    def jwt_secret(self) -> str:
        return os.environ.get("LOONI_JWT_SECRET", "")

    @property
    def jwt_algorithm(self) -> str:
        return os.environ.get("LOONI_JWT_ALGORITHM", "HS256")

    @property
    def access_token_minutes(self) -> int:
        try:
            return int(os.environ.get("LOONI_ACCESS_TOKEN_MINUTES", "30"))
        except ValueError:
            return 30


settings = Settings()
