from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.EventCatalog import AVGEEvent
from ..core.AVGEIOManager import ActionRejectedUpdate

if TYPE_CHECKING:
    from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ..engine.event import Event
    from ..engine.engine_io import IOType


def event_to_update_io(event: Event) -> IOType[None] | None:
    '''Use the catalog event's update shape for match-log serialization.'''
    return event.to_update_io() if isinstance(event, AVGEEvent) else None


def action_rejected_update(env: AVGEEnvironment, reason: str | None = None) -> ActionRejectedUpdate:
    '''Built from env.engine.on_packet_failed - sent to whoever's turn it currently is. `reason`
    is whatever the failing regulator left on Packet.rejection_reason (None if it didn't set
    one).'''
    return ActionRejectedUpdate(rejected_for=env.turn, reason=reason)
