from uuid import uuid4

import pytest

from domain.users.exceptions import InvalidUserStateError, UserValidationError
from domain.users.models import UserStatus
from domain.users.service import UserService


def test_create_user_and_state_transitions() -> None:
    svc = UserService()
    user = svc.create_user("Test User", " TEST@Example.COM ", "123")

    assert user.status == UserStatus.PENDING
    assert user.email == "test@example.com"

    svc.activate(user.id)
    assert svc.get_user(user.id).status == UserStatus.ACTIVE

    svc.suspend(user.id)
    assert svc.get_user(user.id).status == UserStatus.SUSPENDED

    svc.reactivate(user.id)
    assert svc.get_user(user.id).status == UserStatus.ACTIVE

    svc.delete(user.id)
    assert svc.get_user(user.id).status == UserStatus.DELETED

    with pytest.raises(InvalidUserStateError):
        svc.activate(user.id)


def test_update_profile_and_deleted_forbidden() -> None:
    svc = UserService()
    user = svc.create_user("Test User", "user@example.com")
    before = svc.get_user(user.id).updated_at

    updated = svc.update_profile(user.id, display_name="New Name", email="NEW@example.com")
    assert updated.display_name == "New Name"
    assert updated.email == "new@example.com"
    assert updated.updated_at >= before

    svc.delete(user.id)
    with pytest.raises(InvalidUserStateError):
        svc.update_profile(user.id, display_name="X")


def test_invalid_transitions_raise() -> None:
    svc = UserService()
    user = svc.create_user("Test User", "user@example.com")

    with pytest.raises(InvalidUserStateError):
        svc.suspend(user.id)

    svc.activate(user.id)
    with pytest.raises(InvalidUserStateError):
        svc.activate(user.id)

    svc.suspend(user.id)
    with pytest.raises(InvalidUserStateError):
        svc.suspend(user.id)

    svc.delete(user.id)
    with pytest.raises(InvalidUserStateError):
        svc.reactivate(user.id)
