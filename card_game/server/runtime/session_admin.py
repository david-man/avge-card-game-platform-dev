from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload
from typing import Callable
from typing import cast

from ..models.server_models import MultiplayerTransportState, PlayerSlot


def replace_room_session(
    payload: JsonObject,
    *,
    transport_lock: Any,
    transport_state: MultiplayerTransportState,
    expected_p1_session_id: str,
    expected_p2_session_id: str,
    cancel_disconnect_forfeit_timer_locked: Callable[[PlayerSlot], None],
    reset_delivery_state_for_slot: Callable[[PlayerSlot], None],
    registration_condition: Any,
) -> tuple[JsonObject, int, str, str, PlayerSlot | None, str | None]:
    old_session_raw = payload.get('old_session_id')
    new_session_raw = payload.get('new_session_id')
    old_session_id = old_session_raw.strip() if isinstance(old_session_raw, str) else ''
    new_session_id = new_session_raw.strip() if isinstance(new_session_raw, str) else ''

    if not old_session_id or not new_session_id:
        return (
            {'ok': False, 'error': 'old_session_id and new_session_id are required.'},
            400,
            expected_p1_session_id,
            expected_p2_session_id,
            None,
            None,
        )

    replaced_slot: PlayerSlot | None = None
    evicted_sid: str | None = None
    next_expected_p1_session_id = expected_p1_session_id
    next_expected_p2_session_id = expected_p2_session_id

    with transport_lock:
        if old_session_id == expected_p1_session_id:
            next_expected_p1_session_id = new_session_id
            replaced_slot = cast(PlayerSlot, 'p1')
        elif old_session_id == expected_p2_session_id:
            next_expected_p2_session_id = new_session_id
            replaced_slot = cast(PlayerSlot, 'p2')
        else:
            return (
                {'ok': False, 'error': 'old_session_id not assigned to this room.'},
                404,
                expected_p1_session_id,
                expected_p2_session_id,
                None,
                None,
            )

        # Session takeover intentionally suppresses normal disconnect-forfeit flow.
        cancel_disconnect_forfeit_timer_locked(replaced_slot)
        reset_delivery_state_for_slot(replaced_slot)

        sid = transport_state.sid_by_slot[replaced_slot]
        if isinstance(sid, str) and sid:
            evicted_sid = sid
            transport_state.release_sid(sid)

        # Whether the old client was connected or already gone, remove grace-slot
        # reservation so the replacement client can bind this seat immediately.
        transport_state.clear_reserved_slot(replaced_slot)

        registration_condition.notify_all()

    response = {
        'ok': True,
        'slot': replaced_slot,
        'evicted': evicted_sid is not None,
    }
    return (
        response,
        200,
        next_expected_p1_session_id,
        next_expected_p2_session_id,
        replaced_slot,
        evicted_sid,
    )
