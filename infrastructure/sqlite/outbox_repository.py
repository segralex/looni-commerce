from __future__ import annotations

import json
from datetime import UTC, datetime
import threading

from domain.events.outbox import OutboxEntry, OutboxState
from domain.events.metrics import EventMetrics
from domain.events.serialization import deserialize_event, serialize_event

from .database import Database


class SQLiteOutboxRepository:
    def __init__(self, db: Database, metrics: EventMetrics | None = None):
        self.db = db
        self._notifier = None
        self._lock = threading.RLock()
        self._metrics = metrics

    def set_notifier(self, notifier) -> None:
        self._notifier = notifier

    def save(self, event) -> OutboxEntry:
        serialized = serialize_event(event)
        entry_id = event.event_id
        with self._lock:
            conn = self.db.connect()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO event_outbox (
                    id,
                    event_type,
                    aggregate_type,
                    aggregate_id,
                    payload,
                    occurred_at,
                    correlation_id,
                    causation_id,
                    published,
                    published_at,
                    retry_count,
                    permanently_failed,
                    failed_at,
                    failure_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, 0, 0, NULL, NULL)
                """,
                (
                    entry_id,
                    event.event_type,
                    event.aggregate_type,
                    event.aggregate_id,
                    json.dumps(serialized),
                    event.occurred_at.isoformat(),
                    event.correlation_id,
                    event.causation_id,
                ),
            )
            conn.commit()
            entry = OutboxEntry(
                id=entry_id,
                event=event,
                published=False,
                published_at=None,
                retry_count=0,
                permanently_failed=False,
                failed_at=None,
                failure_reason=None,
            )
        if self._notifier is not None:
            self._notifier()
        self._sync_metrics()
        return entry

    def get(self, entry_id: str) -> OutboxEntry | None:
        with self._lock:
            conn = self.db.connect()
            cur = conn.cursor()
            cur.execute("SELECT * FROM event_outbox WHERE id = ?", (entry_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return self._hydrate(row)

    def list_unpublished(
        self,
        limit: int | None = None,
        max_retry_count: int | None = None,
    ) -> list[OutboxEntry]:
        with self._lock:
            conn = self.db.connect()
            cur = conn.cursor()
            sql = "SELECT * FROM event_outbox WHERE published = 0 AND permanently_failed = 0"
            params: list[object] = []
            if max_retry_count is not None:
                sql += " AND retry_count < ?"
                params.append(max_retry_count)
            sql += " ORDER BY occurred_at ASC, id ASC"
            if limit is not None:
                sql += " LIMIT ?"
                params.append(limit)
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        return [self._hydrate(row) for row in rows]

    def get_unpublished(
        self,
        limit: int | None = None,
        max_retry_count: int | None = None,
    ) -> list[OutboxEntry]:
        return self.list_unpublished(limit=limit, max_retry_count=max_retry_count)

    def get_failed(self, limit: int | None = None) -> list[OutboxEntry]:
        with self._lock:
            conn = self.db.connect()
            cur = conn.cursor()
            sql = "SELECT * FROM event_outbox WHERE permanently_failed = 1 ORDER BY failed_at ASC, id ASC"
            params: list[object] = []
            if limit is not None:
                sql += " LIMIT ?"
                params.append(limit)
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        return [self._hydrate(row) for row in rows]

    def get_by_aggregate(self, aggregate_type: str, aggregate_id: str) -> list[OutboxEntry]:
        with self._lock:
            conn = self.db.connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM event_outbox WHERE aggregate_type = ? AND aggregate_id = ? ORDER BY occurred_at ASC, id ASC",
                (aggregate_type, aggregate_id),
            )
            rows = cur.fetchall()
        return [self._hydrate(row) for row in rows]

    def query(
        self, *, state: OutboxState | str | None = None,
        status: OutboxState | str | None = None, event_type: str | None = None,
        aggregate_id: str | None = None, correlation_id: str | None = None,
        occurred_from: datetime | None = None, occurred_to: datetime | None = None,
        limit: int | None = None,
    ) -> list[OutboxEntry]:
        requested_state = OutboxState(state or status) if (state or status) else None
        clauses: list[str] = []
        params: list[object] = []
        if requested_state == OutboxState.PENDING:
            clauses.append("published = 0 AND permanently_failed = 0")
        elif requested_state == OutboxState.PUBLISHED:
            clauses.append("published = 1")
        elif requested_state in (OutboxState.FAILED, OutboxState.DEAD_LETTER):
            clauses.append("permanently_failed = 1")
        for column, value in (("event_type", event_type), ("aggregate_id", aggregate_id),
                              ("correlation_id", correlation_id)):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        if occurred_from is not None:
            clauses.append("occurred_at >= ?")
            params.append(occurred_from.isoformat())
        if occurred_to is not None:
            clauses.append("occurred_at <= ?")
            params.append(occurred_to.isoformat())
        sql = "SELECT * FROM event_outbox"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY occurred_at ASC, id ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._lock:
            cur = self.db.connect().cursor()
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        return [self._hydrate(row) for row in rows]

    def requeue(self, entry_ids: list[str]) -> list[OutboxEntry]:
        if not entry_ids:
            return []
        placeholders = ",".join("?" for _ in entry_ids)
        with self._lock:
            conn = self.db.connect()
            cur = conn.cursor()
            cur.execute(
                f"SELECT id FROM event_outbox WHERE permanently_failed = 1 AND id IN ({placeholders})",
                tuple(entry_ids),
            )
            failed_ids = {row["id"] for row in cur.fetchall()}
            cur.execute(
                f"""UPDATE event_outbox
                    SET published = 0, published_at = NULL, retry_count = 0,
                        permanently_failed = 0, failed_at = NULL, failure_reason = NULL
                    WHERE permanently_failed = 1 AND id IN ({placeholders})""",
                tuple(entry_ids),
            )
            conn.commit()
        result = [entry for entry_id in entry_ids if entry_id in failed_ids
                  and (entry := self.get(entry_id)) is not None]
        self._sync_metrics()
        if result and self._notifier is not None:
            self._notifier()
        return result

    def mark_published(self, entry_id: str, published_at: datetime) -> OutboxEntry | None:
        with self._lock:
            conn = self.db.connect()
            cur = conn.cursor()
            cur.execute(
                "UPDATE event_outbox SET published = 1, published_at = ? WHERE id = ?",
                (published_at.isoformat(), entry_id),
            )
            if cur.rowcount == 0:
                conn.rollback()
                return None
            conn.commit()
        entry = self.get(entry_id)
        self._sync_metrics()
        return entry

    def increment_retry(self, entry_id: str) -> OutboxEntry | None:
        with self._lock:
            conn = self.db.connect()
            cur = conn.cursor()
            cur.execute(
                "UPDATE event_outbox SET retry_count = retry_count + 1 WHERE id = ?",
                (entry_id,),
            )
            if cur.rowcount == 0:
                conn.rollback()
                return None
            conn.commit()
        entry = self.get(entry_id)
        self._sync_metrics()
        return entry

    def mark_failed(self, entry_id: str, failed_at: datetime, failure_reason: str | None = None) -> OutboxEntry | None:
        with self._lock:
            conn = self.db.connect()
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE event_outbox
                SET permanently_failed = 1,
                    failed_at = ?,
                    failure_reason = ?
                WHERE id = ?
                """,
                (failed_at.isoformat(), failure_reason, entry_id),
            )
            if cur.rowcount == 0:
                conn.rollback()
                return None
            conn.commit()
        entry = self.get(entry_id)
        self._sync_metrics()
        return entry

    def _hydrate(self, row) -> OutboxEntry:
        payload = json.loads(row["payload"])
        published_at = row["published_at"]
        failed_at = row["failed_at"] if "failed_at" in row.keys() else None
        return OutboxEntry(
            id=row["id"],
            event=deserialize_event(payload),
            published=bool(row["published"]),
            published_at=datetime.fromisoformat(published_at) if published_at else None,
            retry_count=int(row["retry_count"]),
            permanently_failed=bool(row["permanently_failed"]) if "permanently_failed" in row.keys() else False,
            failed_at=datetime.fromisoformat(failed_at) if failed_at else None,
            failure_reason=row["failure_reason"] if "failure_reason" in row.keys() else None,
        )

    def _sync_metrics(self) -> None:
        if self._metrics is None:
            return
        self._metrics.record_queue_depth(len(self.get_unpublished()))
