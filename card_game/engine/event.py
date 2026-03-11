from __future__ import annotations
from . import engine
from . import event_listener
from typing import Any
from card_game.constants import *
from . import engine_constants
class Event():
    def __init__(self, flags : list[engine_constants.Flag]):
        self.flags = flags
        self.engine : engine.Engine = None
        self.event_listener_groups : dict[engine_constants.EngineGroup, list[event_listener.AbstractEventListener]] = {group : [] for group in engine_constants.EngineGroup}
        self.group_on = engine_constants.EngineGroup.INTERNAL_1
        self.external_modifiers_ordered = False
        self.external_reactors_ordered = False

        self.generate_internal_listeners()

    
    def make_announcement(self) -> bool:
        #function that decides whether we should make an announcement. 
        raise NotImplementedError()
    def package(self):
        #function that actually packages the event into an announcement
        return NotImplementedError()
    
    def core(self, args :Data = {}) ->Response:
        #you should override this!
        #note that, in place of ACCEPT, you should return CORE 
        raise NotImplementedError()

    def generate_internal_listeners(self):
        #you should override this!
        raise NotImplementedError()
    
    def generate_response(self, 
                          response_type :ResponseType =ResponseType.CORE,
                          data :Data = {}) ->Response:
        #Helper function to generate a response packet easier
        #Announcements only happen on Query or Core
        return Response(self, False, response_type, data, 
                                         (self.make_announcement() and response_type==ResponseType.CORE)
                                         or (response_type==ResponseType.REQUIRES_QUERY))

    def attach_to_engine(self, engine : engine.Engine):
        self.engine = engine
        #must update current listeners too
        for group in self.event_listener_groups:
            for listener in self.event_listener_groups[group]:
                listener.engine = engine

    def _check_listener(self, listener : event_listener.AbstractEventListener) -> bool:
        if(listener.flags == []):
            return True
        else:
            if(len(self.flags) == len(listener.flags)):
                for flag in self.flags:
                    if(flag not in listener.flags):
                        return False
                return True
            return False
    def _validate_ordering(self, group : engine_constants.EngineGroup, new_ordering : list[event_listener.AbstractEventListener]) -> bool:
        #validates that the new ordering has all the required elements
        if(len(self.event_listener_groups[group]) == len(new_ordering)):
            for i in new_ordering:
                if(i not in self.event_listener_groups[group]):
                    return False
            return True
        return False
    def attach_listener(self, listener : event_listener.AbstractEventListener):
        #attempts to add a listener if its flags overlap and its valid
        if(listener.is_valid() and self._check_listener(listener)):
            self.event_listener_groups[listener.group].append(listener)
            listener.attach_to_event(self)
    def propose_event(self, e : Event, priority : int = 0):
        self.engine._propose_event(e, priority)
    def forward(self, args :Data = {}) ->Response:
        if(self.group_on == engine_constants.EngineGroup.INTERNAL_4 
           and len(self.event_listener_groups[engine_constants.EngineGroup.INTERNAL_4]) == 0):
            #case 1: there's nothing left to run
            return self.generate_response(ResponseType.FINISHED)
        elif(self.group_on == engine_constants.EngineGroup.CORE):
            #case 2: we're running the core function
            response = self.core(args)
            if(response.response_type ==ResponseType.CORE):
                #if the response indicates that we can move on
                self.group_on = self.group_on.succ()
            return response
        elif(len(self.event_listener_groups[self.group_on]) == 0):
            #case 3: we're on a group that's not the last and not core,
            #and we're done with the listeners in it
            response = self.generate_response(ResponseType.ACCEPT)
            self.group_on = self.group_on.succ()
            return response
        elif(self.group_on == engine_constants.EngineGroup.EXTERNAL_MODIFIERS 
             and len(self.event_listener_groups[self.group_on]) > 1
             and not self.external_modifiers_ordered):
            #case 4: we haven't ordered modifiers and we need to
            if(args != {}):
                if(self._validate_ordering(args['group_ordering'])):
                    self.event_listener_groups[self.group_on] = args['group_ordering']
                    self.external_modifiers_ordered = True
                    return self.generate_response(ResponseType.ACCEPT)
            return self.generate_response(ResponseType.REQUIRES_QUERY,
                                          {"query_type": "ext_modifier_order", 'unordered_groups': self.event_listener_groups[self.group_on]})
        elif(self.group_on == engine_constants.EngineGroup.EXTERNAL_REACTORS 
             and len(self.event_listener_groups[self.group_on]) > 1
             and not self.external_reactors_ordered):
            #case 5: we haven't ordered reactors and we need to
            if(args != {}):
                if(self._validate_ordering(args['group_ordering'])):
                    self.event_listener_groups[self.group_on] = args['group_ordering']
                    self.external_reactors_ordered = True
                    return self.generate_response(ResponseType.ACCEPT)
            return self.generate_response(ResponseType.REQUIRES_QUERY,
                                          {"query_type": "ext_reactor_order", 'unordered_groups': self.event_listener_groups[self.group_on]})
        else:
            #case 6: we have a listener to take care of
            next_listener = self.event_listener_groups[self.group_on].pop(0)
            if(next_listener.internal and not self._check_listener(next_listener)):
                #if the listener's flags don't match (for internal listeners), we simply move on
                return self.generate_response(ResponseType.ACCEPT)
            
            if(isinstance(next_listener, event_listener.AssessorEventListener)):
                response = next_listener.assess(args)
            elif(isinstance(next_listener, event_listener.ModifierEventListener)):
                response = next_listener.modify(args)
            elif(isinstance(next_listener, event_listener.ReactorEventListener)):
                response = next_listener.react(args)
            
            if(response.response_type ==ResponseType.REQUIRES_QUERY):
                #if requires query, we need to wait for args next time and try to run the same listener again -- since we used pop, we now need to insert back
                self.event_listener_groups[self.group_on].insert(0, next_listener)
            return response
        
        