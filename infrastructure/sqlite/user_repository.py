from __future__ import annotations

from typing import Any
from uuid import UUID
from datetime import datetime

from domain.repositories import EntityNotFoundError, DuplicateEntityError, UserRepository
from domain.users.models import User, UserStatus
from .database import Database


class SQLiteUserRepository(UserRepository):
    def __init__(self, db: Database):
        self.db = db

    def add(self, entity: Any) -> None:
        conn = self.db.connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (id, display_name, email, phone, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (
                    str(entity.id),
                    entity.display_name,
                    entity.email,
                    entity.phone,
                    entity.status.value,
                    entity.created_at.isoformat(),
                    entity.updated_at.isoformat(),
                ),
            )
            conn.commit()
        except Exception as exc:
            raise DuplicateEntityError("Duplicate entity id") from exc

    def get(self, entity_id: UUID) -> Any:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (str(entity_id),))
        row = cur.fetchone()
        if row is None:
            raise EntityNotFoundError("Entity not found")
        return User(
            id=UUID(row["id"]),
            display_name=row["display_name"],
            email=row["email"],
            phone=row["phone"],
            status=UserStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save(self, entity: Any) -> None:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE id = ?", (str(entity.id),))
        if cur.fetchone() is None:
            raise EntityNotFoundError("Unknown entity id")
        cur.execute(
            "UPDATE users SET display_name=?, email=?, phone=?, status=?, created_at=?, updated_at=? WHERE id=?",
            (
                entity.display_name,
                entity.email,
                entity.phone,
                entity.status.value,
                entity.created_at.isoformat(),
                entity.updated_at.isoformat(),
                str(entity.id),
            ),
        )
        conn.commit()

    def all(self) -> tuple[Any, ...]:
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users ORDER BY rowid ASC")
        rows = cur.fetchall()
        result = []
        for row in rows:
            result.append(
                User(
                    id=UUID(row["id"]),
                    display_name=row["display_name"],
                    email=row["email"],
                    phone=row["phone"],
                    status=UserStatus(row["status"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            )
        return tuple(result)
