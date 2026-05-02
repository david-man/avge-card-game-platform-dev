from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Condition
from threading import RLock
from threading import Timer
from typing import Any, Literal, cast
from card_game.server.server_types import JsonObject, CommandPayload
import os

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
from .protocol.protocol_command_queue import (
    acknowledge_head_command,
    build_command_packet as command_queue_build_command_packet,
    classify_required_ack_slots,
    commands_ready_for_slot,
    pending_commands_for_slot,
    reset_delivery_state_for_slot,
)
from .protocol.protocol_packets import (
    build_packet_blueprint,
    drain_pending_packets_for_session,
    extract_client_slot_hint,
    issue_backend_packet,
    issue_backend_packet_for_session,
    normalize_client_slot,
    utc_now_iso,
)
from .scanner.scanner_commands import normalize_scanner_command
from .models.server_models import (
    ClientSession,
    MultiplayerTransportState,
    PendingCommandAck,
    PlayerSlot,
)
from .runtime.config import (
    env_csv as runtime_env_csv,
    resolve_init_finalize_timeout_seconds as runtime_resolve_init_finalize_timeout_seconds,
)
from .runtime.init_stage import (
    build_finalized_bridge_from_init_submissions as runtime_build_finalized_bridge_from_init_submissions,
    enqueue_init_state_for_connected_clients as runtime_enqueue_init_state_for_connected_clients,
    init_state_body_for_slot as runtime_init_state_body_for_slot,
    other_slot as runtime_other_slot,
    remove_pending_packets_by_type as runtime_remove_pending_packets_by_type,
    validate_init_setup_submission as runtime_validate_init_setup_submission,
)
from .runtime.session_binding import (
    expected_slot_for_router_session as runtime_expected_slot_for_router_session,
    recover_reconnect_token_for_expected_slot as runtime_recover_reconnect_token_for_expected_slot,
    short_session_id as runtime_short_session_id,
)
from .runtime.lifecycle import (
    mark_room_finished_once as runtime_mark_room_finished_once,
    notify_router_room_finished as runtime_notify_router_room_finished,
    schedule_both_disconnected_termination_if_needed as runtime_schedule_both_disconnected_termination_if_needed,
    schedule_process_termination as runtime_schedule_process_termination,
)
from .runtime.environment_sync import (
    environment_body_for_client as runtime_environment_body_for_client,
    enqueue_environment_for_connected_clients as runtime_enqueue_environment_for_connected_clients,
)
from .runtime.bridge_adapter import (
    extract_bridge_commands as runtime_extract_bridge_commands,
    bridge_requests_force_environment_sync as runtime_bridge_requests_force_environment_sync,
)
from .runtime.packet_dispatch import (
    augment_protocol_response_with_pending_peer_ack as runtime_augment_protocol_response_with_pending_peer_ack,
    blocked_pending_command_for_slot as runtime_blocked_pending_command_for_slot,
    effective_protocol_slot as runtime_effective_protocol_slot,
    emit_pending_packets_to_connected_clients as runtime_emit_pending_packets_to_connected_clients,
    issue_environment_resync_packet_for_source as runtime_issue_environment_resync_packet_for_source,
    protocol_packets_emit_payload_for_slot as runtime_protocol_packets_emit_payload_for_slot,
)
from .runtime.command_flow import (
    emit_pending_peer_ack_status_to_connected_clients as runtime_emit_pending_peer_ack_status_to_connected_clients,
    emit_ready_commands_to_connected_clients as runtime_emit_ready_commands_to_connected_clients,
    enqueue_bridge_commands as runtime_enqueue_bridge_commands,
)
from .runtime.bridge_runtime import (
    force_environment_sync_for_connected_clients as runtime_force_environment_sync_for_connected_clients,
    handle_bridge_runtime_error as runtime_handle_bridge_runtime_error,
)
from .runtime.protocol_service import (
    process_protocol_packet as runtime_process_protocol_packet,
)
from .runtime.transport_disconnect import (
    handle_transport_sid_disconnect as runtime_handle_transport_sid_disconnect,
)
from .runtime.session_admin import (
    replace_room_session as runtime_replace_room_session,
)
from .runtime.socket_transport import (
    emit_server_connected as runtime_emit_server_connected,
    handle_client_unloading as runtime_handle_client_unloading,
    handle_disconnect as runtime_handle_disconnect,
    handle_protocol_socket_event as runtime_handle_protocol_socket_event,
    register_client_or_play as runtime_register_client_or_play,
)
from .runtime.http_api import (
    apply_cors_headers as runtime_apply_cors_headers,
    handle_protocol_http as runtime_handle_protocol_http,
    handle_scanner_input_http as runtime_handle_scanner_input_http,
    health_response as runtime_health_response,
)

app = Flask(__name__)
frontend_game_bridge = FrontendGameBridge()
entity_setup_payload: JsonObject = frontend_game_bridge.get_setup_payload()
protocol_seq = 0
DISCONNECT_GRACE_SECONDS = 5


def _resolve_init_finalize_timeout_seconds() -> float:
    return runtime_resolve_init_finalize_timeout_seconds()


INIT_FINALIZE_TIMEOUT_SECONDS = _resolve_init_finalize_timeout_seconds()

room_stage: str = 'init'
init_setup_submission_by_slot: dict[PlayerSlot, JsonObject | None] = {
    'p1': None,
    'p2': None,
}


def _env_csv(name: str) -> list[str]:
    return runtime_env_csv(name)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


type SocketIOAsyncMode = Literal['threading', 'eventlet', 'gevent', 'gevent_uwsgi']


def _env_socketio_async_mode(name: str, default: SocketIOAsyncMode) -> SocketIOAsyncMode:
    raw = os.getenv(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in {'threading', 'eventlet', 'gevent', 'gevent_uwsgi'}:
        return cast(SocketIOAsyncMode, normalized)
    return default


ROUTER_ALLOWED_ORIGINS = _env_csv('ROUTER_ALLOWED_ORIGINS')
ROUTER_SOCKETIO_ASYNC_MODE = _env_socketio_async_mode('ROUTER_SOCKETIO_ASYNC_MODE', 'gevent')
ROUTER_DEBUG = _env_bool('ROUTER_DEBUG', False)
ROUTER_USE_RELOADER = _env_bool('ROUTER_USE_RELOADER', False)


SERVER_ALLOWED_ORIGINS = _env_csv('SERVER_ALLOWED_ORIGINS')
if not SERVER_ALLOWED_ORIGINS:
    SERVER_ALLOWED_ORIGINS = ROUTER_ALLOWED_ORIGINS
SERVER_SOCKETIO_ASYNC_MODE = _env_socketio_async_mode('SERVER_SOCKETIO_ASYNC_MODE', ROUTER_SOCKETIO_ASYNC_MODE)
SERVER_DEBUG = _env_bool('SERVER_DEBUG', ROUTER_DEBUG)
SERVER_USE_RELOADER = _env_bool('SERVER_USE_RELOADER', ROUTER_USE_RELOADER)


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
    return runtime_expected_slot_for_router_session(
        session_id,
        expected_p1_session_id=expected_p1_session_id,
        expected_p2_session_id=expected_p2_session_id,
    )


def _recover_reconnect_token_for_expected_slot(
    expected_slot: PlayerSlot | None,
    provided_reconnect_token: str | None,
) -> str | None:
    return runtime_recover_reconnect_token_for_expected_slot(
        expected_slot,
        provided_reconnect_token,
        transport_state=transport_state,
    )


def _short_session_id(session_id: str | None) -> str:
    return runtime_short_session_id(session_id)


def _schedule_process_termination(reason: str) -> None:
    global termination_requested
    termination_requested = runtime_schedule_process_termination(
        termination_requested=termination_requested,
        on_scheduled=lambda: log_protocol_event(
            'server_termination_scheduled',
            ['reason'],
            [],
            None,
        ),
        terminate_process=lambda: os._exit(0),
    )


def _notify_router_room_finished(reason: str) -> None:
    runtime_notify_router_room_finished(
        router_base_url=router_base_url,
        room_id_from_env=room_id_from_env,
        reason=reason,
    )


def _mark_room_finished_once(reason: str) -> None:
    global room_finished_notified
    room_finished_notified = runtime_mark_room_finished_once(
        room_finished_notified=room_finished_notified,
        reason=reason,
        notify_callback=_notify_router_room_finished,
    )


def _schedule_both_disconnected_termination_timer_locked() -> None:
    runtime_schedule_both_disconnected_termination_if_needed(
        first_player_join_seen=first_player_join_seen,
        termination_requested=termination_requested,
        sid_by_slot={
            'p1': transport_state.sid_by_slot['p1'],
            'p2': transport_state.sid_by_slot['p2'],
        },
        mark_room_finished_once=_mark_room_finished_once,
        schedule_process_termination=_schedule_process_termination,
    )


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
    socketio_origins: str | list[str] = '*'
    if SERVER_ALLOWED_ORIGINS and '*' not in SERVER_ALLOWED_ORIGINS:
        socketio_origins = SERVER_ALLOWED_ORIGINS
    socketio = SocketIO(
        app,
        cors_allowed_origins=socketio_origins,
        async_mode=SERVER_SOCKETIO_ASYNC_MODE,
    )


def _utc_now_iso() -> str:
    return utc_now_iso()


def _normalize_client_slot(raw_slot: Any) -> str | None:
    return normalize_client_slot(raw_slot)


def _extract_client_slot_hint(body: JsonObject) -> str | None:
    return extract_client_slot_hint(body, normalize_slot=_normalize_client_slot)


def _socket_sid() -> str:
    raw_sid = getattr(request, 'sid', None)
    return raw_sid if isinstance(raw_sid, str) else ''


def _issue_backend_packet(packet_type: str, body: JsonObject, is_response: bool) -> JsonObject:
    global protocol_seq
    packet, protocol_seq = issue_backend_packet(protocol_seq, packet_type, body, is_response)
    return packet


def _issue_backend_packet_for_session(
    session: ClientSession,
    packet_type: str,
    body: JsonObject,
    is_response: bool,
) -> JsonObject:
    return issue_backend_packet_for_session(session, packet_type, body, is_response)


def _build_packet_blueprint(packet_type: str, body: JsonObject, is_response: bool) -> JsonObject:
    return build_packet_blueprint(packet_type, body, is_response)


def _drain_pending_packets_for_session(session: ClientSession) -> list[JsonObject]:
    return drain_pending_packets_for_session(
        session,
        issue_packet_for_session=_issue_backend_packet_for_session,
    )


def _current_environment_body() -> JsonObject:
    return deepcopy(entity_setup_payload) if isinstance(entity_setup_payload, dict) else {}


def _environment_body_for_client(client_slot: str | None) -> JsonObject:
    return runtime_environment_body_for_client(
        client_slot,
        current_environment_body=_current_environment_body,
        normalize_client_slot=_normalize_client_slot,
    )


def _other_slot(slot: PlayerSlot) -> PlayerSlot:
    return runtime_other_slot(slot)


def _init_state_body_for_slot(slot: PlayerSlot) -> JsonObject:
    return runtime_init_state_body_for_slot(
        slot,
        room_stage=room_stage,
        init_setup_submission_by_slot=init_setup_submission_by_slot,
        transport_state=transport_state,
    )


def _remove_pending_packets_by_type(session: ClientSession, packet_type: str) -> None:
    runtime_remove_pending_packets_by_type(session, packet_type)


def _enqueue_init_state_for_connected_clients(force: bool = False) -> None:
    runtime_enqueue_init_state_for_connected_clients(
        force=force,
        transport_state=transport_state,
        init_setup_submission_by_slot=init_setup_submission_by_slot,
        room_stage=room_stage,
        build_packet_blueprint=_build_packet_blueprint,
    )


def _validate_init_setup_submission(
    slot: PlayerSlot,
    body: JsonObject,
) -> tuple[bool, str | None, JsonObject | None]:
    return runtime_validate_init_setup_submission(
        slot,
        body,
        current_environment_body=_current_environment_body,
        max_bench_size=max_bench_size,
    )


def _finalize_init_stage_locked() -> tuple[bool, str | None]:
    global frontend_game_bridge, entity_setup_payload, room_stage, pending_command_acks, next_command_id
    (
        finalized_ok,
        finalize_error,
        candidate_bridge,
        candidate_setup_payload,
        elapsed_ms,
        finalize_target,
    ) = runtime_build_finalized_bridge_from_init_submissions(
        source_bridge=frontend_game_bridge,
        init_setup_submission_by_slot=init_setup_submission_by_slot,
        timeout_seconds=INIT_FINALIZE_TIMEOUT_SECONDS,
    )
    if not finalized_ok:
        return False, finalize_error or 'failed to finalize init setup'

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
    finalize_target_payload = finalize_target if isinstance(finalize_target, dict) else {'p1': {}, 'p2': {}}
    print(
        '[INIT_SETUP][FINALIZE_OK] '
        f'elapsed_ms={elapsed_ms} '
        f"p1_active={finalize_target_payload['p1'].get('active_card_id')!r} "
        f"p2_active={finalize_target_payload['p2'].get('active_card_id')!r}"
    )
    return True, None


def _enqueue_environment_for_connected_clients(force: bool = False) -> None:
    runtime_enqueue_environment_for_connected_clients(
        force=force,
        transport_state=transport_state,
        remove_pending_packets_by_type=_remove_pending_packets_by_type,
        build_packet_blueprint=_build_packet_blueprint,
        environment_body_for_slot=_environment_body_for_client,
    )


def _emit_pending_packets_to_connected_clients(exclude_slots: set[PlayerSlot] | None = None) -> None:
    runtime_emit_pending_packets_to_connected_clients(
        socketio=socketio,
        transport_lock=transport_lock,
        transport_state=transport_state,
        drain_pending_packets_for_session=_drain_pending_packets_for_session,
        protocol_packets_emit_payload_for_slot=_protocol_packets_emit_payload_for_slot,
        log_protocol_send=log_protocol_send,
        exclude_slots=exclude_slots,
    )


def _extract_bridge_commands(bridge_result: JsonObject) -> list[JsonObject]:
    global entity_setup_payload
    extracted, next_setup = runtime_extract_bridge_commands(bridge_result)
    if isinstance(next_setup, dict):
        entity_setup_payload = next_setup
    return extracted


def _bridge_requests_force_environment_sync(bridge_result: JsonObject) -> bool:
    return runtime_bridge_requests_force_environment_sync(bridge_result)


def _handle_bridge_runtime_error(
    exc: Exception,
    source_slot: str | None,
    session_for_client: ClientSession | None,
) -> tuple[JsonObject, int]:
    return runtime_handle_bridge_runtime_error(
        exc=exc,
        source_slot=source_slot,
        session_for_client=session_for_client,
        enqueue_bridge_commands=_enqueue_bridge_commands,
        commands_ready_for_slot=_commands_ready_for_slot,
        mark_room_finished_once=_mark_room_finished_once,
        schedule_process_termination=_schedule_process_termination,
        log_protocol_event=log_protocol_event,
        log_protocol_send=log_protocol_send,
    )


def _force_environment_sync_for_connected_clients() -> None:
    runtime_force_environment_sync_for_connected_clients(
        socketio=socketio,
        transport_lock=transport_lock,
        transport_state=transport_state,
        enqueue_environment_for_connected_clients=_enqueue_environment_for_connected_clients,
        issue_backend_packet_for_session=_issue_backend_packet_for_session,
        environment_body_for_client=_environment_body_for_client,
        protocol_packets_emit_payload_for_slot=_protocol_packets_emit_payload_for_slot,
        log_protocol_send=log_protocol_send,
    )

def _classify_required_ack_slots(command: str, source_slot: str | None) -> set[PlayerSlot]:
    return classify_required_ack_slots(
        command,
        source_slot,
        transport_state,
        _normalize_client_slot,
    )


def _blocked_pending_command_for_slot(source_slot: str | None) -> PendingCommandAck | None:
    return runtime_blocked_pending_command_for_slot(
        source_slot,
        pending_command_acks=pending_command_acks,
        normalize_client_slot=_normalize_client_slot,
    )


def _effective_protocol_slot(source_slot: str | None, response: JsonObject | None = None) -> PlayerSlot | None:
    return runtime_effective_protocol_slot(
        source_slot,
        response,
        normalize_client_slot=_normalize_client_slot,
    )


def _augment_protocol_response_with_pending_peer_ack(
    response: JsonObject,
    source_slot: str | None,
) -> JsonObject:
    return runtime_augment_protocol_response_with_pending_peer_ack(
        response,
        source_slot,
        effective_protocol_slot=_effective_protocol_slot,
        blocked_pending_command_for_slot=_blocked_pending_command_for_slot,
    )


def _protocol_packets_emit_payload_for_slot(slot: str | None, packets: list[JsonObject]) -> JsonObject:
    return runtime_protocol_packets_emit_payload_for_slot(
        slot,
        packets,
        blocked_pending_command_for_slot=_blocked_pending_command_for_slot,
    )


def _issue_environment_resync_packet_for_source(
    source_slot: str | None,
    session_for_client: ClientSession | None,
) -> JsonObject:
    return runtime_issue_environment_resync_packet_for_source(
        source_slot,
        session_for_client,
        environment_body_for_client=_environment_body_for_client,
        issue_backend_packet=_issue_backend_packet,
        issue_backend_packet_for_session=_issue_backend_packet_for_session,
    )


def _enqueue_bridge_commands(commands: list[str] | list[JsonObject], source_slot: str | None) -> None:
    global next_command_id, winner_announced, winner_main_menu_ack_slots
    (
        next_command_id,
        winner_announced,
        winner_main_menu_ack_slots,
    ) = runtime_enqueue_bridge_commands(
        commands,
        source_slot,
        next_command_id=next_command_id,
        winner_announced=winner_announced,
        winner_main_menu_ack_slots=winner_main_menu_ack_slots,
        pending_command_acks=pending_command_acks,
        pending_command_ack_factory=PendingCommandAck,
        classify_required_ack_slots=_classify_required_ack_slots,
        mark_room_finished_once=_mark_room_finished_once,
        transport_lock=transport_lock,
        registration_condition=registration_condition,
        emit_ready_commands_to_connected_clients=_emit_ready_commands_to_connected_clients,
        emit_pending_peer_ack_status_to_connected_clients=_emit_pending_peer_ack_status_to_connected_clients,
    )


def _emit_ready_commands_to_connected_clients() -> None:
    runtime_emit_ready_commands_to_connected_clients(
        socketio=socketio,
        transport_lock=transport_lock,
        transport_state=transport_state,
        commands_ready_for_slot=_commands_ready_for_slot,
        protocol_packets_emit_payload_for_slot=_protocol_packets_emit_payload_for_slot,
        log_protocol_send=log_protocol_send,
    )


def _emit_pending_peer_ack_status_to_connected_clients() -> None:
    runtime_emit_pending_peer_ack_status_to_connected_clients(
        socketio=socketio,
        transport_lock=transport_lock,
        transport_state=transport_state,
        protocol_packets_emit_payload_for_slot=_protocol_packets_emit_payload_for_slot,
        log_protocol_send=log_protocol_send,
    )


def _build_command_packet(
    pending: PendingCommandAck,
    is_response: bool,
    session: ClientSession | None,
) -> JsonObject:
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
) -> list[JsonObject]:
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


def _process_protocol_packet(payload: JsonObject, client_slot: str | None) -> tuple[JsonObject, int]:
    return runtime_process_protocol_packet(
        payload,
        client_slot,
        protocol_seq=protocol_seq,
        room_stage_getter=lambda: room_stage,
        transport_lock=transport_lock,
        transport_state=transport_state,
        init_setup_submission_by_slot=init_setup_submission_by_slot,
        expected_p1_session_id=expected_p1_session_id,
        expected_p2_session_id=expected_p2_session_id,
        winner_announced=winner_announced,
        winner_main_menu_ack_slots=winner_main_menu_ack_slots,
        frontend_game_bridge=frontend_game_bridge,
        normalize_client_slot=_normalize_client_slot,
        extract_client_slot_hint=_extract_client_slot_hint,
        log_protocol_recv=log_protocol_recv,
        log_protocol_ack_mismatch=log_protocol_ack_mismatch,
        log_protocol_send=log_protocol_send,
        log_protocol_update=log_protocol_update,
        log_input_trace=log_input_trace,
        log_protocol_event=log_protocol_event,
        issue_backend_packet=_issue_backend_packet,
        issue_backend_packet_for_session=_issue_backend_packet_for_session,
        environment_body_for_client=_environment_body_for_client,
        expected_slot_for_router_session=_expected_slot_for_router_session,
        recover_reconnect_token_for_expected_slot=_recover_reconnect_token_for_expected_slot,
        cancel_disconnect_forfeit_timer_locked=_cancel_disconnect_forfeit_timer_locked,
        mark_player_join_seen_locked=_mark_player_join_seen_locked,
        enqueue_environment_for_connected_clients=_enqueue_environment_for_connected_clients,
        enqueue_init_state_for_connected_clients=_enqueue_init_state_for_connected_clients,
        registration_condition=registration_condition,
        short_session_id=_short_session_id,
        drain_pending_packets_for_session=_drain_pending_packets_for_session,
        validate_init_setup_submission=_validate_init_setup_submission,
        finalize_init_stage_locked=_finalize_init_stage_locked,
        emit_pending_packets_to_connected_clients=_emit_pending_packets_to_connected_clients,
        other_slot=_other_slot,
        commands_ready_for_slot=_commands_ready_for_slot,
        blocked_pending_command_for_slot=_blocked_pending_command_for_slot,
        issue_environment_resync_packet_for_source=_issue_environment_resync_packet_for_source,
        extract_bridge_commands=_extract_bridge_commands,
        bridge_requests_force_environment_sync=_bridge_requests_force_environment_sync,
        enqueue_bridge_commands=_enqueue_bridge_commands,
        force_environment_sync_for_connected_clients=_force_environment_sync_for_connected_clients,
        acknowledge_head_command=_acknowledge_head_command,
        handle_bridge_runtime_error=_handle_bridge_runtime_error,
        emit_ready_commands_to_connected_clients=_emit_ready_commands_to_connected_clients,
        emit_pending_peer_ack_status_to_connected_clients=_emit_pending_peer_ack_status_to_connected_clients,
        mark_room_finished_once=_mark_room_finished_once,
        schedule_process_termination=_schedule_process_termination,
        bridge_runtime_error_type=BridgeEngineRuntimeError,
    )


@app.after_request
def add_cors_headers(response):
    return runtime_apply_cors_headers(
        response,
        request_origin=request.headers.get('Origin'),
        allowed_origins=SERVER_ALLOWED_ORIGINS,
    )


@app.get('/health')
def health() -> tuple[dict[str, str], int]:
    return runtime_health_response(utc_now_iso=_utc_now_iso)


@app.route('/protocol', methods=['POST', 'OPTIONS'])
def protocol() -> tuple[JsonObject, int]:
    return runtime_handle_protocol_http(
        method=request.method,
        payload=request.get_json(silent=True),
        normalize_client_slot=_normalize_client_slot,
        process_protocol_packet=_process_protocol_packet,
        augment_protocol_response_with_pending_peer_ack=_augment_protocol_response_with_pending_peer_ack,
    )


@app.route('/scanner/input', methods=['POST', 'OPTIONS'])
def scanner_input() -> tuple[JsonObject, int]:
    return runtime_handle_scanner_input_http(
        method=request.method,
        payload=request.get_json(silent=True),
        normalize_scanner_command=normalize_scanner_command,
        enqueue_bridge_commands=_enqueue_bridge_commands,
        transport_lock=transport_lock,
        transport_state=transport_state,
        log_protocol_event=log_protocol_event,
    )


@app.route('/room/replace-session', methods=['POST', 'OPTIONS'])
def room_replace_session() -> tuple[JsonObject, int]:
    if request.method == 'OPTIONS':
        return {'ok': True}, 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {'ok': False, 'error': 'Body must be a JSON object.'}, 400

    global expected_p1_session_id, expected_p2_session_id
    (
        response,
        status,
        expected_p1_session_id,
        expected_p2_session_id,
        replaced_slot,
        evicted_sid,
    ) = runtime_replace_room_session(
        payload,
        transport_lock=transport_lock,
        transport_state=transport_state,
        expected_p1_session_id=expected_p1_session_id,
        expected_p2_session_id=expected_p2_session_id,
        cancel_disconnect_forfeit_timer_locked=_cancel_disconnect_forfeit_timer_locked,
        reset_delivery_state_for_slot=_reset_delivery_state_for_slot,
        registration_condition=registration_condition,
    )

    if status != 200:
        return response, status

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

    return response, status


def _handle_transport_sid_disconnect(
    sid: str,
    *,
    event_name: str,
) -> None:
    runtime_handle_transport_sid_disconnect(
        sid,
        event_name=event_name,
        transport_lock=transport_lock,
        transport_state=transport_state,
        winner_announced=winner_announced,
        winner_main_menu_ack_slots=winner_main_menu_ack_slots,
        disconnect_grace_seconds=DISCONNECT_GRACE_SECONDS,
        socketio=socketio,
        reset_delivery_state_for_slot=_reset_delivery_state_for_slot,
        pending_commands_for_slot=_pending_commands_for_slot,
        schedule_disconnect_forfeit_timer_locked=_schedule_disconnect_forfeit_timer_locked,
        schedule_both_disconnected_termination_timer_locked=_schedule_both_disconnected_termination_timer_locked,
        mark_room_finished_once=_mark_room_finished_once,
        schedule_process_termination=_schedule_process_termination,
        log_protocol_event=log_protocol_event,
    )


if socketio is not None:
    @socketio.on('connect')
    def socket_connect() -> None:
        runtime_emit_server_connected(emit_fn=emit)


    @socketio.on('register_client_or_play')
    def socket_register_client_or_play(payload: Any) -> None:
        sid = _socket_sid()
        runtime_register_client_or_play(
            payload,
            sid=sid,
            transport_lock=transport_lock,
            transport_state=transport_state,
            expected_p1_session_id=expected_p1_session_id,
            expected_p2_session_id=expected_p2_session_id,
            room_stage=room_stage,
            socketio=socketio,
            emit_fn=emit,
            expected_slot_for_router_session=_expected_slot_for_router_session,
            recover_reconnect_token_for_expected_slot=_recover_reconnect_token_for_expected_slot,
            cancel_disconnect_forfeit_timer_locked=_cancel_disconnect_forfeit_timer_locked,
            mark_player_join_seen_locked=_mark_player_join_seen_locked,
            enqueue_environment_for_connected_clients=_enqueue_environment_for_connected_clients,
            enqueue_init_state_for_connected_clients=_enqueue_init_state_for_connected_clients,
            registration_condition=registration_condition,
            short_session_id=_short_session_id,
            drain_pending_packets_for_session=_drain_pending_packets_for_session,
            protocol_packets_emit_payload_for_slot=_protocol_packets_emit_payload_for_slot,
            log_protocol_send=log_protocol_send,
        )


    @socketio.on('ready')
    def socket_ready(payload: Any) -> None:
        sid = _socket_sid()
        runtime_handle_protocol_socket_event(
            payload,
            sid=sid,
            packet_type='ready',
            allow_body_data_fallback=False,
            transport_lock=transport_lock,
            transport_state=transport_state,
            process_protocol_packet=_process_protocol_packet,
            protocol_packets_emit_payload_for_slot=_protocol_packets_emit_payload_for_slot,
            emit_fn=emit,
        )


    @socketio.on('request_environment')
    def socket_request_environment(payload: Any) -> None:
        sid = _socket_sid()
        runtime_handle_protocol_socket_event(
            payload,
            sid=sid,
            packet_type='request_environment',
            allow_body_data_fallback=False,
            transport_lock=transport_lock,
            transport_state=transport_state,
            process_protocol_packet=_process_protocol_packet,
            protocol_packets_emit_payload_for_slot=_protocol_packets_emit_payload_for_slot,
            emit_fn=emit,
        )


    @socketio.on('update_frontend')
    def socket_update_frontend(payload: Any) -> None:
        sid = _socket_sid()
        runtime_handle_protocol_socket_event(
            payload,
            sid=sid,
            packet_type='update_frontend',
            allow_body_data_fallback=True,
            transport_lock=transport_lock,
            transport_state=transport_state,
            process_protocol_packet=_process_protocol_packet,
            protocol_packets_emit_payload_for_slot=_protocol_packets_emit_payload_for_slot,
            emit_fn=emit,
        )


    @socketio.on('init_setup_done')
    def socket_init_setup_done(payload: Any) -> None:
        sid = _socket_sid()
        runtime_handle_protocol_socket_event(
            payload,
            sid=sid,
            packet_type='init_setup_done',
            allow_body_data_fallback=True,
            transport_lock=transport_lock,
            transport_state=transport_state,
            process_protocol_packet=_process_protocol_packet,
            protocol_packets_emit_payload_for_slot=_protocol_packets_emit_payload_for_slot,
            emit_fn=emit,
        )


    @socketio.on('frontend_event')
    def socket_frontend_event(payload: Any) -> None:
        sid = _socket_sid()
        runtime_handle_protocol_socket_event(
            payload,
            sid=sid,
            packet_type='frontend_event',
            allow_body_data_fallback=True,
            transport_lock=transport_lock,
            transport_state=transport_state,
            process_protocol_packet=_process_protocol_packet,
            protocol_packets_emit_payload_for_slot=_protocol_packets_emit_payload_for_slot,
            emit_fn=emit,
        )


    @socketio.on('client_unloading')
    def socket_client_unloading(_payload: Any) -> None:
        sid = _socket_sid()
        runtime_handle_client_unloading(
            sid=sid,
            handle_transport_sid_disconnect=lambda value: _handle_transport_sid_disconnect(value, event_name='client_unloading'),
            disconnect_fn=disconnect,
        )


    @socketio.on('disconnect')
    def socket_disconnect() -> None:
        sid = _socket_sid()
        runtime_handle_disconnect(
            sid=sid,
            handle_transport_sid_disconnect=lambda value: _handle_transport_sid_disconnect(value, event_name='disconnect'),
        )


if __name__ == '__main__':
    server_host = os.getenv('SERVER_HOST', '0.0.0.0')
    server_port = int(os.getenv('SERVER_PORT', '5500'))
    server_debug = SERVER_DEBUG
    server_use_reloader = SERVER_USE_RELOADER
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
