from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload
import sqlite3
import time
from uuid import uuid4


@dataclass(frozen=True)
class StoredSession:
    session_id: str
    user_id: str
    username: str
    issued_at: float
    expires_at: float


@dataclass(frozen=True)
class StoredDeck:
    deck_id: str
    user_id: str
    name: str
    card_payload_json: str
    created_at: float
    updated_at: float


class RouterStorage:
    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._lock = RLock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._db_path))
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.executescript(
                    """
                    PRAGMA journal_mode=WAL;

                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        issued_at REAL NOT NULL,
                        expires_at REAL NOT NULL,
                        revoked_at REAL,
                        FOREIGN KEY(user_id) REFERENCES users(user_id)
                    );

                    CREATE TABLE IF NOT EXISTS decks (
                        deck_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        card_payload_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(user_id)
                    );

                    CREATE INDEX IF NOT EXISTS idx_decks_user_id ON decks(user_id);

                    CREATE TABLE IF NOT EXISTS user_preferences (
                        user_id TEXT PRIMARY KEY,
                        selected_deck_id TEXT,
                        updated_at REAL NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(user_id),
                        FOREIGN KEY(selected_deck_id) REFERENCES decks(deck_id)
                    );
                    """
                )

    def get_or_create_user(self, username: str) -> str:
        normalized = username.strip()
        if not normalized:
            raise ValueError("username must not be empty")

        now = time.time()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT user_id FROM users WHERE username = ?",
                    (normalized,),
                ).fetchone()
                if row is not None:
                    conn.execute(
                        "UPDATE users SET updated_at = ? WHERE user_id = ?",
                        (now, row["user_id"]),
                    )
                    return str(row["user_id"])

                user_id = uuid4().hex
                conn.execute(
                    "INSERT INTO users (user_id, username, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (user_id, normalized, now, now),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO user_preferences (user_id, selected_deck_id, updated_at) VALUES (?, NULL, ?)",
                    (user_id, now),
                )
                return user_id

    def create_or_update_session(self, session_id: str, user_id: str, ttl_seconds: int) -> None:
        now = time.time()
        expires_at = now + max(1, ttl_seconds)
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO sessions (session_id, user_id, issued_at, expires_at, revoked_at)
                    VALUES (?, ?, ?, ?, NULL)
                    ON CONFLICT(session_id) DO UPDATE SET
                        user_id = excluded.user_id,
                        issued_at = excluded.issued_at,
                        expires_at = excluded.expires_at,
                        revoked_at = NULL
                    """,
                    (session_id, user_id, now, expires_at),
                )

    def get_session(self, session_id: str) -> StoredSession | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT s.session_id, s.user_id, u.username, s.issued_at, s.expires_at
                    FROM sessions AS s
                    JOIN users AS u ON u.user_id = s.user_id
                    WHERE s.session_id = ?
                      AND s.revoked_at IS NULL
                    """,
                    (session_id,),
                ).fetchone()

        if row is None:
            return None

        now = time.time()
        if float(row["expires_at"]) < now:
            return None

        return StoredSession(
            session_id=str(row["session_id"]),
            user_id=str(row["user_id"]),
            username=str(row["username"]),
            issued_at=float(row["issued_at"]),
            expires_at=float(row["expires_at"]),
        )

    def touch_session(self, session_id: str, ttl_seconds: int) -> None:
        now = time.time()
        expires_at = now + max(1, ttl_seconds)
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE sessions
                    SET expires_at = ?, revoked_at = NULL
                    WHERE session_id = ?
                    """,
                    (expires_at, session_id),
                )

    def revoke_session(self, session_id: str) -> None:
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE sessions SET revoked_at = ? WHERE session_id = ?",
                    (now, session_id),
                )

    def list_active_session_ids_for_user(self, user_id: str) -> list[str]:
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT session_id
                    FROM sessions
                    WHERE user_id = ?
                      AND revoked_at IS NULL
                      AND expires_at >= ?
                    """,
                    (user_id, now),
                ).fetchall()

        return [
            str(row["session_id"])
            for row in rows
            if isinstance(row["session_id"], str) and row["session_id"].strip()
        ]

    def create_deck(self, user_id: str, name: str, card_payload_json: str) -> StoredDeck:
        normalized_name = name.strip()[:64]
        if not normalized_name:
            raise ValueError("deck name must not be empty")

        now = time.time()
        deck_id = uuid4().hex
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO decks (deck_id, user_id, name, card_payload_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (deck_id, user_id, normalized_name, card_payload_json, now, now),
                )

        return StoredDeck(
            deck_id=deck_id,
            user_id=user_id,
            name=normalized_name,
            card_payload_json=card_payload_json,
            created_at=now,
            updated_at=now,
        )

    def list_decks_for_user(self, user_id: str) -> list[StoredDeck]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT deck_id, user_id, name, card_payload_json, created_at, updated_at
                    FROM decks
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                    """,
                    (user_id,),
                ).fetchall()

        return [
            StoredDeck(
                deck_id=str(row["deck_id"]),
                user_id=str(row["user_id"]),
                name=str(row["name"]),
                card_payload_json=str(row["card_payload_json"]),
                created_at=float(row["created_at"]),
                updated_at=float(row["updated_at"]),
            )
            for row in rows
        ]

    def update_deck(self, deck_id: str, user_id: str, name: str, card_payload_json: str) -> bool:
        normalized_name = name.strip()[:64]
        if not normalized_name:
            raise ValueError("deck name must not be empty")

        now = time.time()
        with self._lock:
            with self._connect() as conn:
                result = conn.execute(
                    """
                    UPDATE decks
                    SET name = ?, card_payload_json = ?, updated_at = ?
                    WHERE deck_id = ? AND user_id = ?
                    """,
                    (normalized_name, card_payload_json, now, deck_id, user_id),
                )
                return result.rowcount > 0

    def delete_deck(self, deck_id: str, user_id: str) -> bool:
        with self._lock:
            with self._connect() as conn:
                result = conn.execute(
                    "DELETE FROM decks WHERE deck_id = ? AND user_id = ?",
                    (deck_id, user_id),
                )
                if result.rowcount > 0:
                    conn.execute(
                        """
                        UPDATE user_preferences
                        SET selected_deck_id = NULL, updated_at = ?
                        WHERE user_id = ? AND selected_deck_id = ?
                        """,
                        (time.time(), user_id, deck_id),
                    )
                return result.rowcount > 0

    def set_selected_deck(self, user_id: str, deck_id: str | None) -> bool:
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                if deck_id is not None:
                    row = conn.execute(
                        "SELECT 1 FROM decks WHERE deck_id = ? AND user_id = ?",
                        (deck_id, user_id),
                    ).fetchone()
                    if row is None:
                        return False

                conn.execute(
                    """
                    INSERT INTO user_preferences (user_id, selected_deck_id, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        selected_deck_id = excluded.selected_deck_id,
                        updated_at = excluded.updated_at
                    """,
                    (user_id, deck_id, now),
                )
                return True

    def get_selected_deck(self, user_id: str) -> JsonObject | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT d.deck_id, d.name, d.card_payload_json, d.updated_at
                    FROM user_preferences AS p
                    JOIN decks AS d ON d.deck_id = p.selected_deck_id
                    WHERE p.user_id = ?
                    """,
                    (user_id,),
                ).fetchone()

        if row is None:
            return None

        return {
            "deck_id": str(row["deck_id"]),
            "name": str(row["name"]),
            "card_payload_json": str(row["card_payload_json"]),
            "updated_at": float(row["updated_at"]),
        }
