from __future__ import annotations

from typing import cast

from ..models.server_models import MultiplayerTransportState, PlayerSlot


def expected_slot_for_router_session(
    session_id: str | None,
    *,
    expected_p1_session_id: str,
    expected_p2_session_id: str,
) -> PlayerSlot | None:
    if not isinstance(session_id, str) or not session_id.strip():
        return None
    normalized = session_id.strip()
    if expected_p1_session_id and normalized == expected_p1_session_id:
        return cast(PlayerSlot, 'p1')
    if expected_p2_session_id and normalized == expected_p2_session_id:
        return cast(PlayerSlot, 'p2')
    return None


def recover_reconnect_token_for_expected_slot(
    expected_slot: PlayerSlot | None,
    provided_reconnect_token: str | None,
    *,
    transport_state: MultiplayerTransportState,
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


def short_session_id(session_id: str | None) -> str:
    if not isinstance(session_id, str):
        return '-'
    normalized = session_id.strip()
    if not normalized:
        return '-'
    return normalized[:8]
