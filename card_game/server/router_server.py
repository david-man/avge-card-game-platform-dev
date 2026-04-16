from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from typing import Any
from uuid import uuid4
import json
import os
import random
import socket

from flask import Flask, jsonify, make_response, request

try:
    from .room_worker import RoomWorker
except ImportError:  # pragma: no cover - direct script execution fallback
    from room_worker import RoomWorker  # type: ignore

try:
    from .router_storage import RouterStorage
except ImportError:  # pragma: no cover - direct script execution fallback
    from router_storage import RouterStorage  # type: ignore

SESSION_COOKIE_NAME = "avge_session"
SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30
ROOM_FINISH_GRACE_SECONDS = 90
ROOM_HOST = os.getenv("ROOM_HOST", "127.0.0.1")
ROOM_BASE_PORT = int(os.getenv("ROOM_BASE_PORT", "5700"))
ROUTER_DB_PATH = os.getenv(
    "ROUTER_DB_PATH",
    os.path.join(os.path.dirname(__file__), "router.sqlite3"),
)


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
    host: str
    port: int
    status: str = "running"
    finished_at: float | None = None
    retain_until: float | None = None
    finish_reason: str | None = None
    worker: RoomWorker | None = None


@dataclass
class RouterState:
    sessions_by_id: dict[str, SessionIdentity] = field(default_factory=dict)
    rooms_by_id: dict[str, RoomRecord] = field(default_factory=dict)
    room_id_by_session_id: dict[str, str] = field(default_factory=dict)
    queue: list[QueueEntry] = field(default_factory=list)


class MatchmakingRouter:
    def __init__(self, db_path: str | None = None) -> None:
        self._state = RouterState()
        self._lock = RLock()
        self._next_room_port = ROOM_BASE_PORT
        self._storage = RouterStorage(db_path or ROUTER_DB_PATH)

    def login(self, username: str, existing_session_id: str | None) -> SessionIdentity:
        now = monotonic()
        user_id = self._storage.get_or_create_user(username)

        with self._lock:
            self._cleanup_expired_rooms_locked(now)

            if existing_session_id:
                existing = self._state.sessions_by_id.get(existing_session_id)
                if existing is not None and existing.user_id == user_id:
                    existing.last_seen_at = now
                    self._storage.create_or_update_session(
                        session_id=existing.session_id,
                        user_id=user_id,
                        ttl_seconds=SESSION_COOKIE_MAX_AGE_SECONDS,
                    )
                    return existing

                stored_session = self._storage.get_session(existing_session_id)
                if stored_session is not None and stored_session.user_id == user_id:
                    self._storage.create_or_update_session(
                        session_id=stored_session.session_id,
                        user_id=user_id,
                        ttl_seconds=SESSION_COOKIE_MAX_AGE_SECONDS,
                    )
                    hydrated = SessionIdentity(
                        session_id=stored_session.session_id,
                        user_id=stored_session.user_id,
                        username=stored_session.username,
                        created_at=now,
                        last_seen_at=now,
                        current_room_id=self._state.room_id_by_session_id.get(stored_session.session_id),
                    )
                    self._state.sessions_by_id[hydrated.session_id] = hydrated
                    return hydrated

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
            self._storage.revoke_session(session_id)
            return True

    def bootstrap_session(self, username: str, existing_session_id: str | None) -> SessionIdentity:
        now = monotonic()
        user_id = self._storage.get_or_create_user(username)
        with self._lock:
            self._cleanup_expired_rooms_locked(now)

            if existing_session_id:
                existing = self._state.sessions_by_id.get(existing_session_id)
                if existing is not None:
                    existing.username = username
                    existing.last_seen_at = now
                    self._storage.create_or_update_session(
                        session_id=existing.session_id,
                        user_id=user_id,
                        ttl_seconds=SESSION_COOKIE_MAX_AGE_SECONDS,
                    )
                    return existing

                stored_session = self._storage.get_session(existing_session_id)
                if stored_session is not None:
                    self._storage.create_or_update_session(
                        session_id=stored_session.session_id,
                        user_id=user_id,
                        ttl_seconds=SESSION_COOKIE_MAX_AGE_SECONDS,
                    )
                    session = SessionIdentity(
                        session_id=stored_session.session_id,
                        user_id=stored_session.user_id,
                        username=username,
                        created_at=now,
                        last_seen_at=now,
                    )
                    self._state.sessions_by_id[session.session_id] = session
                    return session

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
            return session

    def enqueue(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            now = monotonic()
            self._cleanup_expired_rooms_locked(now)

            session = self._ensure_session_locked(session_id)
            if session is None:
                return {"ok": False, "error": "Unknown session."}

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

    def dequeue(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            before = len(self._state.queue)
            self._state.queue = [entry for entry in self._state.queue if entry.session_id != session_id]
            removed = len(self._state.queue) != before
            return {
                "ok": True,
                "removed": removed,
            }

    def status(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            now = monotonic()
            self._cleanup_expired_rooms_locked(now)

            session = self._ensure_session_locked(session_id)
            if session is None:
                return {"ok": False, "error": "Unknown session."}

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

    def rejoin_room(self, session_id: str, room_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            now = monotonic()
            self._cleanup_expired_rooms_locked(now)

            session = self._ensure_session_locked(session_id)
            if session is None:
                return {"ok": False, "error": "Unknown session."}

            resolved_room_id = room_id or self._state.room_id_by_session_id.get(session_id)
            if resolved_room_id is None:
                return {"ok": False, "error": "No active room for session."}

            room = self._state.rooms_by_id.get(resolved_room_id)
            if room is None:
                return {"ok": False, "error": "Room not found."}

            if session_id not in room.player_session_ids:
                return {"ok": False, "error": "Session does not belong to this room."}

            session.current_room_id = room.room_id
            return {
                "ok": True,
                "room": self._serialize_room_locked(room),
            }

    def mark_room_finished(self, room_id: str, reason: str) -> dict[str, Any]:
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
                if room.worker is not None:
                    room.worker.stop(reason=reason)

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
            room_port = self._reserve_next_room_port_locked()
            room = RoomRecord(
                room_id=room_id,
                player_session_ids=(p1_entry.session_id, p2_entry.session_id),
                created_at=now,
                host=ROOM_HOST,
                port=room_port,
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
                    parsed = json.loads(selected.get('card_payload_json', '[]'))
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
                host=room.host,
                port=room.port,
                p1_username=session_a_name,
                p2_username=session_b_name,
                p1_selected_cards=session_a_selected_cards,
                p2_selected_cards=session_b_selected_cards,
                on_finished=self._on_room_worker_finished,
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
                f"[ROUTER] room_started room_id={room_id} endpoint=http://{room.host}:{room.port} "
                f"players=({p1_entry.session_id},{p2_entry.session_id})"
            )
            last_assigned_room = room_id

        return last_assigned_room

    def _reserve_next_room_port_locked(self) -> int:
        candidate = self._next_room_port
        for _ in range(1024):
            if self._is_port_available(candidate):
                self._next_room_port = candidate + 1
                return candidate
            candidate += 1
        raise RuntimeError('Unable to allocate an available room port.')

    def _is_port_available(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((ROOM_HOST, port))
            except OSError:
                return False
        return True

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
                session = self._state.sessions_by_id.get(session_id)
                if session is not None and session.current_room_id == room_id:
                    session.current_room_id = None

    def _queue_position_locked(self, session_id: str) -> int | None:
        for idx, entry in enumerate(self._state.queue, start=1):
            if entry.session_id == session_id:
                return idx
        return None

    def _ensure_session_locked(self, session_id: str) -> SessionIdentity | None:
        session = self._state.sessions_by_id.get(session_id)
        now = monotonic()
        if session is not None:
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
        self._state.sessions_by_id[hydrated.session_id] = hydrated
        self._storage.touch_session(session_id, SESSION_COOKIE_MAX_AGE_SECONDS)
        return hydrated

    def _serialize_room_locked(self, room: RoomRecord) -> dict[str, Any]:
        worker_snapshot = room.worker.snapshot() if room.worker is not None else None
        return {
            "room_id": room.room_id,
            "status": room.status,
            "host": room.host,
            "port": room.port,
            "endpoint_url": f"http://{room.host}:{room.port}",
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


def _payload_session_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("session_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _query_session_id() -> str | None:
    value = request.args.get("session_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _payload_username(payload: dict[str, Any]) -> str | None:
    value = payload.get("username")
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized[:32]


app = Flask(__name__)
router = MatchmakingRouter()


def _session_response_payload(session: SessionIdentity) -> dict[str, Any]:
    return {
        "ok": True,
        "session_id": session.session_id,
        "username": session.username,
        "current_room_id": session.current_room_id,
    }


def _resolve_authenticated_session(payload: dict[str, Any] | None = None) -> tuple[SessionIdentity | None, tuple[dict[str, Any], int] | None]:
    payload_dict = payload if isinstance(payload, dict) else {}
    session_id = _payload_session_id(payload_dict) or _query_session_id() or _cookie_session_id()
    if session_id is None:
        return None, ({"ok": False, "error": "session_id is required."}, 400)

    session = router.session(session_id.strip())
    if session is None:
        return None, ({"ok": False, "error": "Unknown session."}, 401)

    return session, None


def _validate_deck_payload(payload: dict[str, Any]) -> tuple[str, str, tuple[dict[str, Any], int] | None]:
    raw_name = payload.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        return "", "", ({"ok": False, "error": "name is required."}, 400)

    raw_cards = payload.get("cards")
    if not isinstance(raw_cards, list):
        return "", "", ({"ok": False, "error": "cards must be an array."}, 400)

    card_payload_json = json.dumps(raw_cards, separators=(",", ":"))
    return raw_name.strip()[:64], card_payload_json, None


def _serialize_deck_response(deck_id: str, name: str, card_payload_json: str, updated_at: float) -> dict[str, Any]:
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
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS, GET, PUT, DELETE"
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
        samesite="Lax",
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
        existing_session_id=_payload_session_id(payload) or _cookie_session_id(),
    )

    response = make_response(jsonify(_session_response_payload(session)), 200)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session.session_id,
        max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="Lax",
    )
    return response


@app.get("/api/v1/auth/session")
def auth_session() -> tuple[dict[str, Any], int]:
    session_id = request.args.get("session_id") or _cookie_session_id()
    if not isinstance(session_id, str) or not session_id.strip():
        return {"ok": False, "error": "session_id is required."}, 400

    session = router.session(session_id.strip())
    if session is None:
        return {"ok": False, "error": "Unknown session."}, 401

    return _session_response_payload(session), 200


@app.route("/api/v1/auth/logout", methods=["POST", "OPTIONS"])
def auth_logout() -> Any:
    if request.method == "OPTIONS":
        return {"ok": True}, 204

    payload = request.get_json(silent=True)
    if payload is not None and not isinstance(payload, dict):
        return {"ok": False, "error": "Body must be a JSON object."}, 400

    payload_dict: dict[str, Any] = payload if isinstance(payload, dict) else {}
    session_id = _payload_session_id(payload_dict) or _cookie_session_id()
    if session_id is None:
        return {"ok": False, "error": "session_id is required."}, 400

    logged_out = router.logout(session_id)
    if not logged_out:
        return {"ok": False, "error": "Unknown session."}, 401

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

    name, card_payload_json, validation_error = _validate_deck_payload(payload_dict)
    if validation_error is not None:
        return validation_error

    updated = router._storage.update_deck(deck_id.strip(), session.user_id, name, card_payload_json)
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
def matchmaking_queue() -> tuple[dict[str, Any], int]:
    if request.method == "OPTIONS":
        return {"ok": True}, 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "Body must be a JSON object."}, 400

    session_id = _payload_session_id(payload) or _cookie_session_id()
    if session_id is None:
        return {"ok": False, "error": "session_id is required."}, 400

    action = payload.get("action")
    if not isinstance(action, str):
        action = "join"

    if action == "leave":
        result = router.dequeue(session_id)
    else:
        result = router.enqueue(session_id)

    if not result.get("ok"):
        return result, 400
    return result, 200


@app.get("/matchmaking/status")
def matchmaking_status() -> tuple[dict[str, Any], int]:
    session_id = request.args.get("session_id") or _cookie_session_id()
    if not isinstance(session_id, str) or not session_id.strip():
        return {"ok": False, "error": "session_id is required."}, 400

    result = router.status(session_id.strip())
    if not result.get("ok"):
        return result, 404
    return result, 200


@app.route("/rooms/rejoin", methods=["POST", "OPTIONS"])
def room_rejoin() -> tuple[dict[str, Any], int]:
    if request.method == "OPTIONS":
        return {"ok": True}, 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "Body must be a JSON object."}, 400

    session_id = _payload_session_id(payload) or _cookie_session_id()
    if session_id is None:
        return {"ok": False, "error": "session_id is required."}, 400

    room_id = payload.get("room_id") if isinstance(payload.get("room_id"), str) else None
    result = router.rejoin_room(session_id, room_id=room_id)
    if not result.get("ok"):
        return result, 404
    return result, 200


@app.route("/rooms/finish", methods=["POST", "OPTIONS"])
def room_finish() -> tuple[dict[str, Any], int]:
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


if __name__ == "__main__":
    router_host = os.getenv("ROUTER_HOST", "0.0.0.0")
    router_port = int(os.getenv("ROUTER_PORT", "5600"))
    router_debug = os.getenv("ROUTER_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}
    router_use_reloader = os.getenv("ROUTER_USE_RELOADER", "false").strip().lower() in {"1", "true", "yes", "on"}
    app.run(
        host=router_host,
        port=router_port,
        debug=router_debug,
        use_reloader=router_use_reloader,
    )
