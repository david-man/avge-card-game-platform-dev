from __future__ import annotations

import asyncio
import contextlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import deck_rules


@dataclass(frozen=True)
class StoredDeck:
    deck_id: str
    account_id: str
    name: str
    cards: list[str]
    created_at: float
    updated_at: float


class DeckStore:
    '''Per-account saved decks, backed by SQLite (stdlib sqlite3, not aiosqlite - not a dependency
    of this project today, and asyncio.to_thread is already this codebase's established I/O-
    offload idiom - see accounts.py). Unlike AccountStore, this does NOT load everything into
    memory at construction: decks are per-account and unbounded in aggregate, so every method
    queries the database directly (one short-lived connection per call - the simplest thread-safe
    option given asyncio.to_thread runs on arbitrary pool threads).'''

    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize_schema(self) -> None:
        with contextlib.closing(self._connect()) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS decks (
                    deck_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    cards_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            ''')
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_decks_account_id ON decks(account_id)"
            )
            conn.execute('''
                CREATE TABLE IF NOT EXISTS deck_preferences (
                    account_id TEXT PRIMARY KEY,
                    selected_deck_id TEXT,
                    updated_at REAL NOT NULL
                )
            ''')
            conn.commit()

    # --- Reads ---

    async def list_decks(self, account_id: str) -> list[StoredDeck]:
        return await asyncio.to_thread(self._list_decks_sync, account_id)

    def _list_decks_sync(self, account_id: str) -> list[StoredDeck]:
        with contextlib.closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM decks WHERE account_id = ? ORDER BY created_at ASC",
                (account_id,),
            ).fetchall()
            return [_row_to_deck(row) for row in rows]

    async def get_deck(self, account_id: str, deck_id: str) -> StoredDeck | None:
        return await asyncio.to_thread(self._get_deck_sync, account_id, deck_id)

    def _get_deck_sync(self, account_id: str, deck_id: str) -> StoredDeck | None:
        with contextlib.closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM decks WHERE account_id = ? AND deck_id = ?",
                (account_id, deck_id),
            ).fetchone()
            return _row_to_deck(row) if row is not None else None

    async def get_selected_deck_id(self, account_id: str) -> str | None:
        return await asyncio.to_thread(self._get_selected_deck_id_sync, account_id)

    def _get_selected_deck_id_sync(self, account_id: str) -> str | None:
        with contextlib.closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT selected_deck_id FROM deck_preferences WHERE account_id = ?",
                (account_id,),
            ).fetchone()
            return row["selected_deck_id"] if row is not None else None

    async def get_selected_deck(self, account_id: str) -> StoredDeck | None:
        return await asyncio.to_thread(self._get_selected_deck_sync, account_id)

    def _get_selected_deck_sync(self, account_id: str) -> StoredDeck | None:
        with contextlib.closing(self._connect()) as conn:
            row = conn.execute(
                '''
                SELECT decks.* FROM decks
                JOIN deck_preferences ON deck_preferences.selected_deck_id = decks.deck_id
                WHERE deck_preferences.account_id = ? AND decks.account_id = ?
                ''',
                (account_id, account_id),
            ).fetchone()
            return _row_to_deck(row) if row is not None else None

    # --- Writes ---

    async def create_deck(self, account_id: str, name: str, cards: list[str]) -> StoredDeck:
        return await asyncio.to_thread(self._create_deck_sync, account_id, name, cards)

    def _create_deck_sync(self, account_id: str, name: str, cards: list[str]) -> StoredDeck:
        clean_name = deck_rules.validate_deck_name(name)
        clean_cards = deck_rules.validate_deck_cards(cards)
        now = time.time()
        deck_id = str(uuid.uuid4())
        with contextlib.closing(self._connect()) as conn:
            # BEGIN IMMEDIATE takes the write lock up front, so the count-then-insert below is
            # genuinely atomic across threads/processes - unlike AccountStore's check-then-insert
            # trick (accounts.py), which only works because it stays fully synchronous on a single
            # event loop. asyncio.to_thread calls really can interleave across worker threads.
            conn.execute("BEGIN IMMEDIATE")
            try:
                count = conn.execute(
                    "SELECT COUNT(*) AS n FROM decks WHERE account_id = ?", (account_id,),
                ).fetchone()["n"]
                if count >= deck_rules.MAX_DECKS_PER_ACCOUNT:
                    raise deck_rules.DeckLimitError()
                conn.execute(
                    "INSERT INTO decks (deck_id, account_id, name, cards_json, created_at, "
                    "updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (deck_id, account_id, clean_name, json.dumps(clean_cards), now, now),
                )
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return StoredDeck(deck_id, account_id, clean_name, clean_cards, now, now)

    async def update_deck(
        self, account_id: str, deck_id: str, name: str, cards: list[str],
    ) -> StoredDeck | None:
        return await asyncio.to_thread(self._update_deck_sync, account_id, deck_id, name, cards)

    def _update_deck_sync(
        self, account_id: str, deck_id: str, name: str, cards: list[str],
    ) -> StoredDeck | None:
        clean_name = deck_rules.validate_deck_name(name)
        clean_cards = deck_rules.validate_deck_cards(cards)
        now = time.time()
        with contextlib.closing(self._connect()) as conn:
            cursor = conn.execute(
                "UPDATE decks SET name = ?, cards_json = ?, updated_at = ? "
                "WHERE account_id = ? AND deck_id = ?",
                (clean_name, json.dumps(clean_cards), now, account_id, deck_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM decks WHERE account_id = ? AND deck_id = ?",
                (account_id, deck_id),
            ).fetchone()
            return _row_to_deck(row)

    async def delete_deck(self, account_id: str, deck_id: str) -> bool:
        return await asyncio.to_thread(self._delete_deck_sync, account_id, deck_id)

    def _delete_deck_sync(self, account_id: str, deck_id: str) -> bool:
        with contextlib.closing(self._connect()) as conn:
            cursor = conn.execute(
                "DELETE FROM decks WHERE account_id = ? AND deck_id = ?",
                (account_id, deck_id),
            )
            deleted = cursor.rowcount > 0
            if deleted:
                # A deleted deck can never stay "selected" - clear it in the same transaction
                # rather than leaving deck_preferences pointing at a row that no longer exists.
                conn.execute(
                    "UPDATE deck_preferences SET selected_deck_id = NULL, updated_at = ? "
                    "WHERE account_id = ? AND selected_deck_id = ?",
                    (time.time(), account_id, deck_id),
                )
            conn.commit()
            return deleted

    async def set_selected_deck(self, account_id: str, deck_id: str | None) -> bool:
        return await asyncio.to_thread(self._set_selected_deck_sync, account_id, deck_id)

    def _set_selected_deck_sync(self, account_id: str, deck_id: str | None) -> bool:
        with contextlib.closing(self._connect()) as conn:
            if deck_id is not None:
                owned = conn.execute(
                    "SELECT 1 FROM decks WHERE account_id = ? AND deck_id = ?",
                    (account_id, deck_id),
                ).fetchone()
                if owned is None:
                    return False
            conn.execute(
                '''
                INSERT INTO deck_preferences (account_id, selected_deck_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    selected_deck_id = excluded.selected_deck_id,
                    updated_at = excluded.updated_at
                ''',
                (account_id, deck_id, time.time()),
            )
            conn.commit()
            return True


def _row_to_deck(row: sqlite3.Row) -> StoredDeck:
    cards: list[str] = json.loads(row["cards_json"])
    return StoredDeck(
        deck_id=row["deck_id"], account_id=row["account_id"], name=row["name"], cards=cards,
        created_at=row["created_at"], updated_at=row["updated_at"],
    )
