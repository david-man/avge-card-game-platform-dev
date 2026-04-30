from __future__ import annotations

from typing import Any
from typing import Callable
from typing import cast

from ..models.server_models import MultiplayerTransportState, PlayerSlot


def handle_transport_sid_disconnect(
    sid: str,
    *,
    event_name: str,
    transport_lock: Any,
    transport_state: MultiplayerTransportState,
    winner_announced: bool,
    winner_main_menu_ack_slots: set[PlayerSlot],
    disconnect_grace_seconds: int,
    socketio: Any,
    reset_delivery_state_for_slot: Callable[[PlayerSlot], None],
    pending_commands_for_slot: Callable[[PlayerSlot], list[str]],
    schedule_disconnect_forfeit_timer_locked: Callable[[PlayerSlot], None],
    schedule_both_disconnected_termination_timer_locked: Callable[[], None],
    mark_room_finished_once: Callable[[str], None],
    schedule_process_termination: Callable[[str], None],
    log_protocol_event: Callable[[str, list[str], list[str], str | None], None],
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
            reset_delivery_state_for_slot(slot)
            replay_commands = pending_commands_for_slot(slot)
            transport_state.set_reserved_pending_commands(slot, replay_commands)
            transport_state.grace_remaining_seconds(slot)
            schedule_disconnect_forfeit_timer_locked(slot)

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

        schedule_both_disconnected_termination_timer_locked()

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
                    'grace_seconds': disconnect_grace_seconds,
                }, to=peer_sid)
                log_protocol_event(
                    'opponent_disconnected',
                    ['slot', 'grace_seconds'],
                    ['peer_sid'],
                    peer_slot,
                )

    if should_terminate_for_winner_menu:
        mark_room_finished_once('winner_main_menu_ack_disconnect')
        schedule_process_termination('both players exited after winner (disconnect path)')
