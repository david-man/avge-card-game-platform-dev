from __future__ import annotations

from ..engine.event_listener import *#type: ignore
from ..engine.engine_constants import *
from typing import TYPE_CHECKING
from enum import StrEnum
from .AVGEEvent import AVGEEvent

if TYPE_CHECKING:
    from .AVGEEvent import AVGEPacket, DeferredAVGEPacket


class ActionTypes(StrEnum):
    ENV = "ENV"
    ATK_1 = 'ATK_1'
    ACTIVE = 'ACTIVE'#an action type for abilities that are phrased like "once per turn, you may..."
    ATK_2 = "ATK_2"
    PASSIVE = "PASSIVE"#an action type exclusively used for stuff like follow-up atks
    NONCHAR = 'NONCHAR'#any non-character card's event listener

class AVGEPacketListener(AbstractPacketListener[AVGEEvent]):
    def __init__(self, 
                 identifier : AVGEEngineID):
        super().__init__()
        self.identifier= identifier
    def __str__(self):
        return type(self).__name__
    def react(self, p : AVGEPacket) -> Response:#type: ignore
        raise NotImplementedError()
    def packet_match(self, packet : AVGEPacket, packet_finish_status : ResponseType) -> bool:#type: ignore
        """
        Function that checks whether the given packet should be attached onto.
        Packet match is called AFTER the packet has COMPLETED, meaning that full_packet will have been fully constructed by then
        """
        raise NotImplementedError()
class AVGEAbstractEventListener(AbstractEventListener[AVGEEvent]):
    def __init__(self, 
                 identifier : AVGEEngineID,
                 group : EngineGroup,
                 requires_runtime_info : bool = False):
        super().__init__(group,requires_runtime_info)
        self.identifier= identifier
    def __str__(self):
        return type(self).__name__
    def propose(self, e : AVGEPacket, priority : int = 0):#type: ignore
        assert self.engine is not None
        self.engine._propose(e, priority)

class AVGEModifier(AVGEAbstractEventListener, ModifierEventListener[AVGEEvent]):
    pass

class AVGEPostcheck(AVGEAbstractEventListener, PostCheckEventListener[AVGEEvent]):
    pass

class AVGEAssessor(AVGEAbstractEventListener, AssessorEventListener[AVGEEvent]):
    def propose(self, e : AVGEPacket, priority : int = 0):#type: ignore
        assert self.engine is not None
        self.engine._propose(e, priority)

class AVGEReactor(AVGEAbstractEventListener, ReactorEventListener[AVGEEvent]):
    def propose(self, e : AVGEPacket, priority : int = 0):#type: ignore
        assert self.engine is not None
        self.engine._propose(e, priority)
    def extend(self, e : list[AVGEEvent | DeferredAVGEPacket]):
        assert self.engine is not None
        self.engine._extend(e)
    def extend_event(self, e : list[AVGEEvent | DeferredAVGEPacket]):
        assert self.engine is not None
        self.engine._extend_event(e)
