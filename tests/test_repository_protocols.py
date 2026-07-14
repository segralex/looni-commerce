from typing import get_type_hints
from uuid import UUID

import pytest

import domain.repositories as repos


def test_protocols_exist_and_methods():
    for name in ("UserRepository", "ListingRepository", "ReservationRepository"):
        assert hasattr(repos, name), f"{name} missing"
        repo = getattr(repos, name)
        for method in ("add", "get", "save", "all"):
            assert hasattr(repo, method), f"{name}.{method} missing"


def test_exceptions_defined():
    assert hasattr(repos, "EntityNotFoundError")
    assert hasattr(repos, "DuplicateEntityError")
    assert issubclass(repos.EntityNotFoundError, Exception)
    assert issubclass(repos.DuplicateEntityError, Exception)


def test_all_returns_tuple_annotation():
    # Check that the 'all' method is annotated to return tuple
    repo = repos.UserRepository
    hints = get_type_hints(repo.all, globals(), locals())
    assert "return" in hints
    assert hints["return"] is tuple