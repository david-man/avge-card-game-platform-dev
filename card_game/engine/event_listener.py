from __future__ import annotations
from . import event
from card_game.constants import *
from typing import TYPE_CHECKING, Callable, Generic, TypeVar

if TYPE_CHECKING:
    from . import engine
    from . import engine_constants
    from .constrainer import Constraint

T = TypeVar('T')
class AbstractEventListener(Generic[T]):
    def __init__(self, 
                 identifier : T,
                 group : engine_constants.EngineGroup, 
                 internal : bool = False,
                 requires_runtime_info : bool = True):
        
        self.engine : engine.Engine = None
        self.attached_event : event.Event = None
        if(group is None):
            raise Exception("Listener group needs to be defined!")
        self.group = group
        self.internal = internal
        self.identifier = identifier
        self._invalidated : bool = False
        self.requires_runtime_info : bool = requires_runtime_info
        
    
    def event_match(self, event : event.Event) -> bool:
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
    def attach_to_event(self, e : event.Event):
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
    def _should_attach(self, event : event.Event):
        #all internal events are valid by default
        return (self.internal) or ((not self._invalidated) and (self.event_match(event)))
    def make_announcement(self) -> bool:
        raise NotImplementedError()
    def package(self):
        raise NotImplementedError()
    def on_packet_completion(self):
        """
        a function that gets called at the end if the attached event's overall pacekt is completed successfully
        particularly useful for 'one-use' event listeners
        """
        return
    def generate_response(self, 
                          response_type : ResponseType = ResponseType.ACCEPT,
                          data : Data = {}) -> Response:
        #Helper function to generate a response packet easier
        return Response(self, response_type,data, 
                        self.make_announcement() or response_type!=ResponseType.ACCEPT)
    
    def generate_interrupt(self, events : list[Event]) -> Response:
        #Helper function to generate an INTERRUPT response easier
        return Response(self, ResponseType.INTERRUPT, {INTERRUPT_KEY: events}, True)
class ModifierEventListener(AbstractEventListener[T], Generic[T]):
    def modify(self, args : Data = None) -> Response:
        if(args is None):
            args = {}
        raise NotImplementedError()
class ReactorEventListener(AbstractEventListener[T], Generic[T]):
    def react(self, args : Data = None) -> Response:
        if(args is None):
            args = {}
        raise NotImplementedError()
    def propose(self, e : event.Event | list[event.Event] | Callable[[], event.Event | list[event.Event]], priority : int = 0):
        self.engine._propose(e, priority)
class AssessorEventListener(AbstractEventListener[T], Generic[T]):
    def assess(self, args : Data = None) -> Response:
        if(args is None):
            args = {}
        raise NotImplementedError()

class PostCheckEventListener(AbstractEventListener[T], Generic[T]):
    def assess(self, args : Data = None) -> Response:
        if(args is None):
            args = {}
        raise NotImplementedError()