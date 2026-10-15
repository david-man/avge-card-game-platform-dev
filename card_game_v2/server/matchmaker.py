from __future__ import annotations

import re
import secrets
import uuid

from ..avge_abstracts.AVGECard import AVGECard, AVGECharacterCard
from ..constants import INITIAL_HAND_SIZE, SETUP_BLOCKED_CARDS, User
from . import protocol
from .session import GameSession, Transport, safe_send

PRIVATE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PRIVATE_CODE_LENGTH = 10


def normalize_private_code(code: str) -> str:
    normalized = re.sub(r"[\s-]", "", code.upper())
    if len(normalized) != PRIVATE_CODE_LENGTH or any(
        char not in PRIVATE_CODE_ALPHABET for char in normalized
    ):
        raise ValueError("Enter a valid private game code.")
    return normalized


def _validate_opening_deck(deck: list[type[AVGECard]]) -> None:
    opening_eligible = [card for card in deck if card.__name__ not in SETUP_BLOCKED_CARDS]
    if not any(issubclass(card, AVGECharacterCard) for card in opening_eligible):
        raise ValueError("A deck needs a character eligible to start setup.")
    if len(opening_eligible) < INITIAL_HAND_SIZE + 1:
        raise ValueError("A deck needs five eligible opening hand cards.")


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
        self._private_waiting: dict[str, GameSession] = {}
        self._issued_private_codes: set[str] = set()

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
        (ws_routes.py) attaches each socket and sends setup_start when both seats are filled;
        GameSession starts gameplay only after both setup_done submissions.'''
        found = self.find_active_game(account_id)
        if found is not None:
            return found

        _validate_opening_deck(deck)

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

    def create_private(
        self, account_id: str, deck: list[type[AVGECard]],
    ) -> tuple[GameSession, User]:
        if self.find_active_game(account_id) is not None:
            raise ValueError("You are already in a game.")
        _validate_opening_deck(deck)
        while True:
            raw_code = "".join(secrets.choice(PRIVATE_CODE_ALPHABET) for _ in range(PRIVATE_CODE_LENGTH))
            if raw_code not in self._issued_private_codes:
                break
        self._issued_private_codes.add(raw_code)
        session = GameSession(str(uuid.uuid4()), self._on_session_finished)
        session.match_mode = "private"
        session.invite_code = f"{raw_code[:5]}-{raw_code[5:]}"
        session.seats[User.PLAYER_1].account_id = account_id
        session.seats[User.PLAYER_1].deck = deck
        self.sessions[session.id] = session
        self._active_game_by_account[account_id] = (session.id, User.PLAYER_1)
        self._private_waiting[raw_code] = session
        return session, User.PLAYER_1

    async def join_private(
        self, account_id: str, deck: list[type[AVGECard]], code: str,
    ) -> tuple[GameSession, User]:
        if self.find_active_game(account_id) is not None:
            raise ValueError("You are already in a game.")
        raw_code = normalize_private_code(code)
        session = self._private_waiting.get(raw_code)
        if session is None or session.finished or session.stage != "waiting":
            raise ValueError("That private game code is invalid or no longer available.")
        if session.seats[User.PLAYER_1].account_id == account_id:
            raise ValueError("You cannot join your own private game.")
        _validate_opening_deck(deck)

        # Consume the code and claim the seat before the first await, so concurrent joiners
        # cannot both enter the same room. A failed deck check above leaves the code available.
        del self._private_waiting[raw_code]
        session.seats[User.PLAYER_2].account_id = account_id
        session.seats[User.PLAYER_2].deck = deck
        self._active_game_by_account[account_id] = (session.id, User.PLAYER_2)
        try:
            session.configure_decks()
            await session.prepare()
        except Exception:
            session.finished = True
            self._on_session_finished(session.id)
            host = session.seats[User.PLAYER_1]
            if host.connected and host.websocket is not None:
                await safe_send(host.websocket, protocol.LeftMessage().model_dump())
                await safe_send(host.websocket, protocol.ErrorMessage(
                    code="private_start_failed", message="The private game could not start. Create a new one.",
                ).model_dump())
            raise
        return session, User.PLAYER_2

    def leave_waiting(self, account_id: str) -> bool:
        '''Cancels the queued game `account_id` opened, if it is still the lone occupant of the
        waiting session. Returns False (changing nothing) once an opponent has paired in - join()
        clears `_waiting` synchronously before it awaits prepare(), so a leave landing mid-pairing
        loses cleanly and the game starts as normal.'''
        found = self.find_active_game(account_id)
        if found is None or found[1] != User.PLAYER_1:
            return False
        session = found[0]
        if session.finished or session.stage != "waiting":
            return False
        if session.seats[User.PLAYER_2].account_id is not None:
            return False
        session.finished = True
        self._on_session_finished(session.id)
        return True

    def cancel_private_on_disconnect(self, account_id: str, websocket: Transport) -> None:
        found = self.find_active_game(account_id)
        if found is None:
            return
        session, user = found
        if (
            user == User.PLAYER_1
            and session.match_mode == "private"
            and session.stage == "waiting"
            and session.seats[user].websocket is websocket
        ):
            self.leave_waiting(account_id)

    def _on_session_finished(self, game_id: str) -> None:
        session = self.sessions.pop(game_id, None)
        if session is not None:
            for seat in session.seats.values():
                if seat.account_id is not None:
                    self._active_game_by_account.pop(seat.account_id, None)
        if self._waiting is not None and self._waiting.id == game_id:
            self._waiting = None
        if session is not None and session.invite_code is not None:
            code = normalize_private_code(session.invite_code)
            if self._private_waiting.get(code) is session:
                del self._private_waiting[code]
