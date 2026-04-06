from __future__ import annotations

from ..engine.event_listener import *#type: ignore
from ..engine.engine_constants import *
from typing import TYPE_CHECKING
from enum import StrEnum
from .AVGEEvent import AVGEEvent

if TYPE_CHECKING:
    from .AVGEEvent import AVGEPacket


class ActionTypes(StrEnum):
    ENV = "ENV"
    ATK_1 = 'ATK_1'
    ACTIVE = 'ACTIVE'#an action type for abilities that are phrased like "once per turn, you may..."
    ATK_2 = "ATK_2"
    PASSIVE = "PASSIVE"#an action type exclusively used for stuff like follow-up atks
    NONCHAR = 'NONCHAR'#any non-character card's event listener

class AVGEAbstractEventListener(AbstractEventListener[AVGEEvent]):
    def __init__(self, 
                 identifier : AVGEEngineID,
                 group : EngineGroup, 
                 internal : bool = False,
                 requires_runtime_info : bool = True):
        super().__init__(group,internal,requires_runtime_info)
        self.identifier= identifier

class AVGEModifier(AVGEAbstractEventListener, ModifierEventListener[AVGEEvent]):
    pass

class AVGEPostcheck(AVGEAbstractEventListener, PostCheckEventListener[AVGEEvent]):
    pass

class AVGEAssessor(AVGEAbstractEventListener, AssessorEventListener[AVGEEvent]):
    pass

class AVGEReactor(AVGEAbstractEventListener, ReactorEventListener[AVGEEvent]):
    def propose(self, e : AVGEPacket, priority : int = 0):#type: ignore
        assert self.engine is not None
        self.engine._propose(e, priority)
