from __future__ import annotations

from copy import deepcopy
from threading import Thread
from time import monotonic
from typing import Any, Callable, cast
from card_game.server.server_types import JsonObject, CommandPayload

from ..models.server_models import ClientSession, MultiplayerTransportState, PlayerSlot


def build_finalized_bridge_from_init_submissions(
    *,
    source_bridge: Any,
    init_setup_submission_by_slot: dict[PlayerSlot, JsonObject | None],
    timeout_seconds: float,
) -> tuple[bool, str | None, Any, JsonObject | None, int, dict[str, JsonObject] | None]:
    p1_submission = init_setup_submission_by_slot['p1']
    p2_submission = init_setup_submission_by_slot['p2']
    if not isinstance(p1_submission, dict) or not isinstance(p2_submission, dict):
        return False, 'both init submissions are required before finalizing', None, None, 0, None

    finalize_target = {
        'p1': deepcopy(p1_submission),
        'p2': deepcopy(p2_submission),
    }
    worker_result: JsonObject = {}

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
    finalize_worker.join(timeout_seconds)
    elapsed_ms = int((monotonic() - started_at) * 1000)

    if finalize_worker.is_alive():
        return (
            False,
            f'init finalize timed out after {timeout_seconds:.1f}s',
            None,
            None,
            elapsed_ms,
            finalize_target,
        )

    finalize_error = worker_result.get('error')
    if isinstance(finalize_error, Exception):
        return (
            False,
            f'failed to finalize init setup: {finalize_error}',
            None,
            None,
            elapsed_ms,
            finalize_target,
        )

    candidate_bridge = worker_result.get('bridge')
    candidate_setup_payload = worker_result.get('setup_payload')
    if not isinstance(candidate_setup_payload, dict):
        return (
            False,
            'failed to finalize init setup: incomplete finalized state',
            None,
            None,
            elapsed_ms,
            finalize_target,
        )

    return True, None, candidate_bridge, candidate_setup_payload, elapsed_ms, finalize_target


def other_slot(slot: PlayerSlot) -> PlayerSlot:
    return cast(PlayerSlot, 'p2') if slot == 'p1' else cast(PlayerSlot, 'p1')


def init_state_body_for_slot(
    slot: PlayerSlot,
    *,
    room_stage: str,
    init_setup_submission_by_slot: dict[PlayerSlot, JsonObject | None],
    transport_state: MultiplayerTransportState,
) -> JsonObject:
    own_ready = init_setup_submission_by_slot[slot] is not None
    opponent_slot = other_slot(slot)
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


def remove_pending_packets_by_type(session: ClientSession, packet_type: str) -> None:
    session.pending_packets = [
        packet
        for packet in session.pending_packets
        if not (isinstance(packet, dict) and packet.get('PacketType') == packet_type)
    ]


def enqueue_init_state_for_connected_clients(
    *,
    force: bool,
    transport_state: MultiplayerTransportState,
    init_setup_submission_by_slot: dict[PlayerSlot, JsonObject | None],
    room_stage: str,
    build_packet_blueprint: Callable[[str, JsonObject, bool], JsonObject],
) -> None:
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
            remove_pending_packets_by_type(session, 'init_state')
        session.pending_packets.append(
            build_packet_blueprint(
                'init_state',
                init_state_body_for_slot(
                    slot,
                    room_stage=room_stage,
                    init_setup_submission_by_slot=init_setup_submission_by_slot,
                    transport_state=transport_state,
                ),
                is_response=True,
            )
        )


def validate_init_setup_submission(
    slot: PlayerSlot,
    body: JsonObject,
    *,
    current_environment_body: Callable[[], JsonObject],
    max_bench_size: int,
) -> tuple[bool, str | None, JsonObject | None]:
    setup = current_environment_body()
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
