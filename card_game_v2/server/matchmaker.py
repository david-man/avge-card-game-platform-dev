from __future__ import annotations

import uuid

from ..avge_abstracts.AVGECard import AVGECard
from ..constants import User
from . import protocol
from .session import GameSession, Transport, safe_send


class Matchmaker:
    '''Pairs the first two waiting connections into a new GameSession; owns the game_id ->
    GameSession registry, the account_id -> (game_id, User) registry for account-based
    reconnection, and the account_id -> currently-active-websocket registry for session
    precedence (a newer login for the same account supersedes an older one). Supports multiple
    concurrent games - each pair of joiners gets its own session, independent of any others.'''

    def __init__(self):
        self.sessions: dict[str, GameSession] = {}
        self._active_game_by_account: dict[str, tuple[str, User]] = {}
        self._active_connections: dict[str, Transport] = {}
        self._waiting: GameSession | None = None

    async def claim(self, account_id: str, websocket: Transport) -> None:
        '''Registers websocket as this account's current active connection. If the account
        already had a DIFFERENT active connection, the newer one wins: the old one is notified
        and closed, which naturally flows into its own WebSocketDisconnect handling in
        ws_routes.py (session.detach(), etc.) - no special game-ending logic needed here.'''
        old = self._active_connections.get(account_id)
        self._active_connections[account_id] = websocket
        if old is not None and old is not websocket:
            await safe_send(old, protocol.LoggedOutElsewhereMessage().model_dump())
            try:
                await old.close()
            except Exception:
                pass

    def release(self, account_id: str, websocket: Transport) -> None:
        '''Called when a connection closes. Only clears the registry if `websocket` is still the
        currently-registered one - an already-superseded connection's belated cleanup must not
        wipe out the new connection's registration (claim() already overwrote the entry
        synchronously before the old socket's close was ever awaited, so this can't race it).'''
        if self._active_connections.get(account_id) is websocket:
            del self._active_connections[account_id]

    def find_active_game(self, account_id: str) -> tuple[GameSession, User] | None:
        '''Looks up the account's current live session, if any. join() calls this itself now, so
        callers no longer need to check first - kept as its own method since ws_routes.py also
        uses it directly on the initial-connection path, before ever considering join().'''
        entry = self._active_game_by_account.get(account_id)
        if entry is None:
            return None
        game_id, user = entry
        session = self.sessions.get(game_id)
        if session is None:
            del self._active_game_by_account[account_id]
            return None
        return session, user

    async def join(
        self, account_id: str, deck: list[type[AVGECard]],
    ) -> tuple[GameSession, User]:
        '''Called when an account sends "join". `deck` is that account's own resolved, shuffled
        deck (server/decks.py's build_game_deck output) - required, not defaulted, so a caller can
        never accidentally queue someone with no deck of their own (see ws_routes.py's
        _resolve_selected_deck(), which is what actually enforces "you need a selected deck to
        play" before this is ever called). Returns the (session, user) it's placed into - the
        account's already-active session if it has one (so calling this more than once for the
        same account, e.g. a duplicate "join" message, can never seat one account twice - and
        never re-resolves their deck either, since a reconnect to a live game must use whatever
        deck the game already started with), or a freshly paired/created one otherwise. The caller
        (ws_routes.py) is responsible for calling session.attach(user, websocket) immediately
        after this returns, and - when this call paired two players (PLAYER_2's return) - for
        calling session.begin_running() only once both clients have received game_start, so no
        event traffic can race ahead of it.'''
        found = self.find_active_game(account_id)
        if found is not None:
            return found

        if self._waiting is not None and not self._waiting.finished:
            session = self._waiting
            self._waiting = None
            # Registering the account (both the seat's own account_id and the matchmaker's own
            # account_id -> session lookup) BEFORE awaiting prepare() closes a small pre-existing
            # gap: a duplicate "join" for this same account arriving while prepare() is still
            # in-flight used to find neither _waiting (already cleared above) nor a registry entry
            # (previously set one line after this await), and could spin up a stray third session.
            session.seats[User.PLAYER_2].account_id = account_id
            session.seats[User.PLAYER_2].deck = deck
            self._active_game_by_account[account_id] = (session.id, User.PLAYER_2)
            session.configure_decks()
            await session.prepare()
            return session, User.PLAYER_2

        session = GameSession(str(uuid.uuid4()), self._on_session_finished)
        self.sessions[session.id] = session
        session.seats[User.PLAYER_1].account_id = account_id
        session.seats[User.PLAYER_1].deck = deck
        self._active_game_by_account[account_id] = (session.id, User.PLAYER_1)
        self._waiting = session
        return session, User.PLAYER_1

    def _on_session_finished(self, game_id: str) -> None:
        session = self.sessions.pop(game_id, None)
        if session is not None:
            for seat in session.seats.values():
                if seat.account_id is not None:
                    self._active_game_by_account.pop(seat.account_id, None)
        if self._waiting is not None and self._waiting.id == game_id:
            self._waiting = None
