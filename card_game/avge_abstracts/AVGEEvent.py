from __future__ import annotations

from ..engine.event import Event, Packet
from ..engine.event_listener import *
from typing import TYPE_CHECKING, Callable, TypeVar, cast
from ..constants import *

if TYPE_CHECKING:
    from .AVGEEnvironment import AVGEEnvironment


AEV = TypeVar("AEV", bound="AVGEEvent")
type DeferredAVGEPacket = Callable[[], list[AVGEEvent | DeferredAVGEPacket]]
class AVGEEvent(Event):
    def __init__(self,
                 catalyst_action : ActionTypes,
                 caller_card : AVGECard | None,
                 **kwargs):
        super().__init__(catalyst_action = catalyst_action, caller_card = caller_card, **kwargs)
        self.caller_card = caller_card
        self.catalyst_action = catalyst_action
        self.identifier = AVGEEngineID(caller_card, catalyst_action, None)
        self.temp_cache = {}
    
class AVGEPacket(Packet[AEV]):
    type AVGEGenerator = Callable[[], list[AEV | AVGEGenerator]]
    def __init__(self, element : list[AEV | AVGEGenerator], identifier : AVGEEngineID):
        super().__init__(element)
        self.identifier = identifier

type PacketType = list[AVGEEvent | DeferredAVGEPacket]