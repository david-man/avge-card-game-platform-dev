from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload
from typing import Callable
from typing import cast

from ..models.server_models import ClientSession, MultiplayerTransportState, PlayerSlot


def process_protocol_packet(
    payload: JsonObject,
    client_slot: str | None,
    *,
    protocol_seq: int,
    room_stage_getter: Callable[[], str],
    transport_lock: Any,
    transport_state: MultiplayerTransportState,
    init_setup_submission_by_slot: dict[PlayerSlot, JsonObject | None],
    expected_p1_session_id: str,
    expected_p2_session_id: str,
    winner_announced: bool,
    winner_main_menu_ack_slots: set[PlayerSlot],
    frontend_game_bridge: Any,
    normalize_client_slot: Callable[[Any], str | None],
    extract_client_slot_hint: Callable[[JsonObject], str | None],
    log_protocol_recv: Callable[[int, str, list[str], str | None], None],
    log_protocol_ack_mismatch: Callable[[int, int, str, str | None], None],
    log_protocol_send: Callable[[list[JsonObject], str | None], None],
    log_protocol_update: Callable[[bool, bool, bool, str | None], None],
    log_input_trace: Callable[..., None],
    log_protocol_event: Callable[[str, list[str], list[str], str | None], None],
    issue_backend_packet: Callable[..., JsonObject],
    issue_backend_packet_for_session: Callable[..., JsonObject],
    environment_body_for_client: Callable[[str | None], JsonObject],
    expected_slot_for_router_session: Callable[[str | None], PlayerSlot | None],
    recover_reconnect_token_for_expected_slot: Callable[[PlayerSlot | None, str | None], str | None],
    cancel_disconnect_forfeit_timer_locked: Callable[[PlayerSlot], None],
    mark_player_join_seen_locked: Callable[[], None],
    enqueue_environment_for_connected_clients: Callable[..., None],
    enqueue_init_state_for_connected_clients: Callable[..., None],
    registration_condition: Any,
    short_session_id: Callable[[str | None], str],
    drain_pending_packets_for_session: Callable[[ClientSession], list[JsonObject]],
    validate_init_setup_submission: Callable[[PlayerSlot, JsonObject], tuple[bool, str | None, JsonObject | None]],
    finalize_init_stage_locked: Callable[[], tuple[bool, str | None]],
    emit_pending_packets_to_connected_clients: Callable[..., None],
    other_slot: Callable[[PlayerSlot], PlayerSlot],
    commands_ready_for_slot: Callable[..., list[JsonObject]],
    blocked_pending_command_for_slot: Callable[[str | None], Any],
    issue_environment_resync_packet_for_source: Callable[[str | None, ClientSession | None], JsonObject],
    extract_bridge_commands: Callable[[Any], list[JsonObject]],
    bridge_requests_force_environment_sync: Callable[[Any], bool],
    enqueue_bridge_commands: Callable[[list[JsonObject] | list[str], str | None], None],
    force_environment_sync_for_connected_clients: Callable[[], None],
    acknowledge_head_command: Callable[[str, str | None], tuple[bool, str | None]],
    handle_bridge_runtime_error: Callable[[Exception, str | None, ClientSession | None], tuple[JsonObject, int]],
    emit_ready_commands_to_connected_clients: Callable[[], None],
    emit_pending_peer_ack_status_to_connected_clients: Callable[[], None],
    mark_room_finished_once: Callable[[str], None],
    schedule_process_termination: Callable[[str], None],
    bridge_runtime_error_type: type[Exception],
) -> tuple[JsonObject, int]:

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

    source_slot = normalize_client_slot(client_slot) or sid_slot or extract_client_slot_hint(body)

    log_protocol_recv(ack_raw, packet_type_raw, list(body.keys()), source_slot)

    # Resync path:
    # Multi-client transport cannot validate ACK against a single global SEQ,
    # because clients may receive different packet subsets at different times.
    # Validate ACK monotonicity per client session instead.
    if packet_type_raw != 'register_client':
        if session_for_client is not None:
            if ack_raw < session_for_client.last_ack:
                log_protocol_ack_mismatch(ack_raw, session_for_client.last_ack, packet_type_raw, source_slot)
                mismatch_packet = issue_backend_packet_for_session(
                    session_for_client,
                    'environment',
                    environment_body_for_client(source_slot),
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
            mismatch_packet = issue_backend_packet('environment', environment_body_for_client(source_slot), is_response=True)
            log_protocol_send([mismatch_packet], source_slot)
            return {
                'ok': True,
                'packets': [mismatch_packet],
            }, 200

    packets: list[JsonObject] = []

    if packet_type_raw == 'register_client':
        if client_id is None:
            return {'ok': False, 'error': 'register_client requires client_id.'}, 400

        router_session_id_raw = body.get('session_id')
        router_session_id = router_session_id_raw.strip() if isinstance(router_session_id_raw, str) else None
        requested_slot = normalize_client_slot(body.get('requested_slot')) or normalize_client_slot(client_slot)
        expected_slot = expected_slot_for_router_session(router_session_id)
        if expected_slot is not None:
            requested_slot = expected_slot

        with transport_lock:
            recovered_reconnect_token = recover_reconnect_token_for_expected_slot(
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

            cancel_disconnect_forfeit_timer_locked(session.slot)
            mark_player_join_seen_locked()

            both_connected = transport_state.both_players_connected()
            _ = both_connected

            # Always prime newly connected clients with current state, even if
            # the opponent is still disconnected.
            enqueue_environment_for_connected_clients()
            enqueue_init_state_for_connected_clients(force=True)
            registration_condition.notify_all()

        print(
            '[SLOT_BIND] transport=http '
            f'router_session={short_session_id(router_session_id)} '
            f'requested={requested_slot} expected={expected_slot} assigned={session.slot} '
            f'p1_expected={short_session_id(expected_p1_session_id)} '
            f'p2_expected={short_session_id(expected_p2_session_id)}'
        )

        source_slot = session.slot

        if session.pending_packets:
            packets.extend(drain_pending_packets_for_session(session))
        log_protocol_send(packets, source_slot)
        return {
            'ok': True,
            'packets': packets,
            'client_slot': session.slot,
            'reconnect_token': session.reconnect_token,
            'both_players_connected': True,
            'waiting_for_opponent': False,
            'waiting_for_init': room_stage_getter() == 'init',
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
            if room_stage_getter() != 'init':
                print(
                    '[INIT_SETUP][REJECT] '
                    "reason='already_finalized' "
                    f'slot={slot!r} stage={room_stage_getter()!r}'
                )
                return {'ok': False, 'error': 'Init setup is already finalized.'}, 409

            try:
                ok, error_message, normalized_submission = validate_init_setup_submission(slot, body)
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
            enqueue_init_state_for_connected_clients(force=True)

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
                finalized_ok, finalize_error = finalize_init_stage_locked()
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
                    enqueue_init_state_for_connected_clients(force=True)
                else:
                    finalized_now = True

            if not finalize_failed and session_for_client.pending_packets:
                packets.extend(drain_pending_packets_for_session(session_for_client))

        _ = finalized_now

        if finalize_failed:
            emit_pending_packets_to_connected_clients()
            return {
                'ok': False,
                'error': finalize_error_message or 'failed to finalize init setup',
            }, 500

        # Keep non-submitting peers synchronized with latest init_state/finalization
        # while preserving in-order direct delivery for the submitting slot.
        emit_pending_packets_to_connected_clients(exclude_slots={slot})

        log_protocol_send(packets, source_slot)
        return {
            'ok': True,
            'packets': packets,
            'init_stage': room_stage_getter(),
            'self_ready': init_setup_submission_by_slot[slot] is not None,
            'opponent_ready': init_setup_submission_by_slot[other_slot(slot)] is not None,
        }, 200

    if packet_type_raw == 'request_environment':
        if session_for_client is not None:
            env_packet = issue_backend_packet_for_session(
                session_for_client,
                'environment',
                environment_body_for_client(source_slot),
                is_response=True,
            )
            # Explicit environment refreshes after bootstrap are valid and
            # should not reset bootstrap state or trigger registration loops.
            session_for_client.environment_initialized = True
            packets.append(env_packet)
        else:
            packets.append(
                issue_backend_packet(
                    'environment',
                    environment_body_for_client(source_slot),
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
                packets.extend(drain_pending_packets_for_session(slot_session))

            packets.extend(commands_ready_for_slot(source_slot, is_response=True, session=slot_session))
        log_protocol_send(packets, source_slot)
        return {'ok': True, 'packets': packets}, 200

    if room_stage_getter() == 'init' and packet_type_raw == 'frontend_event':
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
                    packets.extend(drain_pending_packets_for_session(session_for_client))
            log_protocol_send(packets, source_slot)
            return {'ok': True, 'packets': packets}, 200

    if packet_type_raw == 'update_frontend':
        command = body.get('command')
        input_response = body.get('input_response')
        notify_response = body.get('notify_response')

        blocked_pending_command = blocked_pending_command_for_slot(source_slot)
        if blocked_pending_command is not None and (
            isinstance(input_response, dict) or isinstance(notify_response, dict)
        ):
            packets.append(issue_environment_resync_packet_for_source(source_slot, session_for_client))
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
                room_stage=room_stage_getter(),
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
            except bridge_runtime_error_type as exc:
                return handle_bridge_runtime_error(exc, source_slot, session_for_client)
            except Exception as exc:
                return handle_bridge_runtime_error(exc, source_slot, session_for_client)

            bridge_commands = extract_bridge_commands(bridge_result)
            force_sync = bridge_requests_force_environment_sync(bridge_result)
            log_input_trace(
                'server_processed_input_response',
                client_slot=source_slot,
                bridge_commands=bridge_commands,
                force_environment_sync=force_sync,
            )
            enqueue_bridge_commands(bridge_commands, source_slot)
            if force_sync:
                force_environment_sync_for_connected_clients()

        ack_completed = False
        if isinstance(command, str) and command.strip():
            ack_completed, acked_command = acknowledge_head_command(command, source_slot)
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
                except bridge_runtime_error_type as exc:
                    return handle_bridge_runtime_error(exc, source_slot, session_for_client)
                except Exception as exc:
                    return handle_bridge_runtime_error(exc, source_slot, session_for_client)

                enqueue_bridge_commands(extract_bridge_commands(bridge_result), source_slot)
                if bridge_requests_force_environment_sync(bridge_result):
                    force_environment_sync_for_connected_clients()

        packets.extend(commands_ready_for_slot(source_slot, is_response=True, session=session_for_client))
        emit_ready_commands_to_connected_clients()
        if ack_completed:
            emit_pending_peer_ack_status_to_connected_clients()

        log_protocol_send(packets, source_slot)

        return {'ok': True, 'packets': packets}, 200

    event_name = body.get('event_type')
    response_data = body.get('response_data', {})
    context = body.get('context', {})

    if not isinstance(event_name, str) or not event_name.strip():
        return {'ok': False, 'error': 'frontend_event requires event_type.'}, 400

    normalized_event_name = str(event_name).strip().lower().replace('-', '_').replace(' ', '_')
    blocked_pending_command = blocked_pending_command_for_slot(source_slot)
    if blocked_pending_command is not None:
        packets.append(issue_environment_resync_packet_for_source(source_slot, session_for_client))
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

    normalized_source_slot = normalize_client_slot(source_slot)
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
    except bridge_runtime_error_type as exc:
        return handle_bridge_runtime_error(exc, source_slot, session_for_client)
    except Exception as exc:
        return handle_bridge_runtime_error(exc, source_slot, session_for_client)

    enqueue_bridge_commands(extract_bridge_commands(bridge_result), source_slot)
    if bridge_requests_force_environment_sync(bridge_result):
        force_environment_sync_for_connected_clients()
    packets.extend(commands_ready_for_slot(source_slot, is_response=True, session=session_for_client))
    emit_ready_commands_to_connected_clients()
    log_protocol_event(
        event_name,
        list(response_data.keys()) if isinstance(response_data, dict) else [],
        list(context.keys()) if isinstance(context, dict) else [],
        source_slot,
    )
    log_protocol_send(packets, source_slot)

    if should_terminate_for_winner_menu:
        mark_room_finished_once('winner_main_menu_ack')
        schedule_process_termination('both players confirmed main menu after winner')

    return {'ok': True, 'packets': packets}, 200
