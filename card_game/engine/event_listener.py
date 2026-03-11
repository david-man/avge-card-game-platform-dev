from __future__ import annotations
from . import event
from . import engine
from . import engine_constants
from card_game.constants import *

class AbstractEventListener():
    def __init__(self, group : engine_constants.EngineGroup, 
                 flags : list[engine_constants.Flag] = [], 
                 internal : bool = False):
        self.engine : engine.Engine = None
        self.attached_event : event.Event = None 
        if(group is None):
            raise Exception("Listener group needs to be defined!")
        self.group = group
        self.flags = flags
        self.internal = internal
    def is_valid(self) -> bool:
        #determines if this event listener is okay to be used. 
        #for internal listeners, this is just always True
        return True
    def attach_to_event(self, e : event.Event):
        self.attached_event = e
        self.engine = e.engine
    def propose_event(self, e : event.Event, priority : int = 0):
        self.engine._propose_event(e, priority)
    def make_announcement(self) -> bool:
        raise NotImplementedError()
    def package(self):
        raise NotImplementedError()
    def on_event_completion(self):
        #a function that gets called at the end if the attached event is completed successfully
        #particularly useful for 'one-use' event listeners
        return
    def generate_response(self, 
                          response_type : ResponseType,
                          to_expire : bool = False,
                          data : Data = {}) -> Response:
        #Helper function to generate a response packet easier
        return Response(self, to_expire, response_type,data, 
                                         self.make_announcement() or response_type==ResponseType.REQUIRES_QUERY)
class ModifierEventListener(AbstractEventListener):
    def __init__(self, group : engine_constants.EngineGroup = None, 
                 flags : list[engine_constants.Flag] = [], 
                 internal : bool = False):
        if(internal):
            super().__init__(group, flags, internal)
        else:
            super().__init__(engine_constants.EngineGroup.EXTERNAL_MODIFIERS, flags, internal)
    def modify(self, args : Data = {}) -> Response:
        raise NotImplementedError()
class ReactorEventListener(AbstractEventListener):
    def __init__(self, group : engine_constants.EngineGroup = None, 
                 flags : list[engine_constants.Flag] = [], 
                 internal : bool = False):
        if(internal):
            super().__init__(group, flags, internal)
        else:
            super().__init__(engine_constants.EngineGroup.EXTERNAL_REACTORS, flags, internal)
    def react(self, args : Data = {}) -> Response:
        raise NotImplementedError()
    def propose_event(self, e : event.Event, priority : int = 0):
        self.engine._propose_event(e, priority)
class AssessorEventListener(AbstractEventListener):
    def __init__(self, group : engine_constants.EngineGroup = None, 
                 flags : list[engine_constants.Flag] = [], 
                 internal : bool = False):
        super().__init__(group, flags, internal)
    def assess(self, args : Data = {}) -> Response:
        raise NotImplementedError()