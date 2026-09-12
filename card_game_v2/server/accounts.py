from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Account:
    account_id: str
    username: str  # original typed casing, for display
    auth_token: str


class AccountStore:
    '''Username-only, open-registration accounts, persisted to a JSON file so they (unlike
    everything else in this system - games, sessions, matchmaker state) survive a server restart.
    No password: with open registration, auth_token is a "remember me" convenience for silent
    re-auth from the browser's localStorage, not a security boundary.'''

    def __init__(self, path: Path):
        self._path = path
        self._by_key: dict[str, Account] = {}
        self._by_token: dict[str, Account] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = json.loads(self._path.read_text())
        for entry in raw:
            account = Account(entry["account_id"], entry["username"], entry["auth_token"])
            self._by_key[_key(account.username)] = account
            self._by_token[account.auth_token] = account

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload: list[dict[str, Any]] = [
            {"account_id": a.account_id, "username": a.username, "auth_token": a.auth_token}
            for a in self._by_key.values()
        ]
        tmp_path = self._path.with_name(self._path.name + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2))
        tmp_path.replace(self._path)

    def _login_by_username_sync(self, username: str) -> tuple[Account | None, bool]:
        '''The check-then-insert itself has no `await` in it, so it's atomic under asyncio's
        cooperative scheduling as long as it stays fully synchronous - only the (slow, blocking)
        _persist() disk write below is offloaded to a thread. Splitting it this way (instead of
        offloading the whole method, as an earlier version did) avoids a real race: two concurrent
        registrations of the same brand-new username on separate worker threads could otherwise
        both pass the "not in _by_key yet" check before either wrote its own Account in, leaving
        one of the two tokens orphaned from _by_key.'''
        stripped = username.strip()
        if not stripped:
            return None, False
        key = _key(stripped)
        existing = self._by_key.get(key)
        if existing is not None:
            return existing, False
        account = Account(str(uuid.uuid4()), stripped, str(uuid.uuid4()))
        self._by_key[key] = account
        self._by_token[account.auth_token] = account
        return account, True

    async def login_by_username(self, username: str) -> Account | None:
        '''Create-if-absent by (case-insensitive) username; returns the SAME account and
        auth_token on repeat logins - never rotates the token, since a second tab/device may
        already have the old one cached. Returns None only for an empty-after-strip username.'''
        account, is_new = self._login_by_username_sync(username)
        if is_new:
            await asyncio.to_thread(self._persist)
        return account

    def login_by_token(self, token: str) -> Account | None:
        return self._by_token.get(token)


def _key(username: str) -> str:
    return username.strip().lower()
