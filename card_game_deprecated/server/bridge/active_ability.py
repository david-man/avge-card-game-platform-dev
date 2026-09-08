from __future__ import annotations

from typing import Any

from ...avge_abstracts.AVGECards import AVGECharacterCard
from ...avge_abstracts.AVGEEvent import AVGEPacket
from ...constants import ActionTypes, AVGEEngineID
from ...internal_events import AtkPhase, Phase2, PlayCharacterCard


def queue_active_ability_interrupt(
    bridge: Any,
    card: AVGECharacterCard,
    running_event: Any,
    default_timeout: int | None,
) -> list[str]:
    if not isinstance(running_event, (Phase2, AtkPhase)):
        return []

    try:
        if not bool(card.can_play_active()):
            return bridge._notify_for_source_player(card, "Can't play this ability right now!", timeout=default_timeout)
    except Exception:
        return bridge._notify_for_source_player(card, "Can't play this ability right now!", timeout=default_timeout)

    packet_events: list[Any] = [
        PlayCharacterCard(card, ActionTypes.ACTIVATE_ABILITY, ActionTypes.PLAYER_CHOICE, card)
    ]
    packet = AVGEPacket(packet_events, AVGEEngineID(card, ActionTypes.PLAYER_CHOICE, type(card)))
    bridge.env._engine.external_interrupt(packet)
    return []
