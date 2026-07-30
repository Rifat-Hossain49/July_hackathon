"""Durable bounded SQLite storage for the public domestic hub."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import threading
from typing import Any

from .validation import CapsuleRequest, HubError


@dataclass(frozen=True, slots=True)
class StoreLimits:
    max_active_capsules: int = 10_000
    max_active_per_channel: int = 1_000
    max_database_bytes: int = 64 * 1024 * 1024
    cleanup_batch: int = 500

    def __post_init__(self) -> None:
        for field_name in (
            "max_active_capsules",
            "max_active_per_channel",
            "max_database_bytes",
            "cleanup_batch",
        ):
            if getattr(self, field_name) < 1:
                raise ValueError(f"{field_name} must be positive")


@dataclass(frozen=True, slots=True)
class StoredCapsule:
    cursor: int
    capsule_id: str
    client_id: str
    channel: str
    message: str
    location: str
    urgency: str
    received_at_unix: int
    expires_at_unix: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "StoredCapsule":
        return cls(
            cursor=int(row["cursor"]),
            capsule_id=str(row["capsule_id"]),
            client_id=str(row["client_id"]),
            channel=str(row["channel"]),
            message=str(row["message"]),
            location=str(row["location"]),
            urgency=str(row["urgency"]),
            received_at_unix=int(row["received_at_unix"]),
            expires_at_unix=int(row["expires_at_unix"]),
        )

    def public_document(self, *, include_client_id: bool = False) -> dict[str, Any]:
        document: dict[str, Any] = {
            "schema": "shongket.bdix.stored-capsule.v1.0",
            "cursor": self.cursor,
            "capsule_id": self.capsule_id,
            "channel": self.channel,
            "message": self.message,
            "location": self.location,
            "urgency": self.urgency,
            "visibility": "public",
            "human_confirmed": True,
            "received_at_unix": self.received_at_unix,
            "expires_at_unix": self.expires_at_unix,
        }
        if include_client_id:
            document["client_id"] = self.client_id
        return document


class CapsuleStore:
    """One SQLite file with short transactions and rejection-only limits."""

    def __init__(self, path: str | Path, *, limits: StoreLimits | None = None) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.limits = limits or StoreLimits()
        self._schema_lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=3.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 3000")
        return connection

    def _initialize(self) -> None:
        with self._schema_lock, closing(self._connect()) as connection:
            with connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS capsules (
                        cursor INTEGER PRIMARY KEY AUTOINCREMENT,
                        capsule_id TEXT NOT NULL UNIQUE,
                        client_id TEXT NOT NULL UNIQUE,
                        channel TEXT NOT NULL,
                        message TEXT NOT NULL,
                        location TEXT NOT NULL,
                        urgency TEXT NOT NULL,
                        received_at_unix INTEGER NOT NULL,
                        expires_at_unix INTEGER NOT NULL,
                        CHECK (urgency IN ('normal', 'important', 'critical')),
                        CHECK (expires_at_unix > received_at_unix)
                    );
                    CREATE INDEX IF NOT EXISTS capsules_channel_cursor
                        ON capsules(channel, cursor);
                    CREATE INDEX IF NOT EXISTS capsules_expiry
                        ON capsules(expires_at_unix);
                    """
                )

    def _cleanup_expired(
        self,
        connection: sqlite3.Connection,
        *,
        now_unix: int,
    ) -> int:
        cursor = connection.execute(
            """
            DELETE FROM capsules
            WHERE cursor IN (
                SELECT cursor
                FROM capsules
                WHERE expires_at_unix <= ?
                ORDER BY expires_at_unix, cursor
                LIMIT ?
            )
            """,
            (now_unix, self.limits.cleanup_batch),
        )
        return int(cursor.rowcount)

    @staticmethod
    def _row_for_client(
        connection: sqlite3.Connection,
        client_id: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM capsules WHERE client_id = ?",
            (client_id,),
        ).fetchone()

    @staticmethod
    def _database_bytes(connection: sqlite3.Connection) -> int:
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        return page_count * page_size

    def publish(
        self,
        request: CapsuleRequest,
        *,
        now_unix: int,
    ) -> tuple[StoredCapsule, bool]:
        estimated_insert_bytes = len(request.canonical_bytes()) + 4096
        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    self._cleanup_expired(connection, now_unix=now_unix)

                    existing = self._row_for_client(connection, request.client_id)
                    if existing is not None:
                        stored = StoredCapsule.from_row(existing)
                        if stored.capsule_id != request.capsule_id:
                            raise HubError(
                                "CLIENT_ID_CONFLICT",
                                "client_id was already used for different content",
                                status=409,
                            )
                        connection.commit()
                        return stored, False

                    active_count = int(
                        connection.execute(
                            "SELECT COUNT(*) FROM capsules WHERE expires_at_unix > ?",
                            (now_unix,),
                        ).fetchone()[0]
                    )
                    if active_count >= self.limits.max_active_capsules:
                        raise HubError(
                            "HUB_CAPACITY_REACHED",
                            "hub active-capsule capacity is reached",
                            status=507,
                        )

                    channel_count = int(
                        connection.execute(
                            """
                            SELECT COUNT(*)
                            FROM capsules
                            WHERE channel = ? AND expires_at_unix > ?
                            """,
                            (request.channel, now_unix),
                        ).fetchone()[0]
                    )
                    if channel_count >= self.limits.max_active_per_channel:
                        raise HubError(
                            "CHANNEL_CAPACITY_REACHED",
                            "channel active-capsule capacity is reached",
                            status=507,
                        )

                    if (
                        self._database_bytes(connection) + estimated_insert_bytes
                        > self.limits.max_database_bytes
                    ):
                        raise HubError(
                            "OUT_OF_BUDGET",
                            "hub database byte budget is reached",
                            status=507,
                        )

                    expires_at_unix = now_unix + request.expires_in_seconds
                    result = connection.execute(
                        """
                        INSERT INTO capsules (
                            capsule_id,
                            client_id,
                            channel,
                            message,
                            location,
                            urgency,
                            received_at_unix,
                            expires_at_unix
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            request.capsule_id,
                            request.client_id,
                            request.channel,
                            request.message,
                            request.location,
                            request.urgency,
                            now_unix,
                            expires_at_unix,
                        ),
                    )
                    row = connection.execute(
                        "SELECT * FROM capsules WHERE cursor = ?",
                        (int(result.lastrowid),),
                    ).fetchone()
                    connection.commit()
                    if row is None:
                        raise RuntimeError("inserted capsule could not be read")
                    return StoredCapsule.from_row(row), True
        except HubError:
            raise
        except sqlite3.IntegrityError as exc:
            raise HubError(
                "STORE_CONFLICT",
                "capsule identity conflicts with stored state",
                status=409,
            ) from exc
        except sqlite3.Error as exc:
            raise HubError(
                "STORE_UNAVAILABLE",
                "durable store is temporarily unavailable",
                status=503,
            ) from exc

    def list_active(
        self,
        *,
        channel: str,
        after: int,
        limit: int,
        now_unix: int,
    ) -> tuple[list[StoredCapsule], int]:
        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    self._cleanup_expired(connection, now_unix=now_unix)
                    rows = connection.execute(
                        """
                        SELECT *
                        FROM capsules
                        WHERE channel = ?
                          AND cursor > ?
                          AND expires_at_unix > ?
                        ORDER BY cursor
                        LIMIT ?
                        """,
                        (channel, after, now_unix, limit),
                    ).fetchall()
                    connection.commit()
        except sqlite3.Error as exc:
            raise HubError(
                "STORE_UNAVAILABLE",
                "durable store is temporarily unavailable",
                status=503,
            ) from exc
        capsules = [StoredCapsule.from_row(row) for row in rows]
        next_cursor = capsules[-1].cursor if capsules else after
        return capsules, next_cursor

    def health(self) -> dict[str, int | str]:
        try:
            with closing(self._connect()) as connection:
                connection.execute("SELECT 1").fetchone()
                database_bytes = self._database_bytes(connection)
                sqlite_version = str(
                    connection.execute("SELECT sqlite_version()").fetchone()[0]
                )
        except sqlite3.Error as exc:
            raise HubError(
                "STORE_UNAVAILABLE",
                "durable store is unavailable",
                status=503,
            ) from exc
        return {
            "status": "ready",
            "database_bytes": database_bytes,
            "sqlite_version": sqlite_version,
        }
