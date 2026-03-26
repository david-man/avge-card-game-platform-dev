from __future__ import annotations
from . import engine
from . import event_listener
from typing import Any
from card_game.constants import *
from . import engine_constants
from . import constrainer

type EventPacket = list[Event]
class Event():
    def __init__(self):
        self.engine : engine.Engine = None
        self.event_listener_groups : dict[engine_constants.EngineGroup, list[event_listener.AbstractEventListener]] = {group : [] for group in engine_constants.EngineGroup}
        self.group_on = engine_constants.EngineGroup.INTERNAL_1
        self.groups_preprocessed : dict[engine_constants.EngineGroup, bool] = {group : False for group in engine_constants.EngineGroup}

        self.core_args : Data = None

        self.generate_internal_listeners()
        for group in self.event_listener_groups.values():
            for listener in group:
                listener.attach_to_event(self)

    
    def make_announcement(self) -> bool:
        #function that decides whether we should make an announcement. 
        raise NotImplementedError()
    def package(self):
        #function that actually packages the event into an announcement
        raise NotImplementedError()
    def _constrain_internal(self, constraint : constrainer.Constraint):
        #checks the internal event listeners with a constrainer
        for group in self.event_listener_groups.values():
            for listener in group:
                if(constraint.match(listener)):
                    listener.invalidate()
    def core_wrapper(self, args : Data | None = None) -> Response:
        if(args is None):
            args = {}
        r = self.core(args)
        if(r.response_type == ResponseType.CORE):
            self.core_args = args
        return r
    
    def core(self, args :Data | None = None) ->Response:
        #you should override this!
        #note that, in place of ACCEPT, you should return CORE 
        raise NotImplementedError()
    def invert_core(self, args : Data | None = None) -> None:
        #this will only be relevant once core() is successfully run
        #args is populated instantaneously
        raise NotImplementedError()

    def generate_internal_listeners(self):
        #you should override this! this function should simply populate the event_listeners_groups
        raise NotImplementedError()
    
    def generate_core_response(self, 
                          response_type : ResponseType =ResponseType.CORE,
                          data :Data | None = None) ->Response:
        #Helper function to generate a response packet for core() easier
        #Announce is true if Requires_Query OR if make_announcement() & CORE
        if(data is None):
            data = {}
        return Response(self, response_type, data, 
                            (self.make_announcement() and response_type==ResponseType.CORE)
                            or (response_type==ResponseType.REQUIRES_QUERY))

    def attach_to_engine(self, engine : engine.Engine):
        self.engine = engine
        #must update current listeners too
        for group in self.event_listener_groups:
            for listener in self.event_listener_groups[group]:
                listener.engine = engine

    def _validate_ordering(self, group : engine_constants.EngineGroup, new_ordering : list[event_listener.AbstractEventListener]) -> bool:
        #validates that the new ordering has all the required elements
        if(len(self.event_listener_groups[group]) == len(new_ordering)):
            for i in new_ordering:
                if(i not in self.event_listener_groups[group]):
                    return False
            return True
        return False
    def attach_listener(self, listener : event_listener.AbstractEventListener) -> bool:
        #attempts to add a listener if its a match. returns True if success
        if(listener._should_attach(self)):
            self.event_listener_groups[listener.group].append(listener)
            listener.attach_to_event(self)
            return True
        return False
    def propose(self, e : Event | EventPacket, priority : int = 0):
        self.engine._propose(e, priority)
    def forward(self, args :Data | None = None) ->Response:
        if(args is None):
            args = {}
        if(self.group_on == engine_constants.EngineGroup.INTERNAL_4 
           and len(self.event_listener_groups[engine_constants.EngineGroup.INTERNAL_4]) == 0):
            #case 1: there's nothing left to run
            return Response(self, ResponseType.FINISHED, {})
        elif(self.group_on == engine_constants.EngineGroup.CORE):
            #case 2: we're running the core function
            response = self.core_wrapper(args)
            if(response.response_type ==ResponseType.CORE):
                #if the response indicates that we can move on
                self.group_on = self.group_on.succ()
            return response
        elif(len(self.event_listener_groups[self.group_on]) == 0):
            #case 3: we're on a group that's not the last and not core,
            #and we're done with the listeners in it
            response = Response(self, ResponseType.ACCEPT, {})
            self.group_on = self.group_on.succ()
            return response
        else:
            #case 4: we have a non-zero length group of listeners to attend to
            
            #step 1: preprocess groups if we haven't
            if(not self.groups_preprocessed[self.group_on]):
                if(self.group_on in [engine_constants.EngineGroup.EXTERNAL_MODIFIERS, engine_constants.EngineGroup.EXTERNAL_REACTORS] 
                     and len(self.event_listener_groups[self.group_on]) >= 2):
                    group_ordering = args.get('group_ordering')
                    if(group_ordering is not None):
                        if(self._validate_ordering(self.group_on, group_ordering)):
                            self.event_listener_groups[self.group_on] = group_ordering
                            self.groups_preprocessed[self.group_on] = True
                            return Response(self, ResponseType.ACCEPT, {})
                    return Response(self, ResponseType.REQUIRES_QUERY,
                                        {"query_type": "ordering", 'unordered_groups': self.event_listener_groups[self.group_on]}, True)
                else:
                    self.groups_preprocessed[self.group_on] = True
                    return Response(self, ResponseType.ACCEPT, {})
            #step 2: question whether to go through with the listener
            next_listener = self.event_listener_groups[self.group_on].pop(0)
            to_run = (not next_listener._invalidated) and bool(next_listener.event_effect())
            for constraint in next_listener.constraints:
                if(not to_run):
                    break
                if(constraint.constrain_listener(next_listener)):
                    to_run = False
            if(not to_run):
                #skip if constrained or invalidated
                return Response(self, ResponseType.ACCEPT)
            else:
                if(isinstance(next_listener, event_listener.AssessorEventListener)):
                    response = next_listener.assess(args)
                elif(isinstance(next_listener, event_listener.PostCheckEventListener)):
                    response = next_listener.assess(args)
                elif(isinstance(next_listener, event_listener.ModifierEventListener)):
                    response = next_listener.modify(args)
                elif(isinstance(next_listener, event_listener.ReactorEventListener)):
                    response = next_listener.react(args)
                
                if(response.response_type ==ResponseType.REQUIRES_QUERY):
                    #if requires query, we need to wait for args next time and try to run the same listener again -- since we used pop, we now need to insert back
                    self.event_listener_groups[self.group_on].insert(0, next_listener)
                return response
        
        