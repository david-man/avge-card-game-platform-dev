from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Condition
from threading import RLock
from threading import Timer
from time import monotonic
from typing import Any
from typing import cast
import os

from flask import Flask, request

try:
    from flask_socketio import SocketIO, emit
except ImportError:  # pragma: no cover - optional runtime dependency
    SocketIO = None  # type: ignore[assignment]
    emit = None  # type: ignore[assignment]

from .game_runner import FrontendGameBridge
from .game_runner import p1_username, p2_username
from .logging import (
    log_protocol_ack_mismatch,
    log_protocol_event,
    log_protocol_recv,
    log_protocol_send,
    log_protocol_update,
)
from .protocol_command_queue import (
    acknowledge_head_command,
    build_command_packet as command_queue_build_command_packet,
    classify_required_ack_slots,
    commands_ready_for_slot,
    pending_commands_for_slot,
    reset_delivery_state_for_slot,
)
from .protocol_packets import (
    build_packet_blueprint,
    drain_pending_packets_for_session,
    extract_client_slot_hint,
    issue_backend_packet,
    issue_backend_packet_for_session,
    normalize_client_slot,
    utc_now_iso,
)
from .scanner_commands import normalize_scanner_command
from .server_models import (
    ClientSession,
    MultiplayerTransportState,
    PendingCommandAck,
    PlayerSlot,
)

app = Flask(__name__)
frontend_game_bridge = FrontendGameBridge()
entity_setup_payload: dict[str, Any] = frontend_game_bridge.get_setup_payload()
protocol_seq = 0
DISCONNECT_GRACE_SECONDS = 5
TERMINATE_WHEN_BOTH_DISCONNECTED_SECONDS = 10


pending_command_acks: list[PendingCommandAck] = []
next_command_id = 1
first_player_join_seen = False
winner_announced = False
winner_main_menu_ack_slots: set[PlayerSlot] = set()
both_disconnected_termination_timer: Timer | None = None
both_disconnected_countdown_timer: Timer | None = None
both_disconnected_shutdown_deadline: float | None = None
termination_requested = False
disconnect_forfeit_timer_by_slot: dict[PlayerSlot, Timer | None] = {
    'p1': None,
    'p2': None,
}

transport_state = MultiplayerTransportState(disconnect_grace_seconds=DISCONNECT_GRACE_SECONDS)
transport_lock = RLock()
registration_condition = Condition(transport_lock)
expected_p1_session_id = os.getenv('P1_SESSION_ID', '').strip()
expected_p2_session_id = os.getenv('P2_SESSION_ID', '').strip()


def _expected_slot_for_router_session(session_id: str | None) -> PlayerSlot | None:
    if not isinstance(session_id, str) or not session_id.strip():
        return None
    normalized = session_id.strip()
    if expected_p1_session_id and normalized == expected_p1_session_id:
        return cast(PlayerSlot, 'p1')
    if expected_p2_session_id and normalized == expected_p2_session_id:
        return cast(PlayerSlot, 'p2')
    return None


def _short_session_id(session_id: str | None) -> str:
    if not isinstance(session_id, str):
        return '-'
    normalized = session_id.strip()
    if not normalized:
        return '-'
    return normalized[:8]


def _schedule_process_termination(reason: str) -> None:
    global termination_requested
    if termination_requested:
        return

    termination_requested = True
    log_protocol_event(
        'server_termination_scheduled',
        ['reason'],
        [],
        None,
    )

    def _terminate() -> None:
        os._exit(0)

    timer = Timer(0.25, _terminate)
    timer.daemon = True
    timer.start()


def _cancel_both_disconnected_termination_timer_locked() -> None:
    global both_disconnected_termination_timer, both_disconnected_countdown_timer, both_disconnected_shutdown_deadline
    timer = both_disconnected_termination_timer
    if timer is None:
        pass
    else:
        timer.cancel()
    both_disconnected_termination_timer = None

    countdown_timer = both_disconnected_countdown_timer
    if countdown_timer is not None:
        countdown_timer.cancel()
    both_disconnected_countdown_timer = None
    both_disconnected_shutdown_deadline = None


def _schedule_next_dual_disconnect_countdown_tick_locked() -> None:
    global both_disconnected_countdown_timer
    if termination_requested:
        return
    if both_disconnected_shutdown_deadline is None:
        return
    if any(transport_state.sid_by_slot[cast(PlayerSlot, slot)] is not None for slot in ('p1', 'p2')):
        return
    if both_disconnected_countdown_timer is not None:
        return

    def _countdown_tick() -> None:
        with transport_lock:
            global both_disconnected_countdown_timer
            both_disconnected_countdown_timer = None

            if termination_requested:
                return
            if both_disconnected_shutdown_deadline is None:
                return
            if any(transport_state.sid_by_slot[cast(PlayerSlot, slot)] is not None for slot in ('p1', 'p2')):
                return

            seconds_left = max(0, int(both_disconnected_shutdown_deadline - monotonic()))
            if seconds_left > 0:
                print(f'[SERVER_SHUTDOWN] dual_disconnect_countdown seconds_left={seconds_left}')
                _schedule_next_dual_disconnect_countdown_tick_locked()

    both_disconnected_countdown_timer = Timer(1.0, _countdown_tick)
    both_disconnected_countdown_timer.daemon = True
    both_disconnected_countdown_timer.start()


def _schedule_both_disconnected_termination_timer_locked() -> None:
    global both_disconnected_termination_timer, both_disconnected_shutdown_deadline
    if not first_player_join_seen or termination_requested:
        return
    if any(transport_state.sid_by_slot[cast(PlayerSlot, slot)] is not None for slot in ('p1', 'p2')):
        _cancel_both_disconnected_termination_timer_locked()
        return
    if both_disconnected_termination_timer is not None:
        return

    both_disconnected_shutdown_deadline = monotonic() + TERMINATE_WHEN_BOTH_DISCONNECTED_SECONDS
    print(f'[SERVER_SHUTDOWN] dual_disconnect_countdown seconds_left={int(TERMINATE_WHEN_BOTH_DISCONNECTED_SECONDS)}')
    _schedule_next_dual_disconnect_countdown_tick_locked()

    def _check_then_terminate() -> None:
        with transport_lock:
            global both_disconnected_termination_timer
            both_disconnected_termination_timer = None
            still_disconnected = all(
                transport_state.sid_by_slot[cast(PlayerSlot, slot)] is None
                for slot in ('p1', 'p2')
            )
            should_terminate = first_player_join_seen and still_disconnected and not termination_requested

        if should_terminate:
            _schedule_process_termination(
                f'both players disconnected for > {TERMINATE_WHEN_BOTH_DISCONNECTED_SECONDS:.0f}s after first join'
            )

    both_disconnected_termination_timer = Timer(
        TERMINATE_WHEN_BOTH_DISCONNECTED_SECONDS,
        _check_then_terminate,
    )
    both_disconnected_termination_timer.daemon = True
    both_disconnected_termination_timer.start()


def _mark_player_join_seen_locked() -> None:
    global first_player_join_seen
    first_player_join_seen = True
    _cancel_both_disconnected_termination_timer_locked()


def _cancel_disconnect_forfeit_timer_locked(slot: PlayerSlot) -> None:
    timer = disconnect_forfeit_timer_by_slot.get(slot)
    if timer is None:
        return
    timer.cancel()
    disconnect_forfeit_timer_by_slot[slot] = None


def _schedule_disconnect_forfeit_timer_locked(disconnected_slot: PlayerSlot) -> None:
    if termination_requested:
        return

    _cancel_disconnect_forfeit_timer_locked(disconnected_slot)

    def _forfeit_if_still_disconnected() -> None:
        winner_command: str | None = None
        with transport_lock:
            disconnect_forfeit_timer_by_slot[disconnected_slot] = None
            if transport_state.sid_by_slot[disconnected_slot] is not None:
                return

            winner_slot: PlayerSlot = 'p2' if disconnected_slot == 'p1' else 'p1'
            if transport_state.sid_by_slot[winner_slot] is None:
                return

            winner_label = p1_username if winner_slot == 'p1' else p2_username
            winner_command = f'winner {"player-1" if winner_slot == "p1" else "player-2"} {winner_label}'

        if winner_command is not None:
            _enqueue_bridge_commands([winner_command], source_slot=None)
            log_protocol_event(
                'disconnect_forfeit_winner_enqueued',
                ['winner_command', 'disconnected_slot'],
                [],
                winner_slot,
            )

    timer = Timer(DISCONNECT_GRACE_SECONDS, _forfeit_if_still_disconnected)
    timer.daemon = True
    disconnect_forfeit_timer_by_slot[disconnected_slot] = timer
    timer.start()

socketio: Any = None
if SocketIO is not None:
    socketio = SocketIO(app, cors_allowed_origins='*')


def _utc_now_iso() -> str:
    return utc_now_iso()


def _normalize_client_slot(raw_slot: Any) -> str | None:
    return normalize_client_slot(raw_slot)


def _extract_client_slot_hint(body: dict[str, Any]) -> str | None:
    return extract_client_slot_hint(body, normalize_slot=_normalize_client_slot)


def _socket_sid() -> str:
    raw_sid = getattr(request, 'sid', None)
    return raw_sid if isinstance(raw_sid, str) else ''


def _issue_backend_packet(packet_type: str, body: dict[str, Any], is_response: bool) -> dict[str, Any]:
    global protocol_seq
    packet, protocol_seq = issue_backend_packet(protocol_seq, packet_type, body, is_response)
    return packet


def _issue_backend_packet_for_session(
    session: ClientSession,
    packet_type: str,
    body: dict[str, Any],
    is_response: bool,
) -> dict[str, Any]:
    return issue_backend_packet_for_session(session, packet_type, body, is_response)


def _build_packet_blueprint(packet_type: str, body: dict[str, Any], is_response: bool) -> dict[str, Any]:
    return build_packet_blueprint(packet_type, body, is_response)


def _drain_pending_packets_for_session(session: ClientSession) -> list[dict[str, Any]]:
    return drain_pending_packets_for_session(
        session,
        issue_packet_for_session=_issue_backend_packet_for_session,
    )


def _current_environment_body() -> dict[str, Any]:
    return deepcopy(entity_setup_payload) if isinstance(entity_setup_payload, dict) else {}


def _environment_body_for_client(client_slot: str | None) -> dict[str, Any]:
    body = _current_environment_body()
    normalized = _normalize_client_slot(client_slot)
    body['playerView'] = normalized if normalized in {'p1', 'p2'} else 'spectator'
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

def _classify_required_ack_slots(command: str, source_slot: str | None) -> set[PlayerSlot]:
    return classify_required_ack_slots(
        command,
        source_slot,
        transport_state,
        _normalize_client_slot,
    )


def _enqueue_bridge_commands(commands: list[str], source_slot: str | None) -> None:
    global next_command_id, winner_announced, winner_main_menu_ack_slots
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
            and action not in {'lock-input', 'lock_input', 'unlock-input', 'unlock_input', 'notify', 'winner'}
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

    if any(command.strip().lower().startswith('winner ') for command in expanded_commands):
        winner_announced = True
        winner_main_menu_ack_slots = set()

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
    return command_queue_build_command_packet(
        pending,
        is_response,
        session,
        _issue_backend_packet,
        _issue_backend_packet_for_session,
    )


def _commands_ready_for_slot(
    slot: str | None,
    is_response: bool,
    session: ClientSession | None,
) -> list[dict[str, Any]]:
    return commands_ready_for_slot(
        slot,
        is_response,
        session,
        pending_command_acks,
        _normalize_client_slot,
        _issue_backend_packet,
        _issue_backend_packet_for_session,
    )


def _acknowledge_head_command(command: str, source_slot: str | None) -> tuple[bool, str | None]:
    return acknowledge_head_command(
        command,
        source_slot,
        pending_command_acks,
        _normalize_client_slot,
        registration_condition,
        transport_lock,
    )


def _pending_commands_for_slot(slot: PlayerSlot) -> list[str]:
    return pending_commands_for_slot(slot, pending_command_acks)


def _reset_delivery_state_for_slot(slot: PlayerSlot) -> None:
    reset_delivery_state_for_slot(slot, pending_command_acks)


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

        router_session_id_raw = body.get('session_id')
        router_session_id = router_session_id_raw.strip() if isinstance(router_session_id_raw, str) else None
        requested_slot = _normalize_client_slot(body.get('requested_slot')) or _normalize_client_slot(client_slot)
        expected_slot = _expected_slot_for_router_session(router_session_id)
        if expected_slot is not None:
            requested_slot = expected_slot

        with transport_lock:
            session = transport_state.assign_slot(
                sid=client_id,
                requested_slot=requested_slot,
                reconnect_token=reconnect_token,
            )

            if session is None:
                return {'ok': False, 'error': 'Both player slots are occupied.'}, 409

            _cancel_disconnect_forfeit_timer_locked(session.slot)
            _mark_player_join_seen_locked()

            both_connected = transport_state.both_players_connected()

            # Initialization barrier: hold registration until both player slots
            # are filled. This avoids client-side registration loops/polling.
            while not both_connected:
                registration_condition.wait()
                both_connected = transport_state.both_players_connected()

            if both_connected:
                _enqueue_environment_for_connected_clients()
                registration_condition.notify_all()

        print(
            '[SLOT_BIND] transport=http '
            f'router_session={_short_session_id(router_session_id)} '
            f'requested={requested_slot} expected={expected_slot} assigned={session.slot} '
            f'p1_expected={_short_session_id(expected_p1_session_id)} '
            f'p2_expected={_short_session_id(expected_p2_session_id)}'
        )

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
    global winner_main_menu_ack_slots
    event_name = body.get('event_type')
    response_data = body.get('response_data', {})
    context = body.get('context', {})

    if not isinstance(event_name, str) or not event_name.strip():
        return {'ok': False, 'error': 'frontend_event requires event_type.'}, 400

    normalized_event_name = str(event_name).strip().lower().replace('-', '_').replace(' ', '_')
    normalized_source_slot = _normalize_client_slot(source_slot)
    should_terminate_for_winner_menu = False
    if normalized_event_name == 'winner' and normalized_source_slot in {'p1', 'p2'} and winner_announced:
        with transport_lock:
            winner_main_menu_ack_slots.add(cast(PlayerSlot, normalized_source_slot))
            should_terminate_for_winner_menu = winner_main_menu_ack_slots.issuperset({'p1', 'p2'})

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

    if should_terminate_for_winner_menu:
        _schedule_process_termination('both players confirmed main menu after winner')

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


@app.route('/scanner/input', methods=['POST', 'OPTIONS'])
def scanner_input() -> tuple[dict[str, Any], int]:
    if request.method == 'OPTIONS':
        return {'ok': True}, 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {'ok': False, 'error': 'Body must be a JSON object.'}, 400

    raw_command = payload.get('command')
    if not isinstance(raw_command, str) or not raw_command.strip():
        return {'ok': False, 'error': 'scanner command must be a non-empty string.'}, 400

    source = payload.get('source')
    source_label = source if isinstance(source, str) and source.strip() else 'scanner'

    try:
        action, normalized_command = normalize_scanner_command(raw_command)
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}, 400

    _enqueue_bridge_commands([normalized_command], source_slot=None)

    with transport_lock:
        connected_slots = [
            slot_name
            for slot_name in ('p1', 'p2')
            if transport_state.sid_by_slot[cast(PlayerSlot, slot_name)] is not None
        ]

    log_protocol_event(
        'scanner_input',
        ['command', 'source', 'action'],
        ['normalized_command'],
        None,
    )

    return {
        'ok': True,
        'source': source_label,
        'action': action,
        'command': normalized_command,
        'connected_slots': connected_slots,
    }, 200


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
        router_session_id_raw = data.get('session_id')
        router_session_id = router_session_id_raw.strip() if isinstance(router_session_id_raw, str) else None
        expected_slot = _expected_slot_for_router_session(router_session_id)
        if expected_slot is not None:
            requested_slot = expected_slot
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

            _cancel_disconnect_forfeit_timer_locked(session.slot)
            _mark_player_join_seen_locked()

            both_connected = transport_state.both_players_connected()
            if both_connected:
                _enqueue_environment_for_connected_clients()
                registration_condition.notify_all()

        print(
            '[SLOT_BIND] transport=ws '
            f'router_session={_short_session_id(router_session_id)} '
            f'requested={requested_slot if isinstance(requested_slot, str) else None} '
            f'expected={expected_slot} assigned={session.slot} '
            f'p1_expected={_short_session_id(expected_p1_session_id)} '
            f'p2_expected={_short_session_id(expected_p2_session_id)}'
        )

        emit('registration_ok', {
            'ok': True,
            'slot': session.slot,
            'reconnect_token': session.reconnect_token,
            'both_players_connected': both_connected,
            'pending_replay_count': len(session.pending_commands),
        })

        if both_connected:
            assert socketio is not None
            connected_sids: list[str] = []
            for slot_name in ('p1', 'p2'):
                peer_sid = transport_state.sid_by_slot[slot_name]
                if peer_sid is None:
                    continue
                connected_sids.append(peer_sid)
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

            for peer_sid in connected_sids:
                socketio.emit('opponent_reconnected', {
                    'slot': session.slot,
                    'both_players_connected': True,
                }, to=peer_sid)


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
        peer_deliveries: list[tuple[PlayerSlot, str]] = []
        should_terminate_for_winner_menu = False
        with transport_lock:
            released_slot = transport_state.release_sid(sid)
            if released_slot is not None:
                slot = cast(PlayerSlot, released_slot)
                _reset_delivery_state_for_slot(slot)
                replay_commands = _pending_commands_for_slot(slot)
                transport_state.set_reserved_pending_commands(slot, replay_commands)
                transport_state.grace_remaining_seconds(slot)
                _schedule_disconnect_forfeit_timer_locked(slot)

                if winner_announced:
                    winner_main_menu_ack_slots.add(slot)
                    should_terminate_for_winner_menu = winner_main_menu_ack_slots.issuperset({'p1', 'p2'})

                for slot_name in ('p1', 'p2'):
                    peer_slot = cast(PlayerSlot, slot_name)
                    if peer_slot == slot:
                        continue
                    peer_sid = transport_state.sid_by_slot[peer_slot]
                    if peer_sid is not None:
                        peer_deliveries.append((peer_slot, peer_sid))

            _schedule_both_disconnected_termination_timer_locked()
        if released_slot is not None:
            log_protocol_event(
                'disconnect',
                [],
                ['sid_released', 'grace_window_s', 'pending_replay_count'],
                released_slot,
            )

            assert socketio is not None
            for peer_slot, peer_sid in peer_deliveries:
                socketio.emit('opponent_disconnected', {
                    'slot': released_slot,
                    'grace_seconds': DISCONNECT_GRACE_SECONDS,
                }, to=peer_sid)
                log_protocol_event(
                    'opponent_disconnected',
                    ['slot', 'grace_seconds'],
                    ['peer_sid'],
                    peer_slot,
                )

        if should_terminate_for_winner_menu:
            _schedule_process_termination('both players exited after winner (disconnect path)')


if __name__ == '__main__':
    server_host = os.getenv('SERVER_HOST', '0.0.0.0')
    server_port = int(os.getenv('SERVER_PORT', '5500'))
    server_debug = os.getenv('SERVER_DEBUG', 'true').strip().lower() in {'1', 'true', 'yes', 'on'}
    server_use_reloader = os.getenv('SERVER_USE_RELOADER', 'false').strip().lower() in {'1', 'true', 'yes', 'on'}
    if socketio is not None:
        socketio.run(
            app,
            host=server_host,
            port=server_port,
            debug=server_debug,
            use_reloader=server_use_reloader,
        )
    else:
        app.run(
            host=server_host,
            port=server_port,
            debug=server_debug,
            use_reloader=server_use_reloader,
        )
