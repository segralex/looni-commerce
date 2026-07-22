"""Tests for repository backend configuration switching (EO-LC-000019)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the external LICOS kernel package is importable.
LICOS_ROOT = Path(__file__).resolve().parents[3] / "200_LICOS" / "licos-core"
if LICOS_ROOT.is_dir() and str(LICOS_ROOT) not in sys.path:
    sys.path.insert(0, str(LICOS_ROOT))

import pytest

import app.dependencies as deps
from infrastructure.config.settings import settings
from infrastructure.repositories.memory import (
    MemoryUserRepository,
    MemoryListingImageRepository,
    MemoryListingRepository,
    MemoryOutboxRepository,
    MemoryReservationRepository,
    MemoryTrustRepository,
)
from infrastructure.sqlite.listing_image_repository import SQLiteListingImageRepository
from infrastructure.sqlite.outbox_repository import SQLiteOutboxRepository
from infrastructure.sqlite.user_repository import SQLiteUserRepository
from infrastructure.sqlite.listing_repository import SQLiteListingRepository
from infrastructure.sqlite.reservation_repository import SQLiteReservationRepository
from infrastructure.sqlite.trust_repository import SQLiteTrustRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENV_BACKEND = "LOONI_REPOSITORY_BACKEND"
_ENV_DB_PATH = "LOONI_DATABASE_PATH"


def _set_env(monkeypatch, backend: str, db_path: str | None = None) -> None:
    monkeypatch.setenv(_ENV_BACKEND, backend)
    if db_path is not None:
        monkeypatch.setenv(_ENV_DB_PATH, db_path)
    else:
        monkeypatch.delenv(_ENV_DB_PATH, raising=False)


# ---------------------------------------------------------------------------
# Settings unit tests
# ---------------------------------------------------------------------------


def test_settings_default_backend():
    # No env var set — default must be "memory".
    original = os.environ.pop(_ENV_BACKEND, None)
    try:
        assert settings.repository_backend == "memory"
    finally:
        if original is not None:
            os.environ[_ENV_BACKEND] = original


def test_settings_default_database_path():
    original = os.environ.pop(_ENV_DB_PATH, None)
    try:
        assert settings.database_path == Path("data/looni-commerce.db")
    finally:
        if original is not None:
            os.environ[_ENV_DB_PATH] = original


def test_settings_reads_env_backend(monkeypatch):
    monkeypatch.setenv(_ENV_BACKEND, "sqlite")
    assert settings.repository_backend == "sqlite"


def test_settings_reads_env_database_path(monkeypatch, tmp_path):
    custom = str(tmp_path / "custom.db")
    monkeypatch.setenv(_ENV_DB_PATH, custom)
    assert settings.database_path == Path(custom)


# ---------------------------------------------------------------------------
# dependencies._build_repositories / reset_singletons
# ---------------------------------------------------------------------------


def test_default_builds_memory_repos():
    """Without env override, repositories must be memory-backed."""
    os.environ.pop(_ENV_BACKEND, None)
    deps.reset_singletons()
    assert isinstance(deps.user_repository, MemoryUserRepository)
    assert isinstance(deps.listing_repository, MemoryListingRepository)
    assert isinstance(deps.reservation_repository, MemoryReservationRepository)
    assert isinstance(deps.image_repository, MemoryListingImageRepository)
    assert isinstance(deps.outbox_repository, MemoryOutboxRepository)
    assert isinstance(deps.trust_repository, MemoryTrustRepository)
    # Restore to known state.
    deps.reset_singletons()


def test_sqlite_backend_builds_sqlite_repos(monkeypatch, tmp_path):
    """When LOONI_REPOSITORY_BACKEND=sqlite, repos must be SQLite-backed."""
    db_file = tmp_path / "test.db"
    _set_env(monkeypatch, "sqlite", str(db_file))
    deps.reset_singletons()
    assert isinstance(deps.user_repository, SQLiteUserRepository)
    assert isinstance(deps.listing_repository, SQLiteListingRepository)
    assert isinstance(deps.reservation_repository, SQLiteReservationRepository)
    assert isinstance(deps.image_repository, SQLiteListingImageRepository)
    assert isinstance(deps.outbox_repository, SQLiteOutboxRepository)
    assert isinstance(deps.trust_repository, SQLiteTrustRepository)
    # Restore default for subsequent tests.
    monkeypatch.delenv(_ENV_BACKEND)
    deps.reset_singletons()


def test_unknown_backend_raises(monkeypatch):
    monkeypatch.setenv(_ENV_BACKEND, "redis")
    with pytest.raises(ValueError, match="redis"):
        deps.reset_singletons()
    # Restore default for subsequent tests.
    monkeypatch.delenv(_ENV_BACKEND)
    deps.reset_singletons()


def test_reset_singletons_respects_changed_env(monkeypatch, tmp_path):
    """reset_singletons picks up a changed env var without restart."""
    # Start with memory.
    monkeypatch.delenv(_ENV_BACKEND, raising=False)
    deps.reset_singletons()
    assert isinstance(deps.user_repository, MemoryUserRepository)

    # Switch to sqlite.
    db_file = tmp_path / "switch.db"
    _set_env(monkeypatch, "sqlite", str(db_file))
    deps.reset_singletons()
    assert isinstance(deps.user_repository, SQLiteUserRepository)

    # Switch back.
    monkeypatch.delenv(_ENV_BACKEND)
    deps.reset_singletons()
    assert isinstance(deps.user_repository, MemoryUserRepository)


# ---------------------------------------------------------------------------
# SQLite data survives dependency rebuild
# ---------------------------------------------------------------------------


def test_sqlite_data_survives_reset(monkeypatch, tmp_path):
    """Data written under one reset_singletons call is visible after another."""
    db_file = tmp_path / "persist.db"
    _set_env(monkeypatch, "sqlite", str(db_file))

    deps.reset_singletons()
    svc = deps.marketplace_service
    user = svc.create_user("Alice", "alice@example.com")
    svc.activate_user(user.id)

    # Rebuild singletons with the same DB file.
    deps.reset_singletons()
    fetched = deps.marketplace_service.get_user(user.id)
    assert fetched.email == "alice@example.com"

    # Restore.
    monkeypatch.delenv(_ENV_BACKEND)
    deps.reset_singletons()


# ---------------------------------------------------------------------------
# Ensure database parent directory is created automatically
# ---------------------------------------------------------------------------


def test_sqlite_creates_parent_directory(monkeypatch, tmp_path):
    nested = tmp_path / "a" / "b" / "c" / "looni.db"
    _set_env(monkeypatch, "sqlite", str(nested))
    deps.reset_singletons()
    assert nested.parent.is_dir()

    monkeypatch.delenv(_ENV_BACKEND)
    deps.reset_singletons()
