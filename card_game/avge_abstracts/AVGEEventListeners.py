from ..engine.event_listener import *
from ..engine.engine_constants import *
from ..engine.event import Event
from typing import Tuple
from enum import StrEnum
from ..abstract.card import Card
from .AVGEEvent import AVGEEvent
from .AVGEEnvironment import AVGEEnvironment


class AVGEEventListenerType(StrEnum):
    ENV = "ENV"
    ATK_1 = 'ATK_1'
    ACTIVE = 'ACTIVE'#an action type for abilities that are phrased like "once per turn, you may..."
    ATK_2 = "ATK_2"
    PASSIVE = "PASSIVE"#an action type exclusively used for stuff like follow-up atks
    NONCHAR = 'NONCHAR'#any non-character card's event listener

type AVGEListenerID = Tuple[Card, AVGEEventListenerType]

class AVGEAbstractEventListener(AbstractEventListener[AVGEListenerID]):
    def __init__(self, 
                 identifier : AVGEListenerID,
                 group : EngineGroup, 
                 internal : bool = False,
                 requires_runtime_info : bool = True):
        super().__init__(identifier,group,internal,requires_runtime_info)
        self.env : AVGEEnvironment = None
    def attach_to_event(self, e : AVGEEvent):
        super().attach_to_event(e)
        self.env : AVGEEnvironment = e.env
    def detach_from_event(self):
        super().detach_from_event()
        self.env = None
    def propose(self, e : Event | list[Event] | Callable[[], Event | list[Event]], priority : int = 0):
        self.env.propose(e, priority)

class AVGEModifier(ModifierEventListener[AVGEListenerID]):
    def __init__(self, 
                 identifier : AVGEListenerID,
                 group : EngineGroup, 
                 internal : bool = False,
                 requires_runtime_info : bool = True):
        super().__init__(identifier,group,internal,requires_runtime_info)
        self.env : AVGEEnvironment = None
    def attach_to_event(self, e : AVGEEvent):
        super().attach_to_event(e)
        self.env : AVGEEnvironment = e.env
    def detach_from_event(self):
        super().detach_from_event()
        self.env = None
    def propose(self, e : Event | list[Event] | Callable[[], Event | list[Event]], priority : int = 0):
        self.env.propose(e, priority)

class AVGEPostcheck(PostCheckEventListener[AVGEListenerID]):
    def __init__(self, 
                 identifier : AVGEListenerID,
                 group : EngineGroup, 
                 internal : bool = False,
                 requires_runtime_info : bool = True):
        super().__init__(identifier,group,internal,requires_runtime_info)
        self.env : AVGEEnvironment = None
    def attach_to_event(self, e : AVGEEvent):
        super().attach_to_event(e)
        self.env : AVGEEnvironment = e.env
    def detach_from_event(self):
        super().detach_from_event()
        self.env = None
    def propose(self, e : Event | list[Event] | Callable[[], Event | list[Event]], priority : int = 0):
        self.env.propose(e, priority)

class AVGEAssessor(AssessorEventListener[AVGEListenerID]):
    def __init__(self, 
                 identifier : AVGEListenerID,
                 group : EngineGroup, 
                 internal : bool = False,
                 requires_runtime_info : bool = True):
        super().__init__(identifier,group,internal,requires_runtime_info)
        self.env : AVGEEnvironment = None
    def attach_to_event(self, e : AVGEEvent):
        super().attach_to_event(e)
        self.env : AVGEEnvironment = e.env
    def detach_from_event(self):
        super().detach_from_event()
        self.env = None
    def propose(self, e : Event | list[Event] | Callable[[], Event | list[Event]], priority : int = 0):
        self.env.propose(e, priority)

class AVGEReactor(ReactorEventListener[AVGEListenerID]):
    def __init__(self, 
                 identifier : AVGEListenerID,
                 group : EngineGroup, 
                 internal : bool = False,
                 requires_runtime_info : bool = True):
        super().__init__(identifier,group,internal,requires_runtime_info)
        self.env : AVGEEnvironment = None
    def attach_to_event(self, e : AVGEEvent):
        super().attach_to_event(e)
        self.env : AVGEEnvironment = e.env
    def detach_from_event(self):
        super().detach_from_event()
        self.env = None
    def propose(self, e : Event | list[Event] | Callable[[], Event | list[Event]], priority : int = 0):
        self.env.propose(e, priority)
