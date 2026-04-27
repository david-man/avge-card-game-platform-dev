from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Condition
from threading import RLock
from threading import Thread
from threading import Timer
from time import monotonic
from typing import Any
from typing import cast
import os
import json
import urllib.error
import urllib.request

from flask import Flask, request

try:
    from flask_socketio import SocketIO, disconnect, emit
except ImportError:  # pragma: no cover - optional runtime dependency
    SocketIO = None  # type: ignore[assignment]
    disconnect = None  # type: ignore[assignment]
    emit = None  # type: ignore[assignment]

from .game_runner import BridgeEngineRuntimeError, FrontendGameBridge
from .game_runner import p1_username, p2_username
from ..constants import max_bench_size
from .logging import (
    log_input_trace,
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


def _resolve_init_finalize_timeout_seconds() -> float:
    raw = os.getenv('INIT_FINALIZE_TIMEOUT_SECONDS', '8').strip()
    try:
        parsed = float(raw)
    except Exception:
        return 8.0
    return max(1.0, min(parsed, 60.0))


INIT_FINALIZE_TIMEOUT_SECONDS = _resolve_init_finalize_timeout_seconds()

room_stage: str = 'init'
init_setup_submission_by_slot: dict[PlayerSlot, dict[str, Any] | None] = {
    'p1': None,
    'p2': None,
}


pending_command_acks: list[PendingCommandAck] = []
next_command_id = 1
first_player_join_seen = False
winner_announced = False
winner_main_menu_ack_slots: set[PlayerSlot] = set()
room_finished_notified = False
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
router_base_url = os.getenv('ROUTER_BASE_URL', 'http://127.0.0.1:5600').strip()
room_id_from_env = os.getenv('ROOM_ID', '').strip()


def _expected_slot_for_router_session(session_id: str | None) -> PlayerSlot | None:
    if not isinstance(session_id, str) or not session_id.strip():
        return None
    normalized = session_id.strip()
    if expected_p1_session_id and normalized == expected_p1_session_id:
        return cast(PlayerSlot, 'p1')
    if expected_p2_session_id and normalized == expected_p2_session_id:
        return cast(PlayerSlot, 'p2')
    return None


def _recover_reconnect_token_for_expected_slot(
    expected_slot: PlayerSlot | None,
    provided_reconnect_token: str | None,
) -> str | None:
    if isinstance(provided_reconnect_token, str) and provided_reconnect_token.strip():
        return provided_reconnect_token.strip()

    if expected_slot not in {'p1', 'p2'}:
        return None

    normalized_slot = cast(PlayerSlot, expected_slot)

    # Polling refreshes can reconnect before the prior sid is released.
    # If we can prove the slot via router session mapping, recover the active
    # slot token so assign_slot can perform an authenticated takeover.
    active_sid = transport_state.sid_by_slot.get(normalized_slot)
    if isinstance(active_sid, str) and active_sid:
        active_session = transport_state.session_by_sid.get(active_sid)
        if (
            active_session is not None
            and isinstance(active_session.reconnect_token, str)
            and active_session.reconnect_token.strip()
        ):
            return active_session.reconnect_token.strip()

    # If the client can prove slot identity via router session mapping,
    # recover the reserved reconnect token so grace-window reconnect succeeds
    # even when browser session storage lost the token.
    reserved = transport_state.reserved_session_by_slot.get(normalized_slot)
    if reserved is None:
        return None
    if not isinstance(reserved.reconnect_token, str) or not reserved.reconnect_token.strip():
        return None
    return reserved.reconnect_token.strip()


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


def _notify_router_room_finished(reason: str) -> None:
    if not room_id_from_env:
        return

    endpoint = f"{router_base_url.rstrip('/')}/rooms/finish"
    payload = {
        'room_id': room_id_from_env,
        'reason': reason,
    }
    body = json.dumps(payload).encode('utf-8')
    request_obj = urllib.request.Request(
        endpoint,
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=0.8) as response:
            _ = response.read()
    except urllib.error.URLError as exc:
        print(f'[ROOM_FINISH_NOTIFY] failed endpoint={endpoint} reason={reason} error={exc}')
    except Exception as exc:
        print(f'[ROOM_FINISH_NOTIFY] failed endpoint={endpoint} reason={reason} error={exc}')


def _mark_room_finished_once(reason: str) -> None:
    global room_finished_notified
    if room_finished_notified:
        return
    room_finished_notified = True
    _notify_router_room_finished(reason)


def _schedule_both_disconnected_termination_timer_locked() -> None:
    if not first_player_join_seen or termination_requested:
        return

    # Simplified policy: if both slots are disconnected at the same time,
    # immediately finish the room and terminate the room server.
    if any(transport_state.sid_by_slot[cast(PlayerSlot, slot)] is not None for slot in ('p1', 'p2')):
        return

    _mark_room_finished_once('both_players_disconnected')
    _schedule_process_termination('both players disconnected simultaneously')


def _mark_player_join_seen_locked() -> None:
    global first_player_join_seen
    first_player_join_seen = True


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


def _other_slot(slot: PlayerSlot) -> PlayerSlot:
    return cast(PlayerSlot, 'p2') if slot == 'p1' else cast(PlayerSlot, 'p1')


def _init_state_body_for_slot(slot: PlayerSlot) -> dict[str, Any]:
    own_ready = init_setup_submission_by_slot[slot] is not None
    opponent_slot = _other_slot(slot)
    opponent_ready = init_setup_submission_by_slot[opponent_slot] is not None
    ready_slots = [
        slot_name
        for slot_name in ('p1', 'p2')
        if init_setup_submission_by_slot[cast(PlayerSlot, slot_name)] is not None
    ]

    return {
        'stage': room_stage,
        'both_players_connected': transport_state.both_players_connected(),
        'self_ready': own_ready,
        'opponent_ready': opponent_ready,
        'ready_slots': ready_slots,
    }


def _remove_pending_packets_by_type(session: ClientSession, packet_type: str) -> None:
    session.pending_packets = [
        packet
        for packet in session.pending_packets
        if not (isinstance(packet, dict) and packet.get('PacketType') == packet_type)
    ]


def _enqueue_init_state_for_connected_clients(force: bool = False) -> None:
    slots_needing_init_state: list[PlayerSlot] = []
    for slot_name in ('p1', 'p2'):
        slot = cast(PlayerSlot, slot_name)
        sid_for_slot = transport_state.sid_by_slot[slot]
        if sid_for_slot is None:
            continue
        session = transport_state.session_by_sid.get(sid_for_slot)
        if session is None:
            continue
        already_has_init_state = any(
            isinstance(packet, dict) and packet.get('PacketType') == 'init_state'
            for packet in session.pending_packets
        )
        if force or not already_has_init_state:
            slots_needing_init_state.append(slot)

    if not slots_needing_init_state:
        return

    for slot in slots_needing_init_state:
        sid_for_slot = transport_state.sid_by_slot[slot]
        if sid_for_slot is None:
            continue
        session = transport_state.session_by_sid.get(sid_for_slot)
        if session is None:
            continue
        if force:
            _remove_pending_packets_by_type(session, 'init_state')
        session.pending_packets.append(
            _build_packet_blueprint(
                'init_state',
                _init_state_body_for_slot(slot),
                is_response=True,
            )
        )


def _validate_init_setup_submission(
    slot: PlayerSlot,
    body: dict[str, Any],
) -> tuple[bool, str | None, dict[str, Any] | None]:
    setup = _current_environment_body()
    cards_raw = setup.get('cards')
    if not isinstance(cards_raw, list):
        return False, 'environment payload missing cards list', None

    active_card_id_raw = body.get('active_card_id')
    bench_card_ids_raw = body.get('bench_card_ids')

    active_card_id = active_card_id_raw.strip() if isinstance(active_card_id_raw, str) else ''
    if not active_card_id:
        return False, 'active_card_id is required', None

    if not isinstance(bench_card_ids_raw, list):
        return False, 'bench_card_ids must be an array', None

    bench_card_ids: list[str] = []
    for raw in bench_card_ids_raw:
        if not isinstance(raw, str) or not raw.strip():
            return False, 'bench_card_ids must only contain non-empty card ids', None
        bench_card_ids.append(raw.strip())

    if len(bench_card_ids) > max_bench_size:
        raise ValueError(f'bench_card_ids cannot exceed {max_bench_size} cards')

    selected_ids = [active_card_id, *bench_card_ids]
    if len(set(selected_ids)) != len(selected_ids):
        return False, 'init setup card ids must be unique', None

    allowed_character_ids: set[str] = set()
    own_slot = cast(str, slot)
    own_hand = f'{own_slot}-hand'
    own_bench = f'{own_slot}-bench'
    own_active = f'{own_slot}-active'
    for raw_card in cards_raw:
        if not isinstance(raw_card, dict):
            continue

        card_id = raw_card.get('id')
        owner_id = raw_card.get('ownerId')
        holder_id = raw_card.get('holderId')
        card_type = raw_card.get('cardType')
        if not isinstance(card_id, str) or not card_id.strip():
            continue
        if owner_id != own_slot:
            continue
        if card_type != 'character':
            continue
        if holder_id not in {own_hand, own_bench, own_active}:
            continue

        allowed_character_ids.add(card_id.strip())

    if active_card_id not in allowed_character_ids:
        return False, 'active_card_id must be one of your visible character cards', None

    for bench_card_id in bench_card_ids:
        if bench_card_id not in allowed_character_ids:
            return False, 'bench_card_ids must be your visible character cards', None

    return True, None, {
        'active_card_id': active_card_id,
        'bench_card_ids': bench_card_ids,
    }


def _finalize_init_stage_locked() -> tuple[bool, str | None]:
    global frontend_game_bridge, entity_setup_payload, room_stage, pending_command_acks, next_command_id

    p1_submission = init_setup_submission_by_slot['p1']
    p2_submission = init_setup_submission_by_slot['p2']
    if not isinstance(p1_submission, dict) or not isinstance(p2_submission, dict):
        return False, 'both init submissions are required before finalizing'

    finalize_target = {
        'p1': deepcopy(p1_submission),
        'p2': deepcopy(p2_submission),
    }
    source_bridge = frontend_game_bridge
    worker_result: dict[str, Any] = {}

    def _build_finalized_bridge() -> None:
        try:
            candidate_bridge = source_bridge.clone_with_init_setup(finalize_target)
            worker_result['bridge'] = candidate_bridge
            worker_result['setup_payload'] = candidate_bridge.get_setup_payload()
        except Exception as exc:
            worker_result['error'] = exc

    started_at = monotonic()
    finalize_worker = Thread(target=_build_finalized_bridge, name='init-finalize-worker', daemon=True)
    finalize_worker.start()
    finalize_worker.join(INIT_FINALIZE_TIMEOUT_SECONDS)
    elapsed_ms = int((monotonic() - started_at) * 1000)

    if finalize_worker.is_alive():
        return False, f'init finalize timed out after {INIT_FINALIZE_TIMEOUT_SECONDS:.1f}s'

    finalize_error = worker_result.get('error')
    if isinstance(finalize_error, Exception):
        return False, f'failed to finalize init setup: {finalize_error}'

    candidate_bridge = worker_result.get('bridge')
    candidate_setup_payload = worker_result.get('setup_payload')
    if not isinstance(candidate_bridge, FrontendGameBridge) or not isinstance(candidate_setup_payload, dict):
        return False, 'failed to finalize init setup: incomplete finalized state'

    frontend_game_bridge = candidate_bridge
    entity_setup_payload = candidate_setup_payload
    pending_command_acks.clear()
    next_command_id = 1
    room_stage = 'live'
    init_setup_submission_by_slot['p1'] = None
    init_setup_submission_by_slot['p2'] = None

    _enqueue_environment_for_connected_clients(force=True)
    _enqueue_init_state_for_connected_clients(force=True)
    registration_condition.notify_all()
    print(
        '[INIT_SETUP][FINALIZE_OK] '
        f'elapsed_ms={elapsed_ms} '
        f"p1_active={finalize_target['p1'].get('active_card_id')!r} "
        f"p2_active={finalize_target['p2'].get('active_card_id')!r}"
    )
    return True, None


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
        if force:
            _remove_pending_packets_by_type(session, 'environment')
        session.pending_packets.append(
            _build_packet_blueprint(
                'environment',
                _environment_body_for_client(slot_name),
                is_response=True,
            )
        )


def _emit_pending_packets_to_connected_clients(exclude_slots: set[PlayerSlot] | None = None) -> None:
    if socketio is None:
        return

    excluded = exclude_slots if isinstance(exclude_slots, set) else set()
    deliveries: list[tuple[PlayerSlot, str, list[dict[str, Any]]]] = []
    with transport_lock:
        for slot_name in ('p1', 'p2'):
            slot = cast(PlayerSlot, slot_name)
            if slot in excluded:
                continue
            sid_for_slot = transport_state.sid_by_slot[slot]
            if sid_for_slot is None:
                continue
            session = transport_state.session_by_sid.get(sid_for_slot)
            if session is None or not session.pending_packets:
                continue
            packets = _drain_pending_packets_for_session(session)
            if not packets:
                continue
            deliveries.append((slot, sid_for_slot, packets))

    for slot, sid_for_slot, packets in deliveries:
        socketio.emit('protocol_packets', _protocol_packets_emit_payload_for_slot(slot, packets), to=sid_for_slot)
        log_protocol_send(packets, slot)


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


def _handle_bridge_runtime_error(
    exc: Exception,
    source_slot: str | None,
    session_for_client: ClientSession | None,
) -> tuple[dict[str, Any], int]:
    print(f'[GAME_RUNNER_ERROR] {exc}')
    log_protocol_event(
        'game_runner_error',
        ['error_message'],
        [],
        source_slot,
    )

    _enqueue_bridge_commands(['notify both Game_error -1'], source_slot)
    packets = _commands_ready_for_slot(source_slot, is_response=True, session=session_for_client)

    _mark_room_finished_once('game_runner_error')
    _schedule_process_termination('game runner error')

    log_protocol_send(packets, source_slot)
    return {
        'ok': True,
        'packets': packets,
        'fatal_error': True,
    }, 200


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
        socketio.emit('protocol_packets', _protocol_packets_emit_payload_for_slot(slot, [env_packet]), to=sid_for_slot)
        log_protocol_send([env_packet], slot)

def _classify_required_ack_slots(command: str, source_slot: str | None) -> set[PlayerSlot]:
    return classify_required_ack_slots(
        command,
        source_slot,
        transport_state,
        _normalize_client_slot,
    )


def _blocked_pending_command_for_slot(source_slot: str | None) -> PendingCommandAck | None:
    normalized_slot = _normalize_client_slot(source_slot)
    if normalized_slot not in {'p1', 'p2'}:
        return None

    if len(pending_command_acks) == 0:
        return None

    head = pending_command_acks[0]
    awaiting_slots = head.required_slots.difference(head.acked_slots)
    if len(awaiting_slots) == 0:
        return None

    slot = cast(PlayerSlot, normalized_slot)
    if slot in awaiting_slots:
        return None

    return head


def _effective_protocol_slot(source_slot: str | None, response: dict[str, Any] | None = None) -> PlayerSlot | None:
    response_slot = None
    if isinstance(response, dict):
        response_slot = _normalize_client_slot(response.get('client_slot'))

    if response_slot in {'p1', 'p2'}:
        return cast(PlayerSlot, response_slot)

    normalized_source = _normalize_client_slot(source_slot)
    if normalized_source in {'p1', 'p2'}:
        return cast(PlayerSlot, normalized_source)

    return None


def _augment_protocol_response_with_pending_peer_ack(
    response: dict[str, Any],
    source_slot: str | None,
) -> dict[str, Any]:
    enriched = dict(response)
    slot = _effective_protocol_slot(source_slot, response)
    blocked_pending_command = _blocked_pending_command_for_slot(slot)

    enriched['blocked_pending_peer_ack'] = blocked_pending_command is not None
    if blocked_pending_command is not None and not isinstance(enriched.get('blocked_command'), str):
        enriched['blocked_command'] = blocked_pending_command.command

    return enriched


def _protocol_packets_emit_payload_for_slot(slot: str | None, packets: list[dict[str, Any]]) -> dict[str, Any]:
    blocked_pending_command = _blocked_pending_command_for_slot(slot)
    payload: dict[str, Any] = {
        'packets': packets,
        'blocked_pending_peer_ack': blocked_pending_command is not None,
    }

    if blocked_pending_command is not None:
        payload['blocked_command'] = blocked_pending_command.command

    return payload


def _issue_environment_resync_packet_for_source(
    source_slot: str | None,
    session_for_client: ClientSession | None,
) -> dict[str, Any]:
    body = _environment_body_for_client(source_slot)
    if session_for_client is not None:
        return _issue_backend_packet_for_session(
            session_for_client,
            'environment',
            body,
            is_response=True,
        )

    return _issue_backend_packet('environment', body, is_response=True)


def _enqueue_bridge_commands(commands: list[str], source_slot: str | None) -> None:
    global next_command_id, winner_announced, winner_main_menu_ack_slots
    expanded_commands: list[str] = []
    for command in commands:
        command_text = command.strip()
        if not command_text:
            continue

        expanded_commands.append(command_text)

    if any(command.strip().lower().startswith('winner ') for command in expanded_commands):
        winner_announced = True
        winner_main_menu_ack_slots = set()
        _mark_room_finished_once('winner_declared')

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
        _emit_pending_peer_ack_status_to_connected_clients()


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
        socketio.emit('protocol_packets', _protocol_packets_emit_payload_for_slot(slot, packets), to=sid_for_slot)
        log_protocol_send(packets, slot)


def _emit_pending_peer_ack_status_to_connected_clients() -> None:
    if socketio is None:
        return

    deliveries: list[tuple[PlayerSlot, str, dict[str, Any]]] = []
    with transport_lock:
        for slot_name in ('p1', 'p2'):
            slot = cast(PlayerSlot, slot_name)
            sid_for_slot = transport_state.sid_by_slot[slot]
            if sid_for_slot is None:
                continue

            deliveries.append((
                slot,
                sid_for_slot,
                _protocol_packets_emit_payload_for_slot(slot, []),
            ))

    for slot, sid_for_slot, payload in deliveries:
        socketio.emit('protocol_packets', payload, to=sid_for_slot)
        log_protocol_send([], slot)


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
        'init_setup_done',
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
            recovered_reconnect_token = _recover_reconnect_token_for_expected_slot(
                expected_slot,
                reconnect_token,
            )
            session = transport_state.assign_slot(
                sid=client_id,
                requested_slot=requested_slot,
                reconnect_token=recovered_reconnect_token,
            )

            if session is None:
                return {'ok': False, 'error': 'Both player slots are occupied.'}, 409

            _cancel_disconnect_forfeit_timer_locked(session.slot)
            _mark_player_join_seen_locked()

            both_connected = transport_state.both_players_connected()

            # Always prime newly connected clients with current state, even if
            # the opponent is still disconnected.
            _enqueue_environment_for_connected_clients()
            _enqueue_init_state_for_connected_clients(force=True)
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
            'waiting_for_init': room_stage == 'init',
        }, 200

    if packet_type_raw == 'init_setup_done':
        if session_for_client is None or source_slot not in {'p1', 'p2'}:
            print(
                '[INIT_SETUP][REJECT] '
                "reason='missing_session_or_slot' "
                f'source_slot={source_slot!r}'
            )
            return {'ok': False, 'error': 'init_setup_done requires an assigned player slot.'}, 400

        slot = cast(PlayerSlot, source_slot)
        finalized_now = False
        finalize_failed = False
        finalize_error_message: str | None = None
        with transport_lock:
            if room_stage != 'init':
                print(
                    '[INIT_SETUP][REJECT] '
                    "reason='already_finalized' "
                    f'slot={slot!r} stage={room_stage!r}'
                )
                return {'ok': False, 'error': 'Init setup is already finalized.'}, 409

            try:
                ok, error_message, normalized_submission = _validate_init_setup_submission(slot, body)
            except ValueError as exc:
                print(
                    '[INIT_SETUP][REJECT] '
                    "reason='invalid_payload' "
                    f'slot={slot!r} error={str(exc)!r}'
                )
                return {'ok': False, 'error': str(exc)}, 400

            if not ok or normalized_submission is None:
                print(
                    '[INIT_SETUP][REJECT] '
                    "reason='validation_failed' "
                    f'slot={slot!r} error={error_message!r}'
                )
                return {'ok': False, 'error': error_message or 'invalid init setup payload'}, 400

            init_setup_submission_by_slot[slot] = normalized_submission
            print(
                '[INIT_SETUP][ACCEPT] '
                f'slot={slot!r} '
                f"active={normalized_submission.get('active_card_id')!r} "
                f"bench_count={len(normalized_submission.get('bench_card_ids', []))}"
            )
            _enqueue_init_state_for_connected_clients(force=True)

            should_finalize = (
                init_setup_submission_by_slot['p1'] is not None
                and init_setup_submission_by_slot['p2'] is not None
            )
            finalize_error: str | None = None
            if should_finalize:
                print(
                    '[INIT_SETUP][FINALIZE_START] '
                    f'trigger_slot={slot!r} '
                    f"p1_active={init_setup_submission_by_slot['p1'].get('active_card_id') if isinstance(init_setup_submission_by_slot['p1'], dict) else None!r} "
                    f"p2_active={init_setup_submission_by_slot['p2'].get('active_card_id') if isinstance(init_setup_submission_by_slot['p2'], dict) else None!r}"
                )
                finalized_ok, finalize_error = _finalize_init_stage_locked()
                if not finalized_ok:
                    finalize_failed = True
                    finalize_error_message = finalize_error or 'failed to finalize init setup'
                    print(
                        '[INIT_SETUP][FINALIZE_FAILED] '
                        f'slot={slot!r} error={finalize_error_message!r} '
                        f"p1_submission={init_setup_submission_by_slot['p1']!r} "
                        f"p2_submission={init_setup_submission_by_slot['p2']!r}"
                    )
                    # Allow both clients to adjust setup and resubmit.
                    init_setup_submission_by_slot['p1'] = None
                    init_setup_submission_by_slot['p2'] = None
                    _enqueue_init_state_for_connected_clients(force=True)
                else:
                    finalized_now = True

            if not finalize_failed and session_for_client.pending_packets:
                packets.extend(_drain_pending_packets_for_session(session_for_client))

        if finalize_failed:
            _emit_pending_packets_to_connected_clients()
            return {
                'ok': False,
                'error': finalize_error_message or 'failed to finalize init setup',
            }, 500

        # Keep non-submitting peers synchronized with latest init_state/finalization
        # while preserving in-order direct delivery for the submitting slot.
        _emit_pending_packets_to_connected_clients(exclude_slots={slot})

        log_protocol_send(packets, source_slot)
        return {
            'ok': True,
            'packets': packets,
            'init_stage': room_stage,
            'self_ready': init_setup_submission_by_slot[slot] is not None,
            'opponent_ready': init_setup_submission_by_slot[_other_slot(slot)] is not None,
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

    if room_stage == 'init' and packet_type_raw == 'frontend_event':
        # During INIT we ignore gameplay frontend events, but winner-flow
        # packets must still be accepted so disconnect-forfeit can complete.
        # Note: update_frontend packets must pass through in INIT so query
        # responses (input/notify) are never dropped.
        raw_event_type = body.get('event_type')
        normalized_event_type = (
            str(raw_event_type).strip().lower().replace('-', '_').replace(' ', '_')
            if isinstance(raw_event_type, str)
            else ''
        )
        is_winner_event = normalized_event_type == 'winner'

        if not is_winner_event:
            with transport_lock:
                if session_for_client is not None and session_for_client.pending_packets:
                    packets.extend(_drain_pending_packets_for_session(session_for_client))
            log_protocol_send(packets, source_slot)
            return {'ok': True, 'packets': packets}, 200

    if packet_type_raw == 'update_frontend':
        command = body.get('command')
        input_response = body.get('input_response')
        notify_response = body.get('notify_response')

        blocked_pending_command = _blocked_pending_command_for_slot(source_slot)
        if blocked_pending_command is not None and (
            isinstance(input_response, dict) or isinstance(notify_response, dict)
        ):
            packets.append(_issue_environment_resync_packet_for_source(source_slot, session_for_client))
            log_protocol_send(packets, source_slot)
            return {
                'ok': True,
                'packets': packets,
                'rejected': True,
                'error': 'input blocked: awaiting response from the other client',
                'blocked_command': blocked_pending_command.command,
            }, 200

        log_protocol_update(
            isinstance(command, str) and bool(command.strip()),
            isinstance(input_response, dict),
            isinstance(notify_response, dict),
            source_slot,
        )

        if isinstance(input_response, dict):
            log_input_trace(
                'server_received_input_response',
                client_slot=source_slot,
                room_stage=room_stage,
                command=command if isinstance(command, str) else None,
                payload_keys=sorted(input_response.keys()),
                payload=input_response,
            )
            try:
                bridge_result = frontend_game_bridge.handle_frontend_event(
                    'input_result',
                    input_response,
                    {},
                )
            except BridgeEngineRuntimeError as exc:
                return _handle_bridge_runtime_error(exc, source_slot, session_for_client)
            except Exception as exc:
                return _handle_bridge_runtime_error(exc, source_slot, session_for_client)

            bridge_commands = _extract_bridge_commands(bridge_result)
            force_sync = _bridge_requests_force_environment_sync(bridge_result)
            log_input_trace(
                'server_processed_input_response',
                client_slot=source_slot,
                bridge_commands=bridge_commands,
                force_environment_sync=force_sync,
            )
            _enqueue_bridge_commands(bridge_commands, source_slot)
            if force_sync:
                _force_environment_sync_for_connected_clients()

        ack_completed = False
        if isinstance(command, str) and command.strip():
            ack_completed, acked_command = _acknowledge_head_command(command, source_slot)
            if ack_completed and isinstance(acked_command, str) and acked_command.strip():
                try:
                    bridge_result = frontend_game_bridge.handle_frontend_event(
                        'terminal_log',
                        {
                            'line': 'ACK backend_update_processed',
                            'command': acked_command,
                        },
                        {},
                    )
                except BridgeEngineRuntimeError as exc:
                    return _handle_bridge_runtime_error(exc, source_slot, session_for_client)
                except Exception as exc:
                    return _handle_bridge_runtime_error(exc, source_slot, session_for_client)

                _enqueue_bridge_commands(_extract_bridge_commands(bridge_result), source_slot)
                if _bridge_requests_force_environment_sync(bridge_result):
                    _force_environment_sync_for_connected_clients()

        packets.extend(_commands_ready_for_slot(source_slot, is_response=True, session=session_for_client))
        _emit_ready_commands_to_connected_clients()
        if ack_completed:
            _emit_pending_peer_ack_status_to_connected_clients()

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
    blocked_pending_command = _blocked_pending_command_for_slot(source_slot)
    if blocked_pending_command is not None:
        packets.append(_issue_environment_resync_packet_for_source(source_slot, session_for_client))
        log_protocol_event(
            'frontend_event_rejected_pending_peer_ack',
            [normalized_event_name],
            ['blocked_command'],
            source_slot,
        )
        log_protocol_send(packets, source_slot)
        return {
            'ok': True,
            'packets': packets,
            'rejected': True,
            'error': 'input blocked: awaiting response from the other client',
            'blocked_command': blocked_pending_command.command,
        }, 200

    normalized_source_slot = _normalize_client_slot(source_slot)
    should_terminate_for_winner_menu = False
    if normalized_event_name == 'winner' and normalized_source_slot in {'p1', 'p2'} and winner_announced:
        with transport_lock:
            winner_main_menu_ack_slots.add(cast(PlayerSlot, normalized_source_slot))
            should_terminate_for_winner_menu = winner_main_menu_ack_slots.issuperset({'p1', 'p2'})

    try:
        bridge_result = frontend_game_bridge.handle_frontend_event(
            event_name,
            response_data if isinstance(response_data, dict) else {},
            context if isinstance(context, dict) else {},
        )
    except BridgeEngineRuntimeError as exc:
        return _handle_bridge_runtime_error(exc, source_slot, session_for_client)
    except Exception as exc:
        return _handle_bridge_runtime_error(exc, source_slot, session_for_client)

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
        _mark_room_finished_once('winner_main_menu_ack')
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
    response, status = _process_protocol_packet(payload, client_slot)
    return _augment_protocol_response_with_pending_peer_ack(response, client_slot), status


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


@app.route('/room/replace-session', methods=['POST', 'OPTIONS'])
def room_replace_session() -> tuple[dict[str, Any], int]:
    if request.method == 'OPTIONS':
        return {'ok': True}, 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {'ok': False, 'error': 'Body must be a JSON object.'}, 400

    old_session_raw = payload.get('old_session_id')
    new_session_raw = payload.get('new_session_id')
    old_session_id = old_session_raw.strip() if isinstance(old_session_raw, str) else ''
    new_session_id = new_session_raw.strip() if isinstance(new_session_raw, str) else ''

    if not old_session_id or not new_session_id:
        return {'ok': False, 'error': 'old_session_id and new_session_id are required.'}, 400

    replaced_slot: PlayerSlot | None = None
    evicted_sid: str | None = None

    global expected_p1_session_id, expected_p2_session_id
    with transport_lock:
        if old_session_id == expected_p1_session_id:
            expected_p1_session_id = new_session_id
            replaced_slot = cast(PlayerSlot, 'p1')
        elif old_session_id == expected_p2_session_id:
            expected_p2_session_id = new_session_id
            replaced_slot = cast(PlayerSlot, 'p2')
        else:
            return {'ok': False, 'error': 'old_session_id not assigned to this room.'}, 404

        # Session takeover intentionally suppresses normal disconnect-forfeit flow.
        _cancel_disconnect_forfeit_timer_locked(replaced_slot)
        _reset_delivery_state_for_slot(replaced_slot)

        sid = transport_state.sid_by_slot[replaced_slot]
        if isinstance(sid, str) and sid:
            evicted_sid = sid
            transport_state.release_sid(sid)

        # Whether the old client was connected or already gone, remove grace-slot
        # reservation so the replacement client can bind this seat immediately.
        transport_state.clear_reserved_slot(replaced_slot)

        registration_condition.notify_all()

    if evicted_sid and socketio is not None:
        socketio.emit('session_replaced', {
            'ok': True,
            'slot': replaced_slot,
            'reason': 'session_superseded',
            'message': 'Signed out: account opened on another client.',
        }, to=evicted_sid)
        if disconnect is not None:
            try:
                disconnect(sid=evicted_sid)
            except Exception:
                pass

    return {
        'ok': True,
        'slot': replaced_slot,
        'evicted': evicted_sid is not None,
    }, 200


def _handle_transport_sid_disconnect(
    sid: str,
    *,
    event_name: str,
) -> None:
    if not isinstance(sid, str) or not sid:
        return

    peer_deliveries: list[tuple[PlayerSlot, str]] = []
    should_terminate_for_winner_menu = False
    released_slot: PlayerSlot | None = None

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
            event_name,
            [],
            ['sid_released', 'grace_window_s', 'pending_replay_count'],
            released_slot,
        )

        if socketio is not None:
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
        _mark_room_finished_once('winner_main_menu_ack_disconnect')
        _schedule_process_termination('both players exited after winner (disconnect path)')


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
            recovered_reconnect_token = _recover_reconnect_token_for_expected_slot(
                expected_slot,
                reconnect_token if isinstance(reconnect_token, str) else None,
            )
            session = transport_state.assign_slot(
                sid=sid,
                requested_slot=requested_slot if isinstance(requested_slot, str) else None,
                reconnect_token=recovered_reconnect_token,
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

            # Always queue environment/init state for connected clients so a
            # lone reconnect lands back in-game view immediately.
            _enqueue_environment_for_connected_clients()
            _enqueue_init_state_for_connected_clients(force=True)
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
            'waiting_for_init': room_stage == 'init',
            'pending_replay_count': len(session.pending_commands),
        })

        # Deliver any immediately available packets to the registering client,
        # including the latest environment snapshot.
        if socketio is not None:
            session_packets = _drain_pending_packets_for_session(session)
            if session_packets:
                socketio.emit(
                    'protocol_packets',
                    _protocol_packets_emit_payload_for_slot(session.slot, session_packets),
                    to=sid,
                )
                log_protocol_send(session_packets, session.slot)

        if both_connected:
            assert socketio is not None
            connected_sids: list[str] = []
            for slot_name in ('p1', 'p2'):
                peer_sid = transport_state.sid_by_slot[slot_name]
                if peer_sid is None:
                    continue
                if peer_sid == sid:
                    continue
                connected_sids.append(peer_sid)
                session_for_slot = transport_state.session_by_sid.get(peer_sid)
                if session_for_slot is None:
                    continue
                peer_packets = _drain_pending_packets_for_session(session_for_slot)
                if not peer_packets:
                    continue
                socketio.emit(
                    'protocol_packets',
                    _protocol_packets_emit_payload_for_slot(slot_name, peer_packets),
                    to=peer_sid,
                )
                log_protocol_send(peer_packets, slot_name)

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
            emit('protocol_error', {
                **response,
                'packet_type': 'ready',
                'status': status,
            })
            return
        packets = response.get('packets', [])
        emit(
            'protocol_packets',
            _protocol_packets_emit_payload_for_slot(client_slot, packets if isinstance(packets, list) else []),
        )


    @socketio.on('request_environment')
    def socket_request_environment(payload: Any) -> None:
        if emit is None:
            return

        data = payload if isinstance(payload, dict) else {}
        sid = _socket_sid()
        with transport_lock:
            client_slot = transport_state.slot_for_sid(sid)

        packet = {
            'ACK': data.get('ACK'),
            'PacketType': 'request_environment',
            'Body': data.get('Body') if isinstance(data.get('Body'), dict) else {},
            'client_id': sid,
        }
        response, status = _process_protocol_packet(packet, client_slot)
        if status != 200:
            emit('protocol_error', {
                **response,
                'packet_type': 'request_environment',
                'status': status,
            })
            return
        packets = response.get('packets', [])
        emit(
            'protocol_packets',
            _protocol_packets_emit_payload_for_slot(client_slot, packets if isinstance(packets, list) else []),
        )


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
            emit('protocol_error', {
                **response,
                'packet_type': 'update_frontend',
                'status': status,
            })
            return
        packets = response.get('packets', [])
        emit(
            'protocol_packets',
            _protocol_packets_emit_payload_for_slot(client_slot, packets if isinstance(packets, list) else []),
        )


    @socketio.on('init_setup_done')
    def socket_init_setup_done(payload: Any) -> None:
        if emit is None:
            return

        data = payload if isinstance(payload, dict) else {}
        sid = _socket_sid()
        with transport_lock:
            client_slot = transport_state.slot_for_sid(sid)

        packet = {
            'ACK': data.get('ACK'),
            'PacketType': 'init_setup_done',
            'Body': data.get('Body') if isinstance(data.get('Body'), dict) else data,
            'client_id': sid,
        }
        response, status = _process_protocol_packet(packet, client_slot)
        if status != 200:
            emit('protocol_error', {
                **response,
                'packet_type': 'init_setup_done',
                'status': status,
            })
            return
        packets = response.get('packets', [])
        emit(
            'protocol_packets',
            _protocol_packets_emit_payload_for_slot(client_slot, packets if isinstance(packets, list) else []),
        )


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
            emit('protocol_error', {
                **response,
                'packet_type': 'frontend_event',
                'status': status,
            })
            return
        packets = response.get('packets', [])
        emit(
            'protocol_packets',
            _protocol_packets_emit_payload_for_slot(client_slot, packets if isinstance(packets, list) else []),
        )


    @socketio.on('client_unloading')
    def socket_client_unloading(_payload: Any) -> None:
        sid = _socket_sid()
        _handle_transport_sid_disconnect(sid, event_name='client_unloading')
        if disconnect is not None:
            try:
                disconnect(sid=sid)
            except Exception:
                pass


    @socketio.on('disconnect')
    def socket_disconnect() -> None:
        sid = _socket_sid()
        _handle_transport_sid_disconnect(sid, event_name='disconnect')


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
