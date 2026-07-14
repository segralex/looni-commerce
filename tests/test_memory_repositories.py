from __future__ import annotations

from uuid import uuid4

from domain.repositories import DuplicateEntityError, EntityNotFoundError
from infrastructure.repositories.memory import (
    MemoryListingRepository,
    MemoryReservationRepository,
    MemoryUserRepository,
)


class DummyEntity:
    def __init__(self, entity_id):
        self.id = entity_id


def test_user_repository_add_get_save_all():
    repo = MemoryUserRepository()
    entity_a = DummyEntity(uuid4())
    entity_b = DummyEntity(uuid4())

    repo.add(entity_a)
    repo.add(entity_b)

    assert repo.get(entity_a.id) is entity_a
    assert repo.get(entity_b.id) is entity_b
    assert repo.all() == (entity_a, entity_b)

    entity_a_replacement = DummyEntity(entity_a.id)
    repo.save(entity_a_replacement)
    assert repo.get(entity_a.id) is entity_a_replacement


def test_listing_repository_add_get_save_all():
    repo = MemoryListingRepository()
    entity_a = DummyEntity(uuid4())
    entity_b = DummyEntity(uuid4())

    repo.add(entity_a)
    repo.add(entity_b)

    assert repo.get(entity_a.id) is entity_a
    assert repo.get(entity_b.id) is entity_b
    assert repo.all() == (entity_a, entity_b)

    entity_b_replacement = DummyEntity(entity_b.id)
    repo.save(entity_b_replacement)
    assert repo.get(entity_b.id) is entity_b_replacement


def test_reservation_repository_add_get_save_all():
    repo = MemoryReservationRepository()
    entity_a = DummyEntity(uuid4())
    entity_b = DummyEntity(uuid4())

    repo.add(entity_a)
    repo.add(entity_b)

    assert repo.get(entity_a.id) is entity_a
    assert repo.get(entity_b.id) is entity_b
    assert repo.all() == (entity_a, entity_b)

    entity_b_replacement = DummyEntity(entity_b.id)
    repo.save(entity_b_replacement)
    assert repo.get(entity_b.id) is entity_b_replacement


def test_duplicate_entity_add_raises():
    repo = MemoryUserRepository()
    entity_id = uuid4()
    repo.add(DummyEntity(entity_id))

    try:
        repo.add(DummyEntity(entity_id))
        assert False, "Expected DuplicateEntityError"
    except DuplicateEntityError:
        pass


def test_save_unknown_entity_raises():
    repo = MemoryListingRepository()

    try:
        repo.save(DummyEntity(uuid4()))
        assert False, "Expected EntityNotFoundError"
    except EntityNotFoundError:
        pass


def test_get_unknown_entity_raises():
    repo = MemoryReservationRepository()

    try:
        repo.get(uuid4())
        assert False, "Expected EntityNotFoundError"
    except EntityNotFoundError:
        pass


def test_repository_independence_and_insertion_order():
    user_repo = MemoryUserRepository()
    listing_repo = MemoryListingRepository()

    user_a = DummyEntity(uuid4())
    user_b = DummyEntity(uuid4())
    listing_a = DummyEntity(uuid4())

    user_repo.add(user_a)
    user_repo.add(user_b)
    listing_repo.add(listing_a)

    assert user_repo.all() == (user_a, user_b)
    assert listing_repo.all() == (listing_a,)

    assert user_repo.get(user_a.id) is user_a
    assert listing_repo.get(listing_a.id) is listing_a
