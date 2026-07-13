from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Dict
from uuid import UUID, uuid4

from .exceptions import InvalidUserStateError, UserValidationError
from .models import User, UserStatus


class UserService:
    def __init__(self) -> None:
        self._store: Dict[UUID, User] = {}

    def create_user(self, display_name: str, email: str, phone: str | None = None) -> User:
        user = User(
            id=uuid4(),
            display_name=display_name,
            email=email,
            phone=phone,
        )
        self._store[user.id] = user
        return deepcopy(user)

    def get_user(self, user_id: UUID) -> User:
        return deepcopy(self._store[user_id])

    def update_profile(self, user_id: UUID, display_name: str | None = None, email: str | None = None, phone: str | None = None) -> User:
        user = self._store.get(user_id)
        if user is None:
            raise KeyError(user_id)
        if user.status == UserStatus.DELETED:
            raise InvalidUserStateError("DELETED users cannot be modified")

        if display_name is not None:
            if not display_name:
                raise UserValidationError("display_name is required")
            user.display_name = display_name
        if email is not None:
            if not email:
                raise UserValidationError("email is required")
            user.email = email.strip().lower()
        if phone is not None:
            user.phone = phone

        user.updated_at = datetime.now(UTC)
        self._store[user.id] = user
        return deepcopy(user)

    def activate(self, user_id: UUID) -> User:
        user = self._store.get(user_id)
        if user is None:
            raise KeyError(user_id)
        if user.status != UserStatus.PENDING:
            raise InvalidUserStateError("Can only activate users in PENDING")
        user.status = UserStatus.ACTIVE
        user.updated_at = datetime.now(UTC)
        self._store[user.id] = user
        return deepcopy(user)

    def suspend(self, user_id: UUID) -> User:
        user = self._store.get(user_id)
        if user is None:
            raise KeyError(user_id)
        if user.status != UserStatus.ACTIVE:
            raise InvalidUserStateError("Can only suspend users in ACTIVE")
        user.status = UserStatus.SUSPENDED
        user.updated_at = datetime.now(UTC)
        self._store[user.id] = user
        return deepcopy(user)

    def reactivate(self, user_id: UUID) -> User:
        user = self._store.get(user_id)
        if user is None:
            raise KeyError(user_id)
        if user.status != UserStatus.SUSPENDED:
            raise InvalidUserStateError("Can only reactivate users in SUSPENDED")
        user.status = UserStatus.ACTIVE
        user.updated_at = datetime.now(UTC)
        self._store[user.id] = user
        return deepcopy(user)

    def delete(self, user_id: UUID) -> User:
        user = self._store.get(user_id)
        if user is None:
            raise KeyError(user_id)
        if user.status == UserStatus.DELETED:
            raise InvalidUserStateError("User is already DELETED")
        user.status = UserStatus.DELETED
        user.updated_at = datetime.now(UTC)
        self._store[user.id] = user
        return deepcopy(user)
