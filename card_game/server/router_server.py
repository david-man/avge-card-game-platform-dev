from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from typing import Any, Callable, Literal, cast
from card_game.server.server_types import JsonObject, CommandPayload
from uuid import uuid4
import importlib
import json
import os
import random
import urllib.error
import urllib.request

from flask import Flask, jsonify, make_response, request

try:
    _flask_socketio = importlib.import_module("flask_socketio")
    SocketIO = getattr(_flask_socketio, "SocketIO", None)
    emit = getattr(_flask_socketio, "emit", None)
except Exception:  # pragma: no cover - optional websocket transport dependency
    SocketIO = None
    emit = None

from ..avge_abstracts.AVGECards import AVGECard
from ..avge_abstracts.AVGECards import AVGECharacterCard
from ..avge_abstracts.AVGECards import AVGEItemCard
from ..avge_abstracts.AVGECards import AVGEToolCard
from ..catalog import *

try:
    from .workers.room_worker import RoomWorker
    from .workers.room_worker import RoomWorkerSnapshot
except ImportError:  # pragma: no cover - direct script execution fallback
    from card_game.server.workers.room_worker import RoomWorker  # type: ignore
    from card_game.server.workers.room_worker import RoomWorkerSnapshot  # type: ignore

try:
    from .storage.router_storage import RouterStorage
except ImportError:  # pragma: no cover - direct script execution fallback
    from card_game.server.storage.router_storage import RouterStorage  # type: ignore


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    raw = os.getenv(name)
    parsed = default
    if raw is not None:
        try:
            parsed = int(raw.strip())
        except Exception:
            parsed = default

    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _env_csv(name: str) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


type SocketIOAsyncMode = Literal["threading", "eventlet", "gevent", "gevent_uwsgi"]


type RoomTransportMode = Literal["pipe"]


def _env_socketio_async_mode(name: str, default: SocketIOAsyncMode) -> SocketIOAsyncMode:
    raw = os.getenv(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in {"threading", "eventlet", "gevent", "gevent_uwsgi"}:
        return cast(SocketIOAsyncMode, normalized)
    return default

SESSION_COOKIE_NAME = "avge_session"
SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30
ROOM_FINISH_GRACE_SECONDS = 5
ROUTER_HOST = os.getenv("ROUTER_HOST", "0.0.0.0")
ROUTER_PORT = _env_int("ROUTER_PORT", 5600, minimum=1, maximum=65535)
ROUTER_DEBUG = _env_bool("ROUTER_DEBUG", False)
ROUTER_USE_RELOADER = _env_bool("ROUTER_USE_RELOADER", False)
ROUTER_SOCKETIO_ASYNC_MODE = _env_socketio_async_mode("ROUTER_SOCKETIO_ASYNC_MODE", "gevent")
ROUTER_ALLOWED_ORIGINS = _env_csv("ROUTER_ALLOWED_ORIGINS")
ROUTER_COOKIE_SECURE = _env_bool("ROUTER_COOKIE_SECURE", False)
ROUTER_COOKIE_SAMESITE = os.getenv("ROUTER_COOKIE_SAMESITE", "Lax").strip() or "Lax"

ROOM_BIND_HOST = ROUTER_HOST
ROOM_TRANSPORT_MODE: RoomTransportMode = "pipe"
ROUTER_DB_PATH = os.getenv(
    "ROUTER_DB_PATH",
    os.path.join(os.path.dirname(__file__), "router.sqlite3"),
)
DECK_REQUIRED_CARD_COUNT = 20
DECK_MAX_ITEM_OR_TOOL_COPIES = 2
DECK_MAX_OTHER_COPIES = 1


def _resolve_catalog_card_class(card_id: str) -> type[AVGECard] | None:
    symbol = globals().get(card_id)
    if not isinstance(symbol, type):
        return None
    if not issubclass(symbol, AVGECard):
        return None
    return symbol


def _validate_deck_cards(
    raw_cards: list[Any],
    *,
    require_exact_count: bool = True,
    require_at_least_one_character: bool = False,
) -> str | None:
    normalized_cards: list[str] = []
    copies_by_card_id: dict[str, int] = {}
    has_character_card = False

    for raw_card_id in raw_cards:
        if not isinstance(raw_card_id, str) or not raw_card_id.strip():
            return "cards must contain non-empty string IDs."

        card_id = raw_card_id.strip()
        resolved_symbol = _resolve_catalog_card_class(card_id)
        if resolved_symbol is None:
            return f"Unknown card ID: {card_id}"
        if issubclass(resolved_symbol, AVGECharacterCard):
            has_character_card = True

        next_count = copies_by_card_id.get(card_id, 0) + 1
        max_copies = (
            DECK_MAX_ITEM_OR_TOOL_COPIES
            if issubclass(resolved_symbol, AVGEItemCard) or issubclass(resolved_symbol, AVGEToolCard)
            else DECK_MAX_OTHER_COPIES
        )
        if next_count > max_copies:
            if max_copies == DECK_MAX_ITEM_OR_TOOL_COPIES:
                return f"{card_id} exceeds max copies ({DECK_MAX_ITEM_OR_TOOL_COPIES}) for item/tool cards."
            return f"{card_id} exceeds max copies ({DECK_MAX_OTHER_COPIES})."

        copies_by_card_id[card_id] = next_count
        normalized_cards.append(card_id)

    if require_exact_count and len(normalized_cards) != DECK_REQUIRED_CARD_COUNT:
        return f"Deck must contain exactly {DECK_REQUIRED_CARD_COUNT} cards."

    if require_at_least_one_character and not has_character_card:
        return "Deck must contain at least 1 character card."

    return None


@dataclass
class SessionIdentity:
    session_id: str
    user_id: str
    username: str
    created_at: float
    last_seen_at: float
    current_room_id: str | None = None


@dataclass
class QueueEntry:
    session_id: str
    enqueued_at: float


@dataclass
class RoomRecord:
    room_id: str
    player_session_ids: tuple[str, str]
    created_at: float
    bind_host: str
    port: int
    transport_mode: RoomTransportMode = "pipe"
    status: str = "running"
    finished_at: float | None = None
    retain_until: float | None = None
    finish_reason: str | None = None
    worker: RoomWorker | None = None


@dataclass
class RouterState:
    sessions_by_id: dict[str, SessionIdentity] = field(default_factory=dict)
    active_session_id_by_user_id: dict[str, str] = field(default_factory=dict)
    superseded_session_ids: set[str] = field(default_factory=set)
    auth_socket_sids_by_session_id: dict[str, set[str]] = field(default_factory=dict)
    game_session_id_by_socket_sid: dict[str, str] = field(default_factory=dict)
    game_session_id_by_client_id: dict[str, str] = field(default_factory=dict)
    rooms_by_id: dict[str, RoomRecord] = field(default_factory=dict)
    room_id_by_session_id: dict[str, str] = field(default_factory=dict)
    queue: list[QueueEntry] = field(default_factory=list)


class MatchmakingRouter:
    def __init__(self, db_path: str | None = None) -> None:
        self._state = RouterState()
        self._lock = RLock()
        self._storage = RouterStorage(db_path or ROUTER_DB_PATH)
        self._superseded_notifier: Callable[[str, list[str]], None] | None = None

    def set_superseded_notifier(self, notifier: Callable[[str, list[str]], None] | None) -> None:
        with self._lock:
            self._superseded_notifier = notifier

    def register_auth_socket(self, session_id: str, socket_sid: str) -> tuple[bool, JsonObject]:
        with self._lock:
            session = self._ensure_session_locked(session_id)
            if session is None:
                error_body, _ = self.session_error_payload(session_id)
                return False, error_body

            for sid_set in self._state.auth_socket_sids_by_session_id.values():
                sid_set.discard(socket_sid)

            sid_set = self._state.auth_socket_sids_by_session_id.setdefault(session.session_id, set())
            sid_set.add(socket_sid)
            return True, {"ok": True, "session_id": session.session_id}

    def unregister_auth_socket(self, socket_sid: str) -> None:
        with self._lock:
            empty_keys: list[str] = []
            for session_id, sid_set in self._state.auth_socket_sids_by_session_id.items():
                sid_set.discard(socket_sid)
                if not sid_set:
                    empty_keys.append(session_id)

            for session_id in empty_keys:
                self._state.auth_socket_sids_by_session_id.pop(session_id, None)

    def register_game_socket(self, session_id: str, socket_sid: str) -> tuple[bool, JsonObject]:
        with self._lock:
            session = self._ensure_session_locked(session_id)
            if session is None:
                error_body, _ = self.session_error_payload(session_id)
                return False, error_body

            room = self._active_room_for_session_locked(session_id)
            if room is None:
                return False, {
                    'ok': False,
                    'error': 'No active room for session.',
                    'error_code': 'no_active_room',
                }

            self._state.game_session_id_by_socket_sid[socket_sid] = session_id
            return True, {
                'ok': True,
                'session_id': session_id,
                'room_id': room.room_id,
            }

    def unregister_game_socket(self, socket_sid: str) -> str | None:
        with self._lock:
            return self._state.game_session_id_by_socket_sid.pop(socket_sid, None)

    def game_session_for_socket(self, socket_sid: str) -> str | None:
        with self._lock:
            value = self._state.game_session_id_by_socket_sid.get(socket_sid)
            return value if isinstance(value, str) and value else None

    def register_game_client(self, client_id: str, session_id: str) -> tuple[bool, JsonObject]:
        with self._lock:
            session = self._ensure_session_locked(session_id)
            if session is None:
                error_body, _ = self.session_error_payload(session_id)
                return False, error_body

            room = self._active_room_for_session_locked(session_id)
            if room is None:
                return False, {
                    'ok': False,
                    'error': 'No active room for session.',
                    'error_code': 'no_active_room',
                }

            self._state.game_session_id_by_client_id[client_id] = session_id
            return True, {
                'ok': True,
                'client_id': client_id,
                'session_id': session_id,
                'room_id': room.room_id,
            }

    def unregister_game_client(self, client_id: str) -> str | None:
        with self._lock:
            return self._state.game_session_id_by_client_id.pop(client_id, None)

    def game_session_for_client(self, client_id: str) -> str | None:
        with self._lock:
            value = self._state.game_session_id_by_client_id.get(client_id)
            return value if isinstance(value, str) and value else None

    def room_worker_for_session(self, session_id: str) -> tuple[RoomWorker | None, JsonObject | None]:
        with self._lock:
            session = self._ensure_session_locked(session_id)
            if session is None:
                error_body, _ = self.session_error_payload(session_id)
                return None, error_body

            room = self._active_room_for_session_locked(session_id)
            if room is None:
                return None, {
                    'ok': False,
                    'error': 'No active room for session.',
                    'error_code': 'no_active_room',
                }

            worker = room.worker
            if worker is None:
                return None, {
                    'ok': False,
                    'error': 'Room worker unavailable.',
                    'error_code': 'room_worker_unavailable',
                }

            return worker, None

    def dispatch_pipe_command_for_session(
        self,
        session_id: str,
        *,
        method: str,
        params: JsonObject,
        timeout_seconds: float = 2.0,
    ) -> tuple[bool, JsonObject]:
        worker, lookup_error = self.room_worker_for_session(session_id)
        if lookup_error is not None:
            return False, lookup_error
        assert worker is not None

        try:
            response = worker.request(method, params, timeout_seconds=timeout_seconds)
            return True, response if isinstance(response, dict) else {'ok': True}
        except TimeoutError:
            return False, {
                'ok': False,
                'error': f'Room pipe command timed out: {method}',
                'error_code': 'room_pipe_timeout',
            }
        except Exception as exc:
            return False, {
                'ok': False,
                'error': str(exc) or f'Room pipe command failed: {method}',
                'error_code': 'room_pipe_failed',
            }

    def handle_room_worker_event(self, room_id: str, event_type: str, payload: JsonObject) -> None:
        if event_type == 'socket_emit':
            if socketio is None:
                return
            event_name = payload.get('event')
            if not isinstance(event_name, str) or not event_name.strip():
                return
            socket_payload = payload.get('payload')
            target_sid = payload.get('to')
            if isinstance(target_sid, str) and target_sid.strip():
                socketio.emit(event_name.strip(), socket_payload, to=target_sid.strip())
            else:
                socketio.emit(event_name.strip(), socket_payload)
            return

        if event_type == 'room_finished':
            reason_raw = payload.get('reason')
            reason = reason_raw.strip() if isinstance(reason_raw, str) and reason_raw.strip() else 'finished'
            self.mark_room_finished(room_id, reason)

    def login(self, username: str, existing_session_id: str | None) -> SessionIdentity:
        now = monotonic()
        user_id = self._storage.get_or_create_user(username)

        with self._lock:
            self._cleanup_expired_rooms_locked(now)

            reusable_session_id: str | None = None

            if existing_session_id:
                existing = self._state.sessions_by_id.get(existing_session_id)
                if existing is not None and existing.user_id == user_id:
                    reusable_session_id = existing.session_id

                stored_session = self._storage.get_session(existing_session_id)
                if stored_session is not None and stored_session.user_id == user_id:
                    reusable_session_id = stored_session.session_id

            prior_active_session_id = self._state.active_session_id_by_user_id.get(user_id)
            session_id_for_room_transfer = (
                prior_active_session_id
                if isinstance(prior_active_session_id, str)
                and prior_active_session_id
                and prior_active_session_id != reusable_session_id
                else None
            )

            self._supersede_user_sessions_locked(
                user_id=user_id,
                keep_session_id=reusable_session_id,
                preserve_room_session_id=session_id_for_room_transfer,
            )

            if reusable_session_id:
                reusable = self._state.sessions_by_id.get(reusable_session_id)
                if reusable is None:
                    stored_reusable = self._storage.get_session(reusable_session_id)
                    if stored_reusable is not None:
                        reusable = SessionIdentity(
                            session_id=stored_reusable.session_id,
                            user_id=stored_reusable.user_id,
                            username=stored_reusable.username,
                            created_at=now,
                            last_seen_at=now,
                            current_room_id=self._state.room_id_by_session_id.get(stored_reusable.session_id),
                        )
                        self._state.sessions_by_id[reusable.session_id] = reusable

                if reusable is not None and reusable.user_id == user_id:
                    reusable.username = username
                    reusable.last_seen_at = now
                    self._storage.create_or_update_session(
                        session_id=reusable.session_id,
                        user_id=user_id,
                        ttl_seconds=SESSION_COOKIE_MAX_AGE_SECONDS,
                    )
                    self._state.active_session_id_by_user_id[user_id] = reusable.session_id
                    self._state.superseded_session_ids.discard(reusable.session_id)
                    return reusable

            session = SessionIdentity(
                session_id=uuid4().hex,
                user_id=user_id,
                username=username,
                created_at=now,
                last_seen_at=now,
            )
            self._storage.create_or_update_session(
                session_id=session.session_id,
                user_id=user_id,
                ttl_seconds=SESSION_COOKIE_MAX_AGE_SECONDS,
            )
            self._state.sessions_by_id[session.session_id] = session
            self._state.active_session_id_by_user_id[user_id] = session.session_id
            self._state.superseded_session_ids.discard(session.session_id)

            if isinstance(session_id_for_room_transfer, str) and session_id_for_room_transfer:
                handoff = self._transfer_room_assignment_locked(
                    from_session_id=session_id_for_room_transfer,
                    to_session_id=session.session_id,
                )
                if handoff is not None:
                    room, slot = handoff
                    self._notify_room_session_takeover(room, slot, session_id_for_room_transfer, session.session_id)

            return session

    def session(self, session_id: str) -> SessionIdentity | None:
        with self._lock:
            return self._ensure_session_locked(session_id)

    def logout(self, session_id: str) -> bool:
        with self._lock:
            session = self._ensure_session_locked(session_id)
            if session is None:
                return False

            self._state.queue = [entry for entry in self._state.queue if entry.session_id != session_id]
            self._state.sessions_by_id.pop(session_id, None)
            self._state.auth_socket_sids_by_session_id.pop(session_id, None)
            if self._state.active_session_id_by_user_id.get(session.user_id) == session_id:
                self._state.active_session_id_by_user_id.pop(session.user_id, None)
            self._state.superseded_session_ids.discard(session_id)
            self._storage.revoke_session(session_id)
            return True

    def bootstrap_session(self, username: str, existing_session_id: str | None) -> SessionIdentity:
        now = monotonic()
        user_id = self._storage.get_or_create_user(username)
        with self._lock:
            self._cleanup_expired_rooms_locked(now)

            reusable_session_id: str | None = None

            if existing_session_id:
                existing = self._state.sessions_by_id.get(existing_session_id)
                if existing is not None and existing.user_id == user_id:
                    reusable_session_id = existing.session_id

                stored_session = self._storage.get_session(existing_session_id)
                if stored_session is not None and stored_session.user_id == user_id:
                    reusable_session_id = stored_session.session_id

            prior_active_session_id = self._state.active_session_id_by_user_id.get(user_id)
            session_id_for_room_transfer = (
                prior_active_session_id
                if isinstance(prior_active_session_id, str)
                and prior_active_session_id
                and prior_active_session_id != reusable_session_id
                else None
            )

            self._supersede_user_sessions_locked(
                user_id=user_id,
                keep_session_id=reusable_session_id,
                preserve_room_session_id=session_id_for_room_transfer,
            )

            if reusable_session_id:
                reusable = self._state.sessions_by_id.get(reusable_session_id)
                if reusable is None:
                    stored_reusable = self._storage.get_session(reusable_session_id)
                    if stored_reusable is not None:
                        reusable = SessionIdentity(
                            session_id=stored_reusable.session_id,
                            user_id=stored_reusable.user_id,
                            username=username,
                            created_at=now,
                            last_seen_at=now,
                            current_room_id=self._state.room_id_by_session_id.get(stored_reusable.session_id),
                        )
                        self._state.sessions_by_id[reusable.session_id] = reusable

                if reusable is not None and reusable.user_id == user_id:
                    reusable.username = username
                    reusable.last_seen_at = now
                    self._storage.create_or_update_session(
                        session_id=reusable.session_id,
                        user_id=user_id,
                        ttl_seconds=SESSION_COOKIE_MAX_AGE_SECONDS,
                    )
                    self._state.active_session_id_by_user_id[user_id] = reusable.session_id
                    self._state.superseded_session_ids.discard(reusable.session_id)
                    return reusable

            session = SessionIdentity(
                session_id=uuid4().hex,
                user_id=user_id,
                username=username,
                created_at=now,
                last_seen_at=now,
            )
            self._storage.create_or_update_session(
                session_id=session.session_id,
                user_id=user_id,
                ttl_seconds=SESSION_COOKIE_MAX_AGE_SECONDS,
            )
            self._state.sessions_by_id[session.session_id] = session
            self._state.active_session_id_by_user_id[user_id] = session.session_id
            self._state.superseded_session_ids.discard(session.session_id)

            if isinstance(session_id_for_room_transfer, str) and session_id_for_room_transfer:
                handoff = self._transfer_room_assignment_locked(
                    from_session_id=session_id_for_room_transfer,
                    to_session_id=session.session_id,
                )
                if handoff is not None:
                    room, slot = handoff
                    self._notify_room_session_takeover(room, slot, session_id_for_room_transfer, session.session_id)

            return session

    def session_error_payload(self, session_id: str | None) -> tuple[JsonObject, int]:
        if not isinstance(session_id, str) or not session_id.strip():
            return {"ok": False, "error": "session_id is required.", "error_code": "session_id_required"}, 400

        normalized = session_id.strip()
        if normalized in self._state.superseded_session_ids:
            return {
                "ok": False,
                "error": "Session superseded by another login.",
                "error_code": "session_superseded",
            }, 401

        return {"ok": False, "error": "Unknown session.", "error_code": "unknown_session"}, 401

    def enqueue(self, session_id: str) -> JsonObject:
        with self._lock:
            now = monotonic()
            self._cleanup_expired_rooms_locked(now)

            session = self._ensure_session_locked(session_id)
            if session is None:
                error_body, _ = self.session_error_payload(session_id)
                return error_body

            # Only running rooms are considered active assignments for queueing.
            room = self._active_room_for_session_locked(session_id)
            if room is not None:
                session.current_room_id = room.room_id
                return {
                    "ok": True,
                    "queued": False,
                    "room_id": room.room_id,
                    "status": "assigned",
                    "room": self._serialize_room_locked(room),
                }

            selected = self._storage.get_selected_deck(session.user_id)
            if selected is not None:
                selected_cards: list[Any]
                try:
                    parsed_cards = json.loads(str(selected.get("card_payload_json", "[]")))
                except Exception:
                    self._state.queue = [entry for entry in self._state.queue if entry.session_id != session_id]
                    return {
                        "ok": False,
                        "error": "Cannot join queue: invalid selected deck. selected deck payload is invalid JSON.",
                    }

                if not isinstance(parsed_cards, list):
                    self._state.queue = [entry for entry in self._state.queue if entry.session_id != session_id]
                    return {
                        "ok": False,
                        "error": "Cannot join queue: invalid selected deck. selected deck payload is not a card list.",
                    }

                selected_cards = parsed_cards
                deck_error = _validate_deck_cards(
                    selected_cards,
                    require_exact_count=True,
                    require_at_least_one_character=True,
                )
                if deck_error is not None:
                    self._state.queue = [entry for entry in self._state.queue if entry.session_id != session_id]
                    return {
                        "ok": False,
                        "error": f"Cannot join queue: invalid selected deck. {deck_error}",
                    }

            if not any(entry.session_id == session_id for entry in self._state.queue):
                self._state.queue.append(QueueEntry(session_id=session_id, enqueued_at=now))

            assigned_room_id = self._assign_rooms_from_queue_locked(now)
            if assigned_room_id is not None:
                if self._state.room_id_by_session_id.get(session_id) == assigned_room_id:
                    session.current_room_id = assigned_room_id
                    room = self._state.rooms_by_id.get(assigned_room_id)
                    return {
                        "ok": True,
                        "queued": False,
                        "room_id": assigned_room_id,
                        "status": "assigned",
                        "room": self._serialize_room_locked(room) if room is not None else None,
                    }

            position = self._queue_position_locked(session_id)
            return {
                "ok": True,
                "queued": True,
                "queue_position": position,
                "status": "waiting",
            }

    def dequeue(self, session_id: str) -> JsonObject:
        with self._lock:
            before = len(self._state.queue)
            self._state.queue = [entry for entry in self._state.queue if entry.session_id != session_id]
            removed = len(self._state.queue) != before
            return {
                "ok": True,
                "removed": removed,
            }

    def status(self, session_id: str) -> JsonObject:
        with self._lock:
            now = monotonic()
            self._cleanup_expired_rooms_locked(now)

            session = self._ensure_session_locked(session_id)
            if session is None:
                error_body, _ = self.session_error_payload(session_id)
                return error_body

            room = self._active_room_for_session_locked(session_id)
            if room is not None:
                session.current_room_id = room.room_id
                return {
                    "ok": True,
                    "status": "assigned",
                    "session_id": session_id,
                    "username": session.username,
                    "room": self._serialize_room_locked(room),
                }

            position = self._queue_position_locked(session_id)
            return {
                "ok": True,
                "status": "waiting" if position is not None else "idle",
                "session_id": session_id,
                "username": session.username,
                "queue_position": position,
            }

    def rejoin_room(self, session_id: str, room_id: str | None = None) -> JsonObject:
        with self._lock:
            now = monotonic()
            self._cleanup_expired_rooms_locked(now)

            session = self._ensure_session_locked(session_id)
            if session is None:
                error_body, _ = self.session_error_payload(session_id)
                return error_body

            resolved_room_id = room_id or self._state.room_id_by_session_id.get(session_id)
            if resolved_room_id is None:
                return {"ok": False, "error": "No active room for session."}

            room = self._state.rooms_by_id.get(resolved_room_id)
            if room is None:
                return {"ok": False, "error": "Room not found."}

            if room.status != "running":
                # Do not allow reconnecting into retained finished rooms.
                if self._state.room_id_by_session_id.get(session_id) == resolved_room_id:
                    self._state.room_id_by_session_id.pop(session_id, None)
                if session.current_room_id == resolved_room_id:
                    session.current_room_id = None
                return {"ok": False, "error": "Room is not active."}

            if session_id not in room.player_session_ids:
                return {"ok": False, "error": "Session does not belong to this room."}

            session.current_room_id = room.room_id
            return {
                "ok": True,
                "room": self._serialize_room_locked(room),
            }

    def mark_room_finished(self, room_id: str, reason: str) -> JsonObject:
        with self._lock:
            room = self._state.rooms_by_id.get(room_id)
            if room is None:
                return {"ok": False, "error": "Room not found."}

            if room.status != "finished":
                now = monotonic()
                room.status = "finished"
                room.finished_at = now
                room.retain_until = now + ROOM_FINISH_GRACE_SECONDS
                room.finish_reason = reason
                # Winner declaration should drop router assignment immediately,
                # but keep the room process alive so clients can finish the
                # winner UI and return to MainMenu explicitly.
                should_stop_worker = reason not in {"winner_declared"}
                if should_stop_worker and room.worker is not None:
                    room.worker.stop(reason=reason)

            # Finished rooms are retained for diagnostics only; active session
            # assignment should be cleared immediately.
            for session_id in room.player_session_ids:
                if self._state.room_id_by_session_id.get(session_id) == room.room_id:
                    self._state.room_id_by_session_id.pop(session_id, None)
                self._clear_transport_bindings_for_session_locked(session_id)
                session = self._state.sessions_by_id.get(session_id)
                if session is not None and session.current_room_id == room.room_id:
                    session.current_room_id = None

            return {
                "ok": True,
                "room": self._serialize_room_locked(room),
            }

    def _assign_rooms_from_queue_locked(self, now: float) -> str | None:
        last_assigned_room: str | None = None
        while len(self._state.queue) >= 2:
            entry_a = self._state.queue.pop(0)
            entry_b = self._state.queue.pop(0)

            if entry_a.session_id == entry_b.session_id:
                # Defensive guard in case duplicate queue rows slipped through.
                self._state.queue.insert(0, entry_b)
                break

            # Randomize slot assignment so either queued player can become p1.
            p1_entry, p2_entry = (entry_a, entry_b)
            if random.random() < 0.5:
                p1_entry, p2_entry = (entry_b, entry_a)

            room_id = f"room-{uuid4().hex[:12]}"
            room_port = ROUTER_PORT
            room = RoomRecord(
                room_id=room_id,
                player_session_ids=(p1_entry.session_id, p2_entry.session_id),
                created_at=now,
                bind_host=ROOM_BIND_HOST,
                port=room_port,
                transport_mode=ROOM_TRANSPORT_MODE,
                status="running",
            )

            session_a = self._state.sessions_by_id.get(p1_entry.session_id)
            session_b = self._state.sessions_by_id.get(p2_entry.session_id)
            session_a_name = session_a.username if session_a is not None else "Player 1"
            session_b_name = session_b.username if session_b is not None else "Player 2"

            def _selected_cards_for_session(session: SessionIdentity | None) -> list[str] | None:
                if session is None:
                    return None
                selected = self._storage.get_selected_deck(session.user_id)
                if selected is None:
                    return None
                try:
                    parsed = json.loads(str(selected.get('card_payload_json', '[]')))
                except Exception:
                    return None
                if not isinstance(parsed, list):
                    return None
                return [str(card_id) for card_id in parsed if isinstance(card_id, str) and card_id.strip()]

            session_a_selected_cards = _selected_cards_for_session(session_a)
            session_b_selected_cards = _selected_cards_for_session(session_b)

            worker = RoomWorker(
                room_id=room_id,
                player_session_ids=room.player_session_ids,
                host=room.bind_host,
                port=room.port,
                p1_username=session_a_name,
                p2_username=session_b_name,
                p1_selected_cards=session_a_selected_cards,
                p2_selected_cards=session_b_selected_cards,
                transport_mode=ROOM_TRANSPORT_MODE,
                on_finished=self._on_room_worker_finished,
                on_event=self.handle_room_worker_event,
            )
            room.worker = worker
            self._state.rooms_by_id[room_id] = room
            self._state.room_id_by_session_id[p1_entry.session_id] = room_id
            self._state.room_id_by_session_id[p2_entry.session_id] = room_id

            if session_a is not None:
                session_a.current_room_id = room_id
            if session_b is not None:
                session_b.current_room_id = room_id

            worker.start()
            print(
                f"[ROUTER] room_started room_id={room_id} "
                f"players=({p1_entry.session_id},{p2_entry.session_id})"
            )
            last_assigned_room = room_id

        return last_assigned_room

    def _on_room_worker_finished(self, room_id: str, reason: str) -> None:
        with self._lock:
            room = self._state.rooms_by_id.get(room_id)
            if room is None:
                return
            if room.status == "finished":
                return
            now = monotonic()
            room.status = "finished"
            room.finished_at = now
            room.retain_until = now + ROOM_FINISH_GRACE_SECONDS
            room.finish_reason = reason

            for session_id in room.player_session_ids:
                if self._state.room_id_by_session_id.get(session_id) == room_id:
                    self._state.room_id_by_session_id.pop(session_id, None)
                self._clear_transport_bindings_for_session_locked(session_id)
                session = self._state.sessions_by_id.get(session_id)
                if session is not None and session.current_room_id == room_id:
                    session.current_room_id = None

            print(
                f"[ROUTER] room_finished room_id={room_id} reason={reason} "
                f"retain_until={room.retain_until}"
            )

    def _active_room_for_session_locked(self, session_id: str) -> RoomRecord | None:
        room_id = self._state.room_id_by_session_id.get(session_id)
        if room_id is None:
            return None

        room = self._state.rooms_by_id.get(room_id)
        if room is None:
            # Stale mapping: room was removed.
            self._state.room_id_by_session_id.pop(session_id, None)
            session = self._state.sessions_by_id.get(session_id)
            if session is not None and session.current_room_id == room_id:
                session.current_room_id = None
            return None

        if room.status != "running":
            # Finished rooms are retained for rejoin/debug, but queue/status
            # should not treat them as active matchmaking assignments.
            self._state.room_id_by_session_id.pop(session_id, None)
            session = self._state.sessions_by_id.get(session_id)
            if session is not None and session.current_room_id == room_id:
                session.current_room_id = None
            return None

        return room

    def _cleanup_expired_rooms_locked(self, now: float) -> None:
        expired_room_ids: list[str] = []
        for room_id, room in self._state.rooms_by_id.items():
            if room.status != "finished":
                continue
            if room.retain_until is None or now < room.retain_until:
                continue
            expired_room_ids.append(room_id)

        for room_id in expired_room_ids:
            room = self._state.rooms_by_id.pop(room_id, None)
            if room is None:
                continue
            for session_id in room.player_session_ids:
                if self._state.room_id_by_session_id.get(session_id) == room_id:
                    self._state.room_id_by_session_id.pop(session_id, None)
                self._clear_transport_bindings_for_session_locked(session_id)
                session = self._state.sessions_by_id.get(session_id)
                if session is not None and session.current_room_id == room_id:
                    session.current_room_id = None

    def _queue_position_locked(self, session_id: str) -> int | None:
        for idx, entry in enumerate(self._state.queue, start=1):
            if entry.session_id == session_id:
                return idx
        return None

    def _clear_transport_bindings_for_session_locked(self, session_id: str) -> None:
        stale_game_sids = [
            sid
            for sid, sid_session_id in self._state.game_session_id_by_socket_sid.items()
            if sid_session_id == session_id
        ]
        for stale_sid in stale_game_sids:
            self._state.game_session_id_by_socket_sid.pop(stale_sid, None)

        stale_client_ids = [
            client_id
            for client_id, client_session_id in self._state.game_session_id_by_client_id.items()
            if client_session_id == session_id
        ]
        for stale_client_id in stale_client_ids:
            self._state.game_session_id_by_client_id.pop(stale_client_id, None)

    def _ensure_session_locked(self, session_id: str) -> SessionIdentity | None:
        session = self._state.sessions_by_id.get(session_id)
        now = monotonic()
        if session is not None:
            active_session_id = self._state.active_session_id_by_user_id.get(session.user_id)
            if active_session_id is not None and active_session_id != session_id:
                self._state.sessions_by_id.pop(session_id, None)
                self._state.superseded_session_ids.add(session_id)
                self._storage.revoke_session(session_id)
                return None
            session.last_seen_at = now
            self._storage.touch_session(session_id, SESSION_COOKIE_MAX_AGE_SECONDS)
            return session

        stored = self._storage.get_session(session_id)
        if stored is None:
            return None

        hydrated = SessionIdentity(
            session_id=stored.session_id,
            user_id=stored.user_id,
            username=stored.username,
            created_at=now,
            last_seen_at=now,
            current_room_id=self._state.room_id_by_session_id.get(stored.session_id),
        )

        active_session_id = self._state.active_session_id_by_user_id.get(hydrated.user_id)
        if active_session_id is not None and active_session_id != hydrated.session_id:
            self._state.superseded_session_ids.add(hydrated.session_id)
            self._storage.revoke_session(hydrated.session_id)
            return None

        self._state.sessions_by_id[hydrated.session_id] = hydrated
        self._state.active_session_id_by_user_id[hydrated.user_id] = hydrated.session_id
        self._state.superseded_session_ids.discard(hydrated.session_id)
        self._storage.touch_session(session_id, SESSION_COOKIE_MAX_AGE_SECONDS)
        return hydrated

    def _transfer_room_assignment_locked(
        self,
        from_session_id: str,
        to_session_id: str,
    ) -> tuple[RoomRecord, str] | None:
        if from_session_id == to_session_id:
            return None

        room_id = self._state.room_id_by_session_id.get(from_session_id)
        if not isinstance(room_id, str) or not room_id:
            return None

        room = self._state.rooms_by_id.get(room_id)
        if room is None or room.status != 'running':
            return None

        p1_session_id, p2_session_id = room.player_session_ids
        slot: str | None = None
        if p1_session_id == from_session_id:
            room.player_session_ids = (to_session_id, p2_session_id)
            slot = 'p1'
        elif p2_session_id == from_session_id:
            room.player_session_ids = (p1_session_id, to_session_id)
            slot = 'p2'

        if slot is None:
            return None

        self._state.room_id_by_session_id.pop(from_session_id, None)
        self._state.room_id_by_session_id[to_session_id] = room_id

        old_session = self._state.sessions_by_id.get(from_session_id)
        if old_session is not None:
            old_session.current_room_id = None

        new_session = self._state.sessions_by_id.get(to_session_id)
        if new_session is not None:
            new_session.current_room_id = room_id

        return room, slot

    def _notify_room_session_takeover(
        self,
        room: RoomRecord,
        slot: str,
        old_session_id: str,
        new_session_id: str,
    ) -> None:
        payload = {
            'old_session_id': old_session_id,
            'new_session_id': new_session_id,
            'slot': slot,
        }

        if room.transport_mode == 'pipe':
            worker = room.worker
            if worker is None:
                print(
                    f'[ROUTER] room_session_takeover_notify_failed room_id={room.room_id} '
                    f'slot={slot} transport=pipe error=worker_unavailable'
                )
                return
            try:
                worker.request(
                    'replace_room_session',
                    {'payload': payload},
                    timeout_seconds=1.2,
                )
            except Exception as exc:
                print(
                    f'[ROUTER] room_session_takeover_notify_failed room_id={room.room_id} '
                    f'slot={slot} transport=pipe error={exc}'
                )
            return

        endpoint = f'http://{room.bind_host}:{room.port}/room/replace-session'
        data = json.dumps(payload).encode('utf-8')
        request_obj = urllib.request.Request(
            endpoint,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(request_obj, timeout=0.8) as response:
                _ = response.read()
        except urllib.error.URLError as exc:
            print(
                f'[ROUTER] room_session_takeover_notify_failed room_id={room.room_id} '
                f'slot={slot} error={exc}'
            )
        except Exception as exc:
            print(
                f'[ROUTER] room_session_takeover_notify_failed room_id={room.room_id} '
                f'slot={slot} error={exc}'
            )

    def _supersede_user_sessions_locked(
        self,
        user_id: str,
        keep_session_id: str | None = None,
        preserve_room_session_id: str | None = None,
    ) -> None:
        active_session_ids = set(self._storage.list_active_session_ids_for_user(user_id))
        active_session_ids.update(
            session.session_id
            for session in self._state.sessions_by_id.values()
            if session.user_id == user_id
        )

        superseded_socket_sids: list[tuple[str, list[str]]] = []

        for session_id in active_session_ids:
            if keep_session_id and session_id == keep_session_id:
                continue

            self._state.queue = [entry for entry in self._state.queue if entry.session_id != session_id]
            if not preserve_room_session_id or session_id != preserve_room_session_id:
                self._state.room_id_by_session_id.pop(session_id, None)

            existing = self._state.sessions_by_id.pop(session_id, None)
            if existing is not None:
                existing.current_room_id = None
            self._clear_transport_bindings_for_session_locked(session_id)

            sid_list = list(self._state.auth_socket_sids_by_session_id.pop(session_id, set()))
            if sid_list:
                superseded_socket_sids.append((session_id, sid_list))

            self._state.superseded_session_ids.add(session_id)
            self._storage.revoke_session(session_id)

        active_session_id = self._state.active_session_id_by_user_id.get(user_id)
        if active_session_id is None:
            return
        if keep_session_id is None or active_session_id != keep_session_id:
            self._state.active_session_id_by_user_id.pop(user_id, None)

        if self._superseded_notifier is not None:
            for session_id, sid_list in superseded_socket_sids:
                self._superseded_notifier(session_id, sid_list)

    def _serialize_room_locked(self, room: RoomRecord) -> JsonObject:
        worker_snapshot: RoomWorkerSnapshot | None = None
        if room.worker is not None:
            worker_snapshot = room.worker.snapshot()
        return {
            "room_id": room.room_id,
            "status": room.status,
            "bind_host": room.bind_host,
            "port": room.port,
            "transport_mode": room.transport_mode,
            "player_session_ids": list(room.player_session_ids),
            "created_at": room.created_at,
            "finished_at": room.finished_at,
            "retain_until": room.retain_until,
            "finish_reason": room.finish_reason,
            "worker": {
                "process_pid": worker_snapshot.process_pid,
                "started_at": worker_snapshot.started_at,
                "finished": worker_snapshot.finished,
                "finish_reason": worker_snapshot.finish_reason,
                "log_path": worker_snapshot.log_path,
            }
            if worker_snapshot is not None
            else None,
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cookie_session_id() -> str | None:
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _payload_session_id(payload: JsonObject) -> str | None:
    value = payload.get("session_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _query_session_id() -> str | None:
    value = request.args.get("session_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _payload_username(payload: JsonObject) -> str | None:
    value = payload.get("username")
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized[:32]


def _payload_protocol_client_id(payload: JsonObject) -> str | None:
    value = payload.get('client_id')
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _payload_protocol_register_session_id(payload: JsonObject) -> str | None:
    body = payload.get('Body')
    if not isinstance(body, dict):
        return None
    value = body.get('session_id')
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


app = Flask(__name__)
router = MatchmakingRouter()
socketio: Any = None
if SocketIO is not None:
    socketio_origins: str | list[str] = '*' if not ROUTER_ALLOWED_ORIGINS else ROUTER_ALLOWED_ORIGINS
    socketio = SocketIO(
        app,
        cors_allowed_origins=socketio_origins,
        async_mode=ROUTER_SOCKETIO_ASYNC_MODE,
    )


def _notify_superseded_session(session_id: str, socket_sids: list[str]) -> None:
    if socketio is None:
        return

    payload = {
        'reason': 'session_superseded',
        'session_id': session_id,
        'message': 'Signed out: account opened on another client.',
    }
    for sid in socket_sids:
        socketio.emit('force_logout', payload, to=sid)


router.set_superseded_notifier(_notify_superseded_session)


def _socket_sid() -> str:
    raw_sid = getattr(request, 'sid', None)
    return raw_sid if isinstance(raw_sid, str) else ''


def _session_response_payload(session: SessionIdentity) -> JsonObject:
    return {
        "ok": True,
        "session_id": session.session_id,
        "username": session.username,
        "current_room_id": session.current_room_id,
    }


def _resolve_authenticated_session(payload: JsonObject | None = None) -> tuple[SessionIdentity | None, tuple[JsonObject, int] | None]:
    payload_dict = payload if isinstance(payload, dict) else {}
    session_id = _payload_session_id(payload_dict) or _query_session_id() or _cookie_session_id()
    if session_id is None:
        return None, router.session_error_payload(session_id)

    session = router.session(session_id.strip())
    if session is None:
        return None, router.session_error_payload(session_id)

    return session, None


def _validate_deck_payload(payload: JsonObject) -> tuple[str, str, tuple[JsonObject, int] | None]:
    raw_name = payload.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        return "", "", ({"ok": False, "error": "name is required."}, 400)

    raw_cards = payload.get("cards")
    if not isinstance(raw_cards, list):
        return "", "", ({"ok": False, "error": "cards must be an array."}, 400)

    deck_error = _validate_deck_cards(raw_cards, require_exact_count=False)
    if deck_error is not None:
        return "", "", ({"ok": False, "error": deck_error}, 400)

    normalized_cards = [str(card_id).strip() for card_id in raw_cards]

    card_payload_json = json.dumps(normalized_cards, separators=(",", ":"))
    return raw_name.strip()[:64], card_payload_json, None


def _serialize_deck_response(deck_id: str, name: str, card_payload_json: str, updated_at: float) -> JsonObject:
    try:
        cards = json.loads(card_payload_json)
    except Exception:
        cards = []

    return {
        "deck_id": deck_id,
        "name": name,
        "cards": cards if isinstance(cards, list) else [],
        "updated_at": updated_at,
    }


@app.after_request
def add_cors_headers(response):
    request_origin = request.headers.get("Origin")
    allowed_origins = set(ROUTER_ALLOWED_ORIGINS)
    if allowed_origins and "*" not in allowed_origins:
        response.headers["Vary"] = "Origin"
        if isinstance(request_origin, str) and request_origin.strip() and request_origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = request_origin
    else:
        if isinstance(request_origin, str) and request_origin.strip():
            response.headers["Access-Control-Allow-Origin"] = request_origin
            response.headers["Vary"] = "Origin"
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"

    requested_headers = request.headers.get("Access-Control-Request-Headers")
    if isinstance(requested_headers, str) and requested_headers.strip():
        response.headers["Access-Control-Allow-Headers"] = requested_headers
    else:
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"

    requested_method = request.headers.get("Access-Control-Request-Method")
    if isinstance(requested_method, str) and requested_method.strip():
        response.headers["Access-Control-Allow-Methods"] = f"{requested_method}, OPTIONS"
    else:
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS, GET, PUT, DELETE"

    allow_origin = response.headers.get("Access-Control-Allow-Origin", "")
    if allow_origin != "*":
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@app.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok", "timestamp": _utc_now_iso()}, 200


@app.route("/session/bootstrap", methods=["POST", "OPTIONS"])
def session_bootstrap() -> Any:
    if request.method == "OPTIONS":
        return {"ok": True}, 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "Body must be a JSON object."}, 400

    username = _payload_username(payload)
    if username is None:
        return {"ok": False, "error": "username is required."}, 400

    session = router.bootstrap_session(
        username=username,
        existing_session_id=_payload_session_id(payload) or _cookie_session_id(),
    )

    response = make_response(jsonify(_session_response_payload(session)), 200)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session.session_id,
        max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=ROUTER_COOKIE_SECURE,
        samesite=ROUTER_COOKIE_SAMESITE,
    )
    return response


@app.route("/api/v1/auth/login", methods=["POST", "OPTIONS"])
def auth_login() -> Any:
    if request.method == "OPTIONS":
        return {"ok": True}, 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "Body must be a JSON object."}, 400

    username = _payload_username(payload)
    if username is None:
        return {"ok": False, "error": "username is required."}, 400

    session = router.login(
        username=username,
        existing_session_id=_payload_session_id(payload),
    )

    response = make_response(jsonify(_session_response_payload(session)), 200)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session.session_id,
        max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=ROUTER_COOKIE_SECURE,
        samesite=ROUTER_COOKIE_SAMESITE,
    )
    return response


@app.get("/api/v1/auth/session")
def auth_session() -> tuple[JsonObject, int]:
    session_id = request.args.get("session_id") or _cookie_session_id()
    if not isinstance(session_id, str) or not session_id.strip():
        return router.session_error_payload(None)

    session = router.session(session_id.strip())
    if session is None:
        return router.session_error_payload(session_id)

    return _session_response_payload(session), 200


@app.route("/api/v1/auth/logout", methods=["POST", "OPTIONS"])
def auth_logout() -> Any:
    if request.method == "OPTIONS":
        return {"ok": True}, 204

    payload = request.get_json(silent=True)
    if payload is not None and not isinstance(payload, dict):
        return {"ok": False, "error": "Body must be a JSON object."}, 400

    payload_dict: JsonObject = payload if isinstance(payload, dict) else {}
    session_id = _payload_session_id(payload_dict) or _cookie_session_id()
    if session_id is None:
        return router.session_error_payload(None)

    logged_out = router.logout(session_id)
    if not logged_out:
        return router.session_error_payload(session_id)

    response = make_response(jsonify({"ok": True}), 200)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.route("/api/v1/decks", methods=["GET", "POST", "OPTIONS"])
def decks_collection() -> Any:
    if request.method == "OPTIONS":
        return {"ok": True}, 204

    if request.method == "GET":
        session, error = _resolve_authenticated_session()
        if error is not None:
            return error
        assert session is not None

        decks = router._storage.list_decks_for_user(session.user_id)
        selected = router._storage.get_selected_deck(session.user_id)
        return {
            "ok": True,
            "decks": [
                _serialize_deck_response(deck.deck_id, deck.name, deck.card_payload_json, deck.updated_at)
                for deck in decks
            ],
            "selected_deck_id": selected["deck_id"] if selected else None,
        }, 200

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "Body must be a JSON object."}, 400

    session, error = _resolve_authenticated_session(payload)
    if error is not None:
        return error
    assert session is not None

    name, card_payload_json, validation_error = _validate_deck_payload(payload)
    if validation_error is not None:
        return validation_error

    deck = router._storage.create_deck(session.user_id, name, card_payload_json)
    return {
        "ok": True,
        "deck": _serialize_deck_response(deck.deck_id, deck.name, deck.card_payload_json, deck.updated_at),
    }, 201


@app.route("/api/v1/decks/<deck_id>", methods=["PUT", "DELETE", "OPTIONS"])
def deck_item(deck_id: str) -> Any:
    if request.method == "OPTIONS":
        return {"ok": True}, 204

    payload = request.get_json(silent=True)
    if payload is not None and not isinstance(payload, dict):
        return {"ok": False, "error": "Body must be a JSON object."}, 400
    payload_dict = payload if isinstance(payload, dict) else {}

    session, error = _resolve_authenticated_session(payload_dict)
    if error is not None:
        return error
    assert session is not None

    if request.method == "DELETE":
        deleted = router._storage.delete_deck(deck_id.strip(), session.user_id)
        if not deleted:
            return {"ok": False, "error": "Deck not found."}, 404
        return {"ok": True}, 200

    deck_id_normalized = deck_id.strip()
    owned_deck_ids = {deck.deck_id for deck in router._storage.list_decks_for_user(session.user_id)}
    if deck_id_normalized not in owned_deck_ids:
        return {"ok": False, "error": "Deck not found."}, 404

    name, card_payload_json, validation_error = _validate_deck_payload(payload_dict)
    if validation_error is not None:
        return validation_error

    updated = router._storage.update_deck(deck_id_normalized, session.user_id, name, card_payload_json)
    if not updated:
        return {"ok": False, "error": "Deck not found."}, 404

    # Re-read deck list and return updated item payload.
    decks = router._storage.list_decks_for_user(session.user_id)
    for deck in decks:
        if deck.deck_id == deck_id.strip():
            return {
                "ok": True,
                "deck": _serialize_deck_response(deck.deck_id, deck.name, deck.card_payload_json, deck.updated_at),
            }, 200

    return {"ok": False, "error": "Deck not found after update."}, 500


@app.route("/api/v1/decks/<deck_id>/select", methods=["POST", "OPTIONS"])
def deck_select(deck_id: str) -> Any:
    if request.method == "OPTIONS":
        return {"ok": True}, 204

    payload = request.get_json(silent=True)
    if payload is not None and not isinstance(payload, dict):
        return {"ok": False, "error": "Body must be a JSON object."}, 400
    payload_dict = payload if isinstance(payload, dict) else {}

    session, error = _resolve_authenticated_session(payload_dict)
    if error is not None:
        return error
    assert session is not None

    selected_ok = router._storage.set_selected_deck(session.user_id, deck_id.strip())
    if not selected_ok:
        return {"ok": False, "error": "Deck not found."}, 404

    selected = router._storage.get_selected_deck(session.user_id)
    return {
        "ok": True,
        "selected_deck_id": selected["deck_id"] if selected else None,
    }, 200


@app.route("/matchmaking/queue", methods=["POST", "OPTIONS"])
def matchmaking_queue() -> tuple[JsonObject, int]:
    if request.method == "OPTIONS":
        return {"ok": True}, 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "Body must be a JSON object."}, 400

    session_id = _payload_session_id(payload) or _cookie_session_id()
    if session_id is None:
        return router.session_error_payload(None)

    action = payload.get("action")
    if not isinstance(action, str):
        action = "join"

    if action == "leave":
        result = router.dequeue(session_id)
    else:
        result = router.enqueue(session_id)

    if not result.get("ok"):
        error_code = result.get("error_code") if isinstance(result.get("error_code"), str) else ""
        status = 401 if error_code in {"session_superseded", "unknown_session"} else 400
        return result, status
    return result, 200


@app.get("/matchmaking/status")
def matchmaking_status() -> tuple[JsonObject, int]:
    session_id = request.args.get("session_id") or _cookie_session_id()
    if not isinstance(session_id, str) or not session_id.strip():
        return router.session_error_payload(None)

    result = router.status(session_id.strip())
    if not result.get("ok"):
        error_code = result.get("error_code") if isinstance(result.get("error_code"), str) else ""
        status = 401 if error_code in {"session_superseded", "unknown_session"} else 404
        return result, status
    return result, 200


@app.route('/protocol', methods=['POST', 'OPTIONS'])
def protocol_proxy() -> tuple[JsonObject, int]:
    if request.method == 'OPTIONS':
        return {'ok': True}, 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {'ok': False, 'error': 'Body must be a JSON object.'}, 400

    packet_type_raw = payload.get('PacketType')
    packet_type = packet_type_raw.strip() if isinstance(packet_type_raw, str) else ''
    if not packet_type:
        return {'ok': False, 'error': 'PacketType is required.'}, 400

    client_id = _payload_protocol_client_id(payload)
    if not client_id:
        return {'ok': False, 'error': 'client_id is required.'}, 400

    session_id: str | None
    if packet_type == 'register_client':
        session_id = _payload_protocol_register_session_id(payload)
        if not session_id:
            return {'ok': False, 'error': 'register_client requires Body.session_id.'}, 400

        bind_ok, bind_body = router.register_game_client(client_id, session_id)
        if not bind_ok:
            error_code = bind_body.get('error_code') if isinstance(bind_body.get('error_code'), str) else ''
            status = 401 if error_code in {'session_superseded', 'unknown_session'} else 404
            return bind_body, status
    else:
        session_id = router.game_session_for_client(client_id)
        if not session_id:
            return {
                'ok': False,
                'error': 'Unknown protocol client_id; register_client is required first.',
                'error_code': 'unknown_protocol_client',
            }, 401

    assert isinstance(session_id, str) and session_id

    forwarded_ok, forwarded_body = router.dispatch_pipe_command_for_session(
        session_id,
        method='protocol_http_packet',
        params={'payload': payload},
        timeout_seconds=3.5,
    )
    if not forwarded_ok:
        if packet_type == 'register_client':
            router.unregister_game_client(client_id)

        error_code = forwarded_body.get('error_code') if isinstance(forwarded_body.get('error_code'), str) else ''
        if error_code in {'session_superseded', 'unknown_session'}:
            status = 401
        elif error_code == 'no_active_room':
            status = 404
        else:
            status = 502
        return forwarded_body, status

    response_body_raw = forwarded_body.get('body')
    response_body: JsonObject | None = (
        cast(JsonObject, response_body_raw)
        if isinstance(response_body_raw, dict)
        else None
    )

    response_status_raw = forwarded_body.get('status')
    response_status = response_status_raw if isinstance(response_status_raw, int) else 200
    if packet_type == 'register_client' and response_status != 200:
        router.unregister_game_client(client_id)

    if response_body is None:
        return {'ok': False, 'error': 'Invalid room protocol proxy response.'}, 502
    return response_body, response_status


@app.route("/rooms/rejoin", methods=["POST", "OPTIONS"])
def room_rejoin() -> tuple[JsonObject, int]:
    if request.method == "OPTIONS":
        return {"ok": True}, 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "Body must be a JSON object."}, 400

    session_id = _payload_session_id(payload) or _cookie_session_id()
    if session_id is None:
        return router.session_error_payload(None)

    room_id = payload.get("room_id") if isinstance(payload.get("room_id"), str) else None
    result = router.rejoin_room(session_id, room_id=room_id)
    if not result.get("ok"):
        error_code = result.get("error_code") if isinstance(result.get("error_code"), str) else ""
        status = 401 if error_code in {"session_superseded", "unknown_session"} else 404
        return result, status
    return result, 200


@app.route("/rooms/finish", methods=["POST", "OPTIONS"])
def room_finish() -> tuple[JsonObject, int]:
    if request.method == "OPTIONS":
        return {"ok": True}, 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "Body must be a JSON object."}, 400

    room_id = payload.get("room_id")
    reason = payload.get("reason")
    if not isinstance(room_id, str) or not room_id.strip():
        return {"ok": False, "error": "room_id is required."}, 400
    if not isinstance(reason, str) or not reason.strip():
        reason = "finished"

    result = router.mark_room_finished(room_id.strip(), reason.strip())
    if not result.get("ok"):
        return result, 404
    return result, 200


if socketio is not None:
    @socketio.on('connect')
    def socket_connect() -> None:
        if emit is None:
            return
        emit('server_status', {
            'ok': True,
            'transport': 'socketio',
            'message': 'connected',
        })


    @socketio.on('auth_register_session')
    def socket_auth_register_session(payload: Any) -> None:
        if emit is None:
            return

        data = payload if isinstance(payload, dict) else {}
        raw_session_id = data.get('session_id')
        session_id = raw_session_id.strip() if isinstance(raw_session_id, str) else ''
        if not session_id:
            emit('auth_registration_error', {
                'ok': False,
                'error': 'session_id is required.',
                'error_code': 'session_id_required',
            })
            return

        socket_sid = getattr(request, 'sid', None)
        sid = socket_sid if isinstance(socket_sid, str) else ''
        if not sid:
            emit('auth_registration_error', {
                'ok': False,
                'error': 'socket sid unavailable',
                'error_code': 'socket_sid_unavailable',
            })
            return

        ok, body = router.register_auth_socket(session_id, sid)
        if not ok:
            emit('auth_registration_error', body)
            if body.get('error_code') == 'session_superseded':
                emit('force_logout', {
                    'reason': 'session_superseded',
                    'session_id': session_id,
                    'message': 'Signed out: account opened on another client.',
                })
            return

        emit('auth_registration_ok', body)


    @socketio.on('register_client_or_play')
    def socket_register_client_or_play(payload: Any) -> None:
        if emit is None:
            return

        data = payload if isinstance(payload, dict) else {}
        raw_session_id = data.get('session_id')
        session_id = raw_session_id.strip() if isinstance(raw_session_id, str) else ''
        if not session_id:
            emit('registration_error', {
                'ok': False,
                'error': 'session_id is required.',
            })
            return

        sid = _socket_sid()
        if not sid:
            emit('registration_error', {
                'ok': False,
                'error': 'socket sid unavailable',
            })
            return

        ok, register_body = router.register_game_socket(session_id, sid)
        if not ok:
            emit('registration_error', register_body)
            return

        forwarded_ok, forwarded_body = router.dispatch_pipe_command_for_session(
            session_id,
            method='register_client_or_play',
            params={
                'sid': sid,
                'payload': data,
            },
            timeout_seconds=2.5,
        )
        if not forwarded_ok:
            router.unregister_game_socket(sid)
            emit('registration_error', forwarded_body)


    def _forward_pipe_protocol_socket_event(packet_type: str, payload: Any) -> None:
        if emit is None:
            return

        sid = _socket_sid()
        if not sid:
            emit('protocol_error', {
                'ok': False,
                'error': 'socket sid unavailable',
                'packet_type': packet_type,
                'status': 400,
            })
            return

        session_id = router.game_session_for_socket(sid)
        if not session_id:
            emit('protocol_error', {
                'ok': False,
                'error': 'Socket is not registered for gameplay.',
                'packet_type': packet_type,
                'status': 401,
            })
            return

        forwarded_ok, forwarded_body = router.dispatch_pipe_command_for_session(
            session_id,
            method='protocol_socket_event',
            params={
                'sid': sid,
                'packet_type': packet_type,
                'payload': payload if isinstance(payload, dict) else {},
            },
            timeout_seconds=2.5,
        )

        if not forwarded_ok:
            emit('protocol_error', {
                **forwarded_body,
                'packet_type': packet_type,
                'status': 502,
            })


    @socketio.on('ready')
    def socket_ready(payload: Any) -> None:
        _forward_pipe_protocol_socket_event('ready', payload)


    @socketio.on('request_environment')
    def socket_request_environment(payload: Any) -> None:
        _forward_pipe_protocol_socket_event('request_environment', payload)


    @socketio.on('update_frontend')
    def socket_update_frontend(payload: Any) -> None:
        _forward_pipe_protocol_socket_event('update_frontend', payload)


    @socketio.on('init_setup_done')
    def socket_init_setup_done(payload: Any) -> None:
        _forward_pipe_protocol_socket_event('init_setup_done', payload)


    @socketio.on('frontend_event')
    def socket_frontend_event(payload: Any) -> None:
        _forward_pipe_protocol_socket_event('frontend_event', payload)


    @socketio.on('client_unloading')
    def socket_client_unloading(_payload: Any) -> None:
        sid = _socket_sid()
        if not sid:
            return

        session_id = router.game_session_for_socket(sid)
        if not isinstance(session_id, str) or not session_id:
            return

        router.unregister_game_socket(sid)
        router.dispatch_pipe_command_for_session(
            session_id,
            method='client_unloading',
            params={'sid': sid},
            timeout_seconds=1.2,
        )


    @socketio.on('disconnect')
    def socket_disconnect() -> None:
        sid = _socket_sid()
        if not sid:
            return

        game_session_id = router.unregister_game_socket(sid)
        if isinstance(game_session_id, str) and game_session_id:
            router.dispatch_pipe_command_for_session(
                game_session_id,
                method='disconnect',
                params={'sid': sid},
                timeout_seconds=1.2,
            )

        router.unregister_auth_socket(sid)


if __name__ == "__main__":
    if socketio is not None:
        socketio.run(
            app,
            host=ROUTER_HOST,
            port=ROUTER_PORT,
            debug=ROUTER_DEBUG,
            use_reloader=ROUTER_USE_RELOADER,
        )
    else:
        app.run(
            host=ROUTER_HOST,
            port=ROUTER_PORT,
            debug=ROUTER_DEBUG,
            use_reloader=ROUTER_USE_RELOADER,
        )
