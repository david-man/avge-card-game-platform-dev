from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime, timezone
from threading import Condition
from threading import RLock
from time import monotonic
from typing import Any
from typing import Literal
from typing import cast
from uuid import uuid4

from flask import Flask, request

try:
    from flask_socketio import SocketIO, emit
except ImportError:  # pragma: no cover - optional runtime dependency
    SocketIO = None  # type: ignore[assignment]
    emit = None  # type: ignore[assignment]

from .game_runner import FrontendGameBridge
from .logging import (
    log_protocol_ack_mismatch,
    log_protocol_event,
    log_protocol_recv,
    log_protocol_send,
    log_protocol_update,
)

app = Flask(__name__)
frontend_game_bridge = FrontendGameBridge()
entity_setup_payload: dict[str, Any] = frontend_game_bridge.get_setup_payload()
protocol_seq = 0
DISCONNECT_GRACE_SECONDS = 30.0


@dataclass
class PendingCommandAck:
    command_id: int
    command: str
    required_slots: set[PlayerSlot]
    acked_slots: set[PlayerSlot] = field(default_factory=set)
    delivered_slots: set[PlayerSlot] = field(default_factory=set)


pending_command_acks: list[PendingCommandAck] = []
next_command_id = 1

PlayerSlot = Literal['p1', 'p2']


@dataclass
class ClientSession:
    sid: str
    slot: PlayerSlot
    reconnect_token: str
    connected: bool = True
    last_ack: int = 0
    next_seq: int = 0
    pending_commands: list[str] = field(default_factory=list)
    pending_packets: list[dict[str, Any]] = field(default_factory=list)
    environment_initialized: bool = False
    disconnected_at: float | None = None


@dataclass
class MultiplayerTransportState:
    sid_by_slot: dict[PlayerSlot, str | None] = field(default_factory=lambda: {'p1': None, 'p2': None})
    session_by_sid: dict[str, ClientSession] = field(default_factory=dict)
    reconnect_token_to_slot: dict[str, PlayerSlot] = field(default_factory=dict)
    reserved_session_by_slot: dict[PlayerSlot, ClientSession | None] = field(default_factory=lambda: {'p1': None, 'p2': None})
    grace_deadline_by_slot: dict[PlayerSlot, float | None] = field(default_factory=lambda: {'p1': None, 'p2': None})

    def both_players_connected(self) -> bool:
        return all(self.sid_by_slot[slot] is not None for slot in ('p1', 'p2'))

    def slot_for_sid(self, sid: str) -> PlayerSlot | None:
        self._expire_grace_slots()
        session = self.session_by_sid.get(sid)
        if session is None:
            return None
        return session.slot

    def assign_slot(self, sid: str, requested_slot: str | None = None, reconnect_token: str | None = None) -> ClientSession | None:
        self._expire_grace_slots()

        # Idempotent registration: if this sid is already assigned, reuse it.
        existing_session = self.session_by_sid.get(sid)
        if existing_session is not None:
            return existing_session

        reconnect_slot = self.reconnect_token_to_slot.get(reconnect_token or '')
        if reconnect_slot is not None:
            current_sid_for_slot = self.sid_by_slot[reconnect_slot]
            if current_sid_for_slot == sid:
                return self.session_by_sid.get(sid)
            if self.sid_by_slot[reconnect_slot] is None:
                reusable = self.reserved_session_by_slot[reconnect_slot]
                return self._bind_sid_to_slot(
                    sid,
                    reconnect_slot,
                    reconnect_token or '',
                    reusable_session=reusable,
                )
            return None

        normalized_requested: PlayerSlot | None = None
        if requested_slot in {'p1', 'p2'}:
            normalized_requested = cast(PlayerSlot, requested_slot)

        if (
            normalized_requested is not None
            and self.sid_by_slot[normalized_requested] is None
            and self.reserved_session_by_slot[normalized_requested] is None
        ):
            token = uuid4().hex
            return self._bind_sid_to_slot(sid, normalized_requested, token)

        for candidate in ('p1', 'p2'):
            if self.sid_by_slot[candidate] is None and self.reserved_session_by_slot[candidate] is None:
                token = uuid4().hex
                return self._bind_sid_to_slot(sid, candidate, token)

        return None

    def release_sid(self, sid: str) -> PlayerSlot | None:
        self._expire_grace_slots()
        session = self.session_by_sid.pop(sid, None)
        if session is None:
            return None
        slot = session.slot
        self.sid_by_slot[slot] = None
        session.connected = False
        session.disconnected_at = monotonic()
        session.environment_initialized = False
        self.reserved_session_by_slot[slot] = session
        self.grace_deadline_by_slot[slot] = session.disconnected_at + DISCONNECT_GRACE_SECONDS
        return slot

    def grace_remaining_seconds(self, slot: PlayerSlot) -> int:
        self._expire_grace_slots()
        deadline = self.grace_deadline_by_slot.get(slot)
        if deadline is None:
            return 0
        return max(0, int(deadline - monotonic()))

    def set_reserved_pending_commands(self, slot: PlayerSlot, commands: list[str]) -> None:
        session = self.reserved_session_by_slot.get(slot)
        if session is None:
            return
        session.pending_commands = list(commands)

    def _bind_sid_to_slot(
        self,
        sid: str,
        slot: PlayerSlot,
        token: str,
        reusable_session: ClientSession | None = None,
    ) -> ClientSession:
        self._expire_grace_slots()
        previous_sid = self.sid_by_slot[slot]
        if previous_sid is not None and previous_sid != sid:
            self.session_by_sid.pop(previous_sid, None)

        self.sid_by_slot[slot] = sid
        self.reconnect_token_to_slot[token] = slot
        self.reserved_session_by_slot[slot] = None
        self.grace_deadline_by_slot[slot] = None

        if reusable_session is not None:
            session = reusable_session
            session.sid = sid
            session.connected = True
            session.disconnected_at = None
        else:
            session = ClientSession(
                sid=sid,
                slot=slot,
                reconnect_token=token,
            )

        self.session_by_sid[sid] = session
        return session

    def _expire_grace_slots(self) -> None:
        now = monotonic()
        for slot in ('p1', 'p2'):
            deadline = self.grace_deadline_by_slot.get(slot)
            if deadline is None or now < deadline:
                continue
            if self.sid_by_slot[slot] is not None:
                continue

            reserved = self.reserved_session_by_slot.get(slot)
            if reserved is not None:
                self.reconnect_token_to_slot.pop(reserved.reconnect_token, None)
            self.reserved_session_by_slot[slot] = None
            self.grace_deadline_by_slot[slot] = None


transport_state = MultiplayerTransportState()
transport_lock = RLock()
registration_condition = Condition(transport_lock)

socketio: Any = None
if SocketIO is not None:
    socketio = SocketIO(app, cors_allowed_origins='*')


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_client_slot(raw_slot: Any) -> str | None:
    return raw_slot if isinstance(raw_slot, str) and raw_slot in {'p1', 'p2'} else None


def _extract_client_slot_hint(body: dict[str, Any]) -> str | None:
    if not isinstance(body, dict):
        return None

    direct_slot = _normalize_client_slot(body.get('client_slot'))
    if direct_slot is not None:
        return direct_slot

    context = body.get('context')
    if isinstance(context, dict):
        context_slot = _normalize_client_slot(context.get('client_slot'))
        if context_slot is not None:
            return context_slot

    response_data = body.get('response_data')
    if isinstance(response_data, dict):
        response_slot = _normalize_client_slot(response_data.get('client_slot'))
        if response_slot is not None:
            return response_slot

    return None


def _socket_sid() -> str:
    raw_sid = getattr(request, 'sid', None)
    return raw_sid if isinstance(raw_sid, str) else ''


def _issue_backend_packet(packet_type: str, body: dict[str, Any], is_response: bool) -> dict[str, Any]:
    global protocol_seq
    packet = {
        'SEQ': protocol_seq,
        'IsResponse': bool(is_response),
        'PacketType': packet_type,
        'Body': body,
    }
    protocol_seq += 1
    return packet


def _issue_backend_packet_for_session(
    session: ClientSession,
    packet_type: str,
    body: dict[str, Any],
    is_response: bool,
) -> dict[str, Any]:
    packet = {
        'SEQ': session.next_seq,
        'IsResponse': bool(is_response),
        'PacketType': packet_type,
        'Body': body,
    }
    session.next_seq += 1
    return packet


def _build_packet_blueprint(packet_type: str, body: dict[str, Any], is_response: bool) -> dict[str, Any]:
    return {
        'IsResponse': bool(is_response),
        'PacketType': packet_type,
        'Body': body,
    }


def _drain_pending_packets_for_session(session: ClientSession) -> list[dict[str, Any]]:
    drained: list[dict[str, Any]] = []
    for pending in session.pending_packets:
        packet_type = pending.get('PacketType')
        body = pending.get('Body')
        is_response = pending.get('IsResponse', True)
        if isinstance(packet_type, str) and isinstance(body, dict):
            if packet_type == 'environment':
                session.environment_initialized = True
            drained.append(
                _issue_backend_packet_for_session(
                    session,
                    packet_type,
                    body,
                    bool(is_response),
                )
            )
    session.pending_packets = []
    return drained


def _current_environment_body() -> dict[str, Any]:
    return deepcopy(entity_setup_payload) if isinstance(entity_setup_payload, dict) else {}


def _environment_body_for_client(client_slot: str | None) -> dict[str, Any]:
    body = _current_environment_body()
    normalized = _normalize_client_slot(client_slot)
    body['playerView'] = normalized if normalized in {'p1', 'p2'} else 'admin'
    return body


def _enqueue_environment_for_connected_clients(force: bool = False) -> None:
    slots_needing_environment: list[PlayerSlot] = []
    for slot_name in ('p1', 'p2'):
        sid_for_slot = transport_state.sid_by_slot[slot_name]
        if sid_for_slot is None:
            continue
        session = transport_state.session_by_sid.get(sid_for_slot)
        if session is None:
            continue
        if session.environment_initialized and not force:
            continue
        already_has_environment = any(
            isinstance(packet, dict) and packet.get('PacketType') == 'environment'
            for packet in session.pending_packets
        )
        if force or not already_has_environment:
            slots_needing_environment.append(slot_name)

    if not slots_needing_environment:
        return

    for slot_name in slots_needing_environment:
        sid_for_slot = transport_state.sid_by_slot[slot_name]
        if sid_for_slot is None:
            continue
        session = transport_state.session_by_sid.get(sid_for_slot)
        if session is None:
            continue
        session.pending_packets.append(
            _build_packet_blueprint(
                'environment',
                _environment_body_for_client(slot_name),
                is_response=True,
            )
        )


def _extract_bridge_commands(bridge_result: dict[str, Any]) -> list[str]:
    global entity_setup_payload
    next_setup = bridge_result.get('setup_payload')
    if isinstance(next_setup, dict):
        entity_setup_payload = next_setup

    return [
        command for command in bridge_result.get('commands', [])
        if isinstance(command, str) and command.strip()
    ]


def _bridge_requests_force_environment_sync(bridge_result: dict[str, Any]) -> bool:
    return bool(bridge_result.get('force_environment_sync'))


def _force_environment_sync_for_connected_clients() -> None:
    if socketio is None:
        with transport_lock:
            _enqueue_environment_for_connected_clients(force=True)
        return

    deliveries: list[tuple[PlayerSlot, str, dict[str, Any]]] = []
    with transport_lock:
        for slot_name in ('p1', 'p2'):
            slot = cast(PlayerSlot, slot_name)
            sid_for_slot = transport_state.sid_by_slot[slot]
            if sid_for_slot is None:
                continue
            session = transport_state.session_by_sid.get(sid_for_slot)
            if session is None:
                continue
            env_packet = _issue_backend_packet_for_session(
                session,
                'environment',
                _environment_body_for_client(slot),
                is_response=True,
            )
            session.environment_initialized = True
            deliveries.append((slot, sid_for_slot, env_packet))

    for slot, sid_for_slot, env_packet in deliveries:
        socketio.emit('protocol_packets', {'packets': [env_packet]}, to=sid_for_slot)
        log_protocol_send([env_packet], slot)

def _normalize_target_slot(raw_target: str | None) -> PlayerSlot | None:
    if not isinstance(raw_target, str):
        return None
    normalized = raw_target.strip().lower()
    if normalized in {'player-1', 'p1', 'player1'}:
        return 'p1'
    if normalized in {'player-2', 'p2', 'player2'}:
        return 'p2'
    return None


def _classify_required_ack_slots(command: str, source_slot: str | None) -> set[PlayerSlot]:
    parts = command.strip().split()
    if not parts:
        return set()

    action = parts[0].lower()
    targeted_slot: PlayerSlot | None = None

    connected_slots: set[PlayerSlot] = {
        cast(PlayerSlot, slot)
        for slot in ('p1', 'p2')
        if transport_state.sid_by_slot[cast(PlayerSlot, slot)] is not None
    }

    if action == 'notify' and len(parts) >= 2:
        notify_target = parts[1].strip().lower()
        if notify_target in {'both', 'all'}:
            # Require both connected clients to ACK shared notify commands
            # before input is unlocked again.
            return connected_slots if connected_slots else {'p1', 'p2'}

    if action in {'lock-input', 'lock_input', 'unlock-input', 'unlock_input'} and len(parts) >= 2:
        targeted_slot = _normalize_target_slot(parts[1])
        if targeted_slot is not None:
            return {targeted_slot}

    if action in {'notify', 'reveal'} and len(parts) >= 2:
        targeted_slot = _normalize_target_slot(parts[1])
    elif action == 'input' and len(parts) >= 3:
        targeted_slot = _normalize_target_slot(parts[2])

    if targeted_slot is not None:
        return {targeted_slot}

    if connected_slots:
        return connected_slots

    normalized_source = _normalize_client_slot(source_slot)
    if normalized_source in {'p1', 'p2'}:
        return {cast(PlayerSlot, normalized_source)}

    # Conservative fallback: never return an empty set, which would make the
    # command impossible to deliver through per-slot ready dispatch.
    return {'p1', 'p2'}


def _enqueue_bridge_commands(commands: list[str], source_slot: str | None) -> None:
    global next_command_id
    connected_slots: set[PlayerSlot] = {
        cast(PlayerSlot, slot)
        for slot in ('p1', 'p2')
        if transport_state.sid_by_slot[cast(PlayerSlot, slot)] is not None
    }

    expanded_commands: list[str] = []
    for command in commands:
        command_text = command.strip()
        if not command_text:
            continue

        action = command_text.split()[0].lower()
        required_slots = _classify_required_ack_slots(command_text, source_slot)

        should_wrap_with_remote_lock = (
            len(required_slots) == 1
            and len(connected_slots) == 2
            and action not in {'lock-input', 'lock_input', 'unlock-input', 'unlock_input'}
        )

        should_wrap_with_shared_lock = (
            len(required_slots) > 1
            and len(connected_slots) == 2
            and action not in {'lock-input', 'lock_input', 'unlock-input', 'unlock_input', 'notify'}
        )

        if should_wrap_with_remote_lock:
            target_slot = next(iter(required_slots))
            passive_slot: PlayerSlot = 'p2' if target_slot == 'p1' else 'p1'
            if passive_slot in connected_slots:
                expanded_commands.append(f'lock-input {passive_slot}')
                expanded_commands.append(command_text)
                expanded_commands.append(f'unlock-input {passive_slot}')
                continue

        if should_wrap_with_shared_lock:
            expanded_commands.append('lock-input')
            expanded_commands.append(command_text)
            expanded_commands.append('unlock-input')
            continue

        expanded_commands.append(command_text)

    for command in expanded_commands:
        pending_command_acks.append(
            PendingCommandAck(
                command_id=next_command_id,
                command=command,
                required_slots=_classify_required_ack_slots(command, source_slot),
            )
        )
        next_command_id += 1
    if expanded_commands:
        with transport_lock:
            registration_condition.notify_all()
        _emit_ready_commands_to_connected_clients()


def _emit_ready_commands_to_connected_clients() -> None:
    if socketio is None:
        return

    deliveries: list[tuple[PlayerSlot, str, list[dict[str, Any]]]] = []
    with transport_lock:
        for slot_name in ('p1', 'p2'):
            slot = cast(PlayerSlot, slot_name)
            sid_for_slot = transport_state.sid_by_slot[slot]
            if sid_for_slot is None:
                continue
            session = transport_state.session_by_sid.get(sid_for_slot)
            if session is None:
                continue
            packets = _commands_ready_for_slot(slot, is_response=True, session=session)
            if not packets:
                continue
            deliveries.append((slot, sid_for_slot, packets))

    for slot, sid_for_slot, packets in deliveries:
        socketio.emit('protocol_packets', {'packets': packets}, to=sid_for_slot)
        log_protocol_send(packets, slot)


def _build_command_packet(
    pending: PendingCommandAck,
    is_response: bool,
    session: ClientSession | None,
) -> dict[str, Any]:
    body = {
        'command': pending.command,
        'command_id': pending.command_id,
        'target_slots': sorted(pending.required_slots),
    }
    if session is not None:
        return _issue_backend_packet_for_session(session, 'command', body, is_response=is_response)
    return _issue_backend_packet('command', body, is_response=is_response)


def _commands_ready_for_slot(
    slot: str | None,
    is_response: bool,
    session: ClientSession | None,
) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    if not pending_command_acks:
        return packets

    head = pending_command_acks[0]
    normalized_slot = _normalize_client_slot(slot)
    is_notify_command = head.command.strip().lower().startswith('notify ')

    if normalized_slot is None:
        packets.append(_build_command_packet(head, is_response=is_response, session=session))
        return packets

    recipient = cast(PlayerSlot, normalized_slot)
    if recipient not in head.required_slots:
        # Notify is visible protocol state for all clients (target sees overlay,
        # non-target enters passive lock), but ACK is still required only from
        # slots listed in required_slots.
        if not is_notify_command:
            return packets
    if recipient in head.delivered_slots:
        return packets

    head.delivered_slots.add(recipient)
    packets.append(_build_command_packet(head, is_response=is_response, session=session))
    return packets


def _acknowledge_head_command(command: str, source_slot: str | None) -> tuple[bool, str | None]:
    if not pending_command_acks:
        return False, None

    head = pending_command_acks[0]
    if head.command != command:
        return False, None

    normalized_slot = _normalize_client_slot(source_slot)

    # Legacy single-client mode without slot identity.
    if not head.required_slots:
        pending_command_acks.pop(0)
        return True, head.command

    if normalized_slot not in {'p1', 'p2'}:
        return False, None

    slot = cast(PlayerSlot, normalized_slot)
    if slot not in head.required_slots:
        return False, None

    head.acked_slots.add(slot)
    if head.required_slots.issubset(head.acked_slots):
        pending_command_acks.pop(0)
        with transport_lock:
            registration_condition.notify_all()
        return True, head.command

    return False, None


def _pending_commands_for_slot(slot: PlayerSlot) -> list[str]:
    return [
        pending.command
        for pending in pending_command_acks
        if slot in pending.required_slots and slot not in pending.acked_slots
    ]


def _reset_delivery_state_for_slot(slot: PlayerSlot) -> None:
    for pending in pending_command_acks:
        if slot in pending.required_slots and slot not in pending.acked_slots:
            pending.delivered_slots.discard(slot)


def _process_protocol_packet(payload: dict[str, Any], client_slot: str | None) -> tuple[dict[str, Any], int]:

    ack_raw = payload.get('ACK')
    packet_type_raw = payload.get('PacketType')
    body_raw = payload.get('Body', {})
    client_id_raw = payload.get('client_id')
    reconnect_token_raw = payload.get('reconnect_token')

    if not isinstance(ack_raw, int):
        return {'ok': False, 'error': 'ACK must be an integer.'}, 400

    if not isinstance(packet_type_raw, str) or packet_type_raw not in {
        'ready',
        'register_client',
        'request_environment',
        'update_frontend',
        'frontend_event',
    }:
        return {'ok': False, 'error': 'PacketType is invalid.'}, 400

    body = body_raw if isinstance(body_raw, dict) else {}

    client_id = client_id_raw if isinstance(client_id_raw, str) and client_id_raw.strip() else None
    reconnect_token = reconnect_token_raw if isinstance(reconnect_token_raw, str) and reconnect_token_raw.strip() else None

    sid_slot: PlayerSlot | None = None
    session_for_client: ClientSession | None = None
    if client_id is not None:
        with transport_lock:
            sid_slot = transport_state.slot_for_sid(client_id)
            session_for_client = transport_state.session_by_sid.get(client_id)

    source_slot = _normalize_client_slot(client_slot) or sid_slot or _extract_client_slot_hint(body)

    log_protocol_recv(ack_raw, packet_type_raw, list(body.keys()), source_slot)

    # Resync path:
    # Multi-client transport cannot validate ACK against a single global SEQ,
    # because clients may receive different packet subsets at different times.
    # Validate ACK monotonicity per client session instead.
    if packet_type_raw != 'register_client':
        if session_for_client is not None:
            if ack_raw < session_for_client.last_ack:
                log_protocol_ack_mismatch(ack_raw, session_for_client.last_ack, packet_type_raw, source_slot)
                mismatch_packet = _issue_backend_packet_for_session(
                    session_for_client,
                    'environment',
                    _environment_body_for_client(source_slot),
                    is_response=True,
                )
                log_protocol_send([mismatch_packet], source_slot)
                return {
                    'ok': True,
                    'packets': [mismatch_packet],
                }, 200
            session_for_client.last_ack = ack_raw
        elif ack_raw != protocol_seq:
            # Legacy/fallback path when no client session identity is available.
            log_protocol_ack_mismatch(ack_raw, protocol_seq, packet_type_raw, source_slot)
            mismatch_packet = _issue_backend_packet('environment', _environment_body_for_client(source_slot), is_response=True)
            log_protocol_send([mismatch_packet], source_slot)
            return {
                'ok': True,
                'packets': [mismatch_packet],
            }, 200

    packets: list[dict[str, Any]] = []

    if packet_type_raw == 'register_client':
        if client_id is None:
            return {'ok': False, 'error': 'register_client requires client_id.'}, 400

        requested_slot = _normalize_client_slot(body.get('requested_slot')) or _normalize_client_slot(client_slot)

        with transport_lock:
            session = transport_state.assign_slot(
                sid=client_id,
                requested_slot=requested_slot,
                reconnect_token=reconnect_token,
            )

            if session is None:
                return {'ok': False, 'error': 'Both player slots are occupied.'}, 409

            both_connected = transport_state.both_players_connected()

            # Initialization barrier: hold registration until both player slots
            # are filled. This avoids client-side registration loops/polling.
            while not both_connected:
                registration_condition.wait()
                both_connected = transport_state.both_players_connected()

            if both_connected:
                _enqueue_environment_for_connected_clients()
                registration_condition.notify_all()

        source_slot = session.slot

        if session.pending_packets:
            packets.extend(_drain_pending_packets_for_session(session))
        log_protocol_send(packets, source_slot)
        return {
            'ok': True,
            'packets': packets,
            'client_slot': session.slot,
            'reconnect_token': session.reconnect_token,
            'both_players_connected': True,
            'waiting_for_opponent': False,
        }, 200

    if packet_type_raw == 'request_environment':
        if session_for_client is not None:
            env_packet = _issue_backend_packet_for_session(
                session_for_client,
                'environment',
                _environment_body_for_client(source_slot),
                is_response=True,
            )
            # Explicit environment refreshes after bootstrap are valid and
            # should not reset bootstrap state or trigger registration loops.
            session_for_client.environment_initialized = True
            packets.append(env_packet)
        else:
            packets.append(
                _issue_backend_packet(
                    'environment',
                    _environment_body_for_client(source_slot),
                    is_response=True,
                )
            )

        log_protocol_send(packets, source_slot)
        return {'ok': True, 'packets': packets}, 200

    if packet_type_raw == 'ready':
        with transport_lock:
            slot_session = session_for_client
            if client_id is not None:
                slot_session = transport_state.session_by_sid.get(client_id)

            if slot_session is not None and slot_session.pending_packets:
                packets.extend(_drain_pending_packets_for_session(slot_session))

            packets.extend(_commands_ready_for_slot(source_slot, is_response=True, session=slot_session))
        log_protocol_send(packets, source_slot)
        return {'ok': True, 'packets': packets}, 200

    if packet_type_raw == 'update_frontend':
        command = body.get('command')
        input_response = body.get('input_response')
        notify_response = body.get('notify_response')

        log_protocol_update(
            isinstance(command, str) and bool(command.strip()),
            isinstance(input_response, dict),
            isinstance(notify_response, dict),
            source_slot,
        )

        if isinstance(input_response, dict):
            bridge_result = frontend_game_bridge.handle_frontend_event(
                'input_result',
                input_response,
                {},
            )
            _enqueue_bridge_commands(_extract_bridge_commands(bridge_result), source_slot)
            if _bridge_requests_force_environment_sync(bridge_result):
                _force_environment_sync_for_connected_clients()

        if isinstance(command, str) and command.strip():
            ack_completed, acked_command = _acknowledge_head_command(command, source_slot)
            if ack_completed and isinstance(acked_command, str) and acked_command.strip():
                if acked_command.strip().lower().startswith('notify '):
                    _enqueue_bridge_commands(['unlock-input'], source_slot)
                bridge_result = frontend_game_bridge.handle_frontend_event(
                    'terminal_log',
                    {
                        'line': 'ACK backend_update_processed',
                        'command': acked_command,
                    },
                    {},
                )
                _enqueue_bridge_commands(_extract_bridge_commands(bridge_result), source_slot)
                if _bridge_requests_force_environment_sync(bridge_result):
                    _force_environment_sync_for_connected_clients()

        packets.extend(_commands_ready_for_slot(source_slot, is_response=True, session=session_for_client))
        _emit_ready_commands_to_connected_clients()

        log_protocol_send(packets, source_slot)

        return {'ok': True, 'packets': packets}, 200

    # frontend_event
    event_name = body.get('event_type')
    response_data = body.get('response_data', {})
    context = body.get('context', {})

    if not isinstance(event_name, str) or not event_name.strip():
        return {'ok': False, 'error': 'frontend_event requires event_type.'}, 400

    bridge_result = frontend_game_bridge.handle_frontend_event(
        event_name,
        response_data if isinstance(response_data, dict) else {},
        context if isinstance(context, dict) else {},
    )
    _enqueue_bridge_commands(_extract_bridge_commands(bridge_result), source_slot)
    if _bridge_requests_force_environment_sync(bridge_result):
        _force_environment_sync_for_connected_clients()
    packets.extend(_commands_ready_for_slot(source_slot, is_response=True, session=session_for_client))
    _emit_ready_commands_to_connected_clients()
    log_protocol_event(
        event_name,
        list(response_data.keys()) if isinstance(response_data, dict) else [],
        list(context.keys()) if isinstance(context, dict) else [],
        source_slot,
    )
    log_protocol_send(packets, source_slot)
    return {'ok': True, 'packets': packets}, 200


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS, GET'
    return response


@app.get('/health')
def health() -> tuple[dict[str, str], int]:
    return {'status': 'ok', 'timestamp': _utc_now_iso()}, 200


@app.route('/protocol', methods=['POST', 'OPTIONS'])
def protocol() -> tuple[dict[str, Any], int]:
    if request.method == 'OPTIONS':
        return {'ok': True}, 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {'ok': False, 'error': 'Body must be a JSON object.'}, 400

    client_slot = _normalize_client_slot(payload.get('client_slot'))
    return _process_protocol_packet(payload, client_slot)


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


    @socketio.on('register_client_or_play')
    def socket_register_client_or_play(payload: Any) -> None:
        if emit is None:
            return

        data = payload if isinstance(payload, dict) else {}
        requested_slot = data.get('slot')
        reconnect_token = data.get('reconnect_token')
        sid = _socket_sid()

        with transport_lock:
            session = transport_state.assign_slot(
                sid=sid,
                requested_slot=requested_slot if isinstance(requested_slot, str) else None,
                reconnect_token=reconnect_token if isinstance(reconnect_token, str) else None,
            )

            if session is None:
                emit('registration_error', {
                    'ok': False,
                    'error': 'Both player slots are occupied.',
                })
                return

            both_connected = transport_state.both_players_connected()
            if both_connected:
                _enqueue_environment_for_connected_clients()
                registration_condition.notify_all()

        emit('registration_ok', {
            'ok': True,
            'slot': session.slot,
            'reconnect_token': session.reconnect_token,
            'both_players_connected': both_connected,
            'pending_replay_count': len(session.pending_commands),
        })

        if both_connected:
            assert socketio is not None
            for slot_name in ('p1', 'p2'):
                peer_sid = transport_state.sid_by_slot[slot_name]
                if peer_sid is None:
                    continue
                session_for_slot = transport_state.session_by_sid.get(peer_sid)
                if session_for_slot is None:
                    continue
                env_packet = None
                if session_for_slot.pending_packets:
                    for idx, candidate in enumerate(session_for_slot.pending_packets):
                        if isinstance(candidate, dict) and candidate.get('PacketType') == 'environment':
                            packet_type = candidate.get('PacketType')
                            body = candidate.get('Body')
                            is_response = candidate.get('IsResponse', True)
                            if isinstance(packet_type, str) and isinstance(body, dict):
                                env_packet = _issue_backend_packet_for_session(
                                    session_for_slot,
                                    packet_type,
                                    body,
                                    bool(is_response),
                                )
                            session_for_slot.pending_packets.pop(idx)
                            break
                if env_packet is None:
                    continue
                socketio.emit('protocol_packets', {'packets': [env_packet]}, to=peer_sid)
                log_protocol_send([env_packet], slot_name)


    @socketio.on('ready')
    def socket_ready(payload: Any) -> None:
        if emit is None:
            return

        data = payload if isinstance(payload, dict) else {}
        sid = _socket_sid()
        with transport_lock:
            client_slot = transport_state.slot_for_sid(sid)

        packet = {
            'ACK': data.get('ACK'),
            'PacketType': 'ready',
            'Body': data.get('Body') if isinstance(data.get('Body'), dict) else {},
            'client_id': sid,
        }
        response, status = _process_protocol_packet(packet, client_slot)
        if status != 200:
            emit('protocol_error', response)
            return
        emit('protocol_packets', {'packets': response.get('packets', [])})


    @socketio.on('update_frontend')
    def socket_update_frontend(payload: Any) -> None:
        if emit is None:
            return

        data = payload if isinstance(payload, dict) else {}
        sid = _socket_sid()
        with transport_lock:
            client_slot = transport_state.slot_for_sid(sid)

        packet = {
            'ACK': data.get('ACK'),
            'PacketType': 'update_frontend',
            'Body': data.get('Body') if isinstance(data.get('Body'), dict) else data,
            'client_id': sid,
        }
        response, status = _process_protocol_packet(packet, client_slot)
        if status != 200:
            emit('protocol_error', response)
            return
        emit('protocol_packets', {'packets': response.get('packets', [])})


    @socketio.on('frontend_event')
    def socket_frontend_event(payload: Any) -> None:
        if emit is None:
            return

        data = payload if isinstance(payload, dict) else {}
        sid = _socket_sid()
        with transport_lock:
            client_slot = transport_state.slot_for_sid(sid)

        packet = {
            'ACK': data.get('ACK'),
            'PacketType': 'frontend_event',
            'Body': data.get('Body') if isinstance(data.get('Body'), dict) else data,
            'client_id': sid,
        }
        response, status = _process_protocol_packet(packet, client_slot)
        if status != 200:
            emit('protocol_error', response)
            return
        emit('protocol_packets', {'packets': response.get('packets', [])})


    @socketio.on('disconnect')
    def socket_disconnect() -> None:
        sid = _socket_sid()
        with transport_lock:
            released_slot = transport_state.release_sid(sid)
            if released_slot is not None:
                slot = cast(PlayerSlot, released_slot)
                _reset_delivery_state_for_slot(slot)
                replay_commands = _pending_commands_for_slot(slot)
                transport_state.set_reserved_pending_commands(slot, replay_commands)
                transport_state.grace_remaining_seconds(slot)
        if released_slot is not None:
            log_protocol_event(
                'disconnect',
                [],
                ['sid_released', 'grace_window_s', 'pending_replay_count'],
                released_slot,
            )


if __name__ == '__main__':
    if socketio is not None:
        socketio.run(app, host='0.0.0.0', port=5500, debug=True)
    else:
        app.run(host='0.0.0.0', port=5500, debug=True)
