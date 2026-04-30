from __future__ import annotations

from typing import Any, Callable
from card_game.server.server_types import JsonObject, CommandPayload

from ..models.server_models import ClientSession, MultiplayerTransportState, PlayerSlot


def handle_bridge_runtime_error(
    *,
    exc: Exception,
    source_slot: str | None,
    session_for_client: ClientSession | None,
    enqueue_bridge_commands: Callable[[list[str] | list[JsonObject], str | None], None],
    commands_ready_for_slot: Callable[[str | None, bool, ClientSession | None], list[JsonObject]],
    mark_room_finished_once: Callable[[str], None],
    schedule_process_termination: Callable[[str], None],
    log_protocol_event: Callable[[str, list[str], list[str], str | None], None],
    log_protocol_send: Callable[[list[JsonObject], str | None], None],
) -> tuple[JsonObject, int]:
    print(f'[GAME_RUNNER_ERROR] {exc}')
    log_protocol_event(
        'game_runner_error',
        ['error_message'],
        [],
        source_slot,
    )

    enqueue_bridge_commands(['notify both Game_error -1'], source_slot)
    packets = commands_ready_for_slot(source_slot, is_response=True, session=session_for_client)

    mark_room_finished_once('game_runner_error')
    schedule_process_termination('game runner error')

    log_protocol_send(packets, source_slot)
    return {
        'ok': True,
        'packets': packets,
        'fatal_error': True,
    }, 200


def force_environment_sync_for_connected_clients(
    *,
    socketio: Any,
    transport_lock: Any,
    transport_state: MultiplayerTransportState,
    enqueue_environment_for_connected_clients: Callable[[bool], None],
    issue_backend_packet_for_session: Callable[[ClientSession, str, JsonObject, bool], JsonObject],
    environment_body_for_client: Callable[[str | None], JsonObject],
    protocol_packets_emit_payload_for_slot: Callable[[str | None, list[JsonObject]], JsonObject],
    log_protocol_send: Callable[[list[JsonObject], str | None], None],
) -> None:
    if socketio is None:
        with transport_lock:
            enqueue_environment_for_connected_clients(True)
        return

    deliveries: list[tuple[PlayerSlot, str, JsonObject]] = []
    with transport_lock:
        for slot_name in ('p1', 'p2'):
            slot = slot_name  # literal p1|p2
            sid_for_slot = transport_state.sid_by_slot[slot]
            if sid_for_slot is None:
                continue
            session = transport_state.session_by_sid.get(sid_for_slot)
            if session is None:
                continue
            env_packet = issue_backend_packet_for_session(
                session,
                'environment',
                environment_body_for_client(slot),
                is_response=True,
            )
            session.environment_initialized = True
            deliveries.append((slot, sid_for_slot, env_packet))

    for slot, sid_for_slot, env_packet in deliveries:
        socketio.emit('protocol_packets', protocol_packets_emit_payload_for_slot(slot, [env_packet]), to=sid_for_slot)
        log_protocol_send([env_packet], slot)
