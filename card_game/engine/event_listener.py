from __future__ import annotations
from typing import Callable, Self
from . import event
from . import engine
from . import engine_constants
from card_game.constants import *

class AbstractEventListener():
    def __init__(self, group : engine_constants.EngineGroup, 
                 flags : list[engine_constants.Flag] | None = None, 
                 internal : bool = False):
        self.engine : engine.Engine = None
        self.attached_event : event.Event = None 
        if(group is None):
            raise Exception("Listener group needs to be defined!")
        self.group = group
        if(flags is None):
            flags = []
        self.flags = flags
        self.internal = internal
        self.external_validity_constraints : list[Callable[[Self, event.Event], bool]] = []
    
    def add_external_validity_constraint(self, constraint : Callable[[Self, event.Event], bool]):
        self.external_validity_constraints.append(constraint)
    def attach_to_event(self, e : event.Event):
        self.attached_event = e
        self.engine = e.engine

    def is_active(self) -> bool:
        """
        Determines if, according to this event listeners constraints, this event listener should continue being used 
        
        DOES NOT GUARANTEE THAT EVENT LISTENER ABILITY WILL RUN, since there may be external constraints. 
        
        Is_active is also used to test if an event listener believes it should continue to run and be stored in the engine's external listeners
        
        Must be overriden.
        """
        raise NotImplementedError()
    def invalidate(self):
        """
        Invalidates this event listener by forcing is_active to be False
        """
        self.is_active = lambda : False
    def _is_valid_now(self, event : event.Event):
        for constraint in self.external_validity_constraints:
            if(not constraint(self, event)):
                return False
        return self.is_active()
    def make_announcement(self) -> bool:
        raise NotImplementedError()
    def package(self):
        raise NotImplementedError()
    def on_event_completion(self):
        """
        a function that gets called at the end if the attached event is completed successfully
        particularly useful for 'one-use' event listeners
        """
        return
    def generate_response(self, 
                          response_type : ResponseType = ResponseType.ACCEPT,
                          data : Data | None = None) -> Response:
        #Helper function to generate a response packet easier
        if(data is None):
            data = {}
        return Response(self, response_type,data, 
                        self.make_announcement() or response_type==ResponseType.REQUIRES_QUERY)
class ModifierEventListener(AbstractEventListener):
    def __init__(self, group : engine_constants.EngineGroup = None, 
                 flags : list[engine_constants.Flag] | None = None, 
                 internal : bool = False):
        if(internal):
            super().__init__(group, flags, internal)
        else:
            super().__init__(engine_constants.EngineGroup.EXTERNAL_MODIFIERS, flags, internal)
    def modify(self, args : Data | None = None) -> Response:
        raise NotImplementedError()
class ReactorEventListener(AbstractEventListener):
    def __init__(self, group : engine_constants.EngineGroup = None, 
                 flags : list[engine_constants.Flag] | None = None, 
                 internal : bool = False):
        if(internal):
            super().__init__(group, flags, internal)
        else:
            super().__init__(engine_constants.EngineGroup.EXTERNAL_REACTORS, flags, internal)
    def react(self, args : Data | None = None) -> Response:
        raise NotImplementedError()
    def propose(self, e : event.Event | event.EventPacket, priority : int = 0):
        self.engine._propose(e, priority)
class AssessorEventListener(AbstractEventListener):
    def __init__(self, group : engine_constants.EngineGroup, 
                 flags : list[engine_constants.Flag] | None = None, 
                 internal : bool = False):
        super().__init__(group, flags, internal)
    def assess(self, args : Data | None = None) -> Response:
        raise NotImplementedError()
    def inject_event(self, e : event.Event | event.EventPacket, priority : int = 0):
        """ONLY to be used for skip-and-run responses"""
        self.engine._inject_event(e, priority)

class PostCheckEventListener(AbstractEventListener):
    def __init__(self, group : engine_constants.EngineGroup, 
                 flags : list[engine_constants.Flag] | None = None, 
                 internal : bool = False):
        super().__init__(group, flags, internal)
    def assess(self, args : Data | None = None) -> Response:
        raise NotImplementedError()