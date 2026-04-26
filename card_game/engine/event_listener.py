from __future__ import annotations
from card_game.constants import *
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from . import engine
    from . import engine_constants
    from .constrainer import Constraint
    from .event import Event, Packet

EV = TypeVar('EV', bound='Event')
class AbstractPacketListener(Generic[EV]):
    def __init__(self):
        self.engine : engine.Engine[EV] | None = None
        self.attached_packet : Packet[EV] | None = None
        self._invalidated = False
    def packet_match(self, packet : Packet[EV], packet_finish_status : ResponseType) -> bool:
        """
        Function that checks whether the given packet should be attached onto.
        Packet match is called AFTER the packet has COMPLETED, meaning that full_packet will have been fully constructed by then
        """
        raise NotImplementedError()
    def update_status(self):
        """
        Makes the listener evaluate whether it should still be valid. If it shouldn't be, it should call invalidate by itself
        """
        raise NotImplementedError()
    def invalidate(self):
        """
        Invalidates this event listener. Event listeners are considered active until invalidated, after which they are completely dropped out
        """
        self._invalidated = True
    def _should_attach(self, packet : Packet[EV], packet_finish_status : ResponseType):
        return (not self._invalidated) and (self.packet_match(packet, packet_finish_status))
    def react(self, p : Packet[EV]) -> Response:
        raise NotImplementedError()
    def propose(self, e : Packet, priority : int = 0):
        assert self.engine is not None
        self.engine._propose(e, priority)
class AbstractEventListener(Generic[EV]):
    def __init__(self, 
                 group : engine_constants.EngineGroup,
                 requires_runtime_info : bool = True):
        
        self.engine : engine.Engine[EV] | None = None
        self.attached_event : EV | None = None
        self.group = group
        self._invalidated : bool = False
        self.requires_runtime_info : bool = requires_runtime_info
    def event_match(self, event : EV) -> bool:
        """
        Function that checks whether the given event should be attached onto.
        Event match is called before the event has undergone ANY modification
        """
        raise NotImplementedError()
    def event_effect(self) -> bool:
        """
        Function that checks whether, at runtime, the listener should react to its attached event
        """
        if(not self.requires_runtime_info):
            return True
        raise NotImplementedError()
    def attach_to_event(self, e : EV):
        self.attached_event = e
    def detach_from_event(self):
        self.attached_event = None
    def update_status(self):
        """
        Makes the listener evaluate whether it should still be valid. If it shouldn't be, it should call invalidate by itself
        """
        raise NotImplementedError()
    def invalidate(self):
        """
        Invalidates this event listener. Event listeners are considered active until invalidated, after which they are completely dropped out
        """
        self._invalidated = True
    def _should_attach(self, event : EV):
        return (not self._invalidated) and (self.event_match(event))
    def on_packet_completion(self):
        """
        a function that gets called at the end if the attached event's overall pacekt is completed successfully
        particularly useful for 'one-use' event listeners
        """
        return
class ModifierEventListener(AbstractEventListener[EV]):
    def modify(self) -> Response:
        raise NotImplementedError()
class ReactorEventListener(AbstractEventListener[EV]):
    def react(self) -> Response:
        raise NotImplementedError()
    def propose(self, e : Packet, priority : int = 0):
        assert self.engine is not None
        self.engine._propose(e, priority)
class AssessorEventListener(AbstractEventListener[EV]):
    def assess(self) -> Response:
        raise NotImplementedError()

class PostCheckEventListener(AbstractEventListener[EV]):
    def assess(self) -> Response:
        raise NotImplementedError()