from __future__ import annotations

from ..engine.event import Event, Packet, DeferredEvent
from ..engine.event_listener import *
from typing import TYPE_CHECKING, Callable, TypeVar, cast, Sequence
from ..constants import *

if TYPE_CHECKING:
    from .AVGEEnvironment import AVGEEnvironment


AEV = TypeVar("AEV", bound="AVGEEvent")
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
    def __init__(self, element : Sequence[AEV] | 
                 Sequence[DeferredEvent[AEV]] | 
                 Sequence[AEV | DeferredEvent[AEV]] | 
                 Callable[[], Sequence[AEV | DeferredEvent[AEV]]] | 
                 Callable[[], Sequence[AEV]] | 
                 Callable[[], Sequence[DeferredEvent[AEV]]], identifier : AVGEEngineID):
        if(isinstance(element, Callable)):
            element = cast(Callable[[], Sequence[AEV | DeferredEvent[AEV]]], element)
        super().__init__(element)
        self.identifier = identifier