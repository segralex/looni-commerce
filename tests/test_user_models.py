from datetime import UTC
from uuid import uuid4

import pytest

from domain.users.exceptions import UserValidationError
from domain.users.models import User, UserStatus


def test_create_user_normalizes_email_and_starts_pending() -> None:
    user = User(
        id=uuid4(),
        display_name="Test User",
        email=" Test@Example.COM ",
    )

    assert user.status == UserStatus.PENDING
    assert user.email == "test@example.com"
    assert user.created_at.tzinfo == UTC
    assert user.updated_at.tzinfo == UTC


def test_display_name_required() -> None:
    with pytest.raises(UserValidationError):
        User(id=uuid4(), display_name="", email="test@example.com")


def test_email_required() -> None:
    with pytest.raises(UserValidationError):
        User(id=uuid4(), display_name="Test", email="")
