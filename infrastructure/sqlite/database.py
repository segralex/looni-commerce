from __future__ import annotations

import sqlite3
from typing import Optional
from .schema import CREATE_USERS, CREATE_LISTINGS, CREATE_RESERVATIONS


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        if self.conn is None:
            self.conn = sqlite3.connect(self.path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._init_schema()
        return self.conn

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript("\n".join([CREATE_USERS, CREATE_LISTINGS, CREATE_RESERVATIONS]))
        self.conn.commit()

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            finally:
                self.conn = None
