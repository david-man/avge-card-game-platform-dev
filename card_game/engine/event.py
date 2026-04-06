from __future__ import annotations
from . import event_listener
from typing import TYPE_CHECKING, Callable, Sequence, Generic, TypeVar, cast
from card_game.constants import *
from . import engine_constants

if TYPE_CHECKING:
    from . import engine
    from . import constrainer

EV = TypeVar("EV", bound="Event")
class Packet(Generic[EV]):
    def __init__(self, element : Sequence[EV] | Sequence[DeferredEvent[EV]] | Sequence[EV|DeferredEvent[EV]] | Callable[[], Sequence[EV|DeferredEvent[EV]]]):
        self.element : Sequence[EV | DeferredEvent[EV]] | Callable[[], Sequence[EV|DeferredEvent[EV]]]
        if(not isinstance(element, Sequence) and not isinstance(element, Callable)):
            self.element = [element]
        elif(isinstance(element, Callable)):
            self.element = element
        else:
            self.element = cast(list[EV | DeferredEvent[EV]], element)
    def insert(self, i : int, e : EV | DeferredEvent[EV] | list[DeferredEvent[EV] | EV]):
        if(isinstance(self.element, list)):
            if(not isinstance(e, list)):
                self.element.insert(i, e)
            else:
                self.element[i:i] = e
        else:
            raise Exception("Cannot insert into packet when packet not assembled")
    def append(self, e : EV | DeferredEvent[EV] | list[EV | DeferredEvent[EV]]):
        if(isinstance(self.element ,list)):
            if(isinstance(e, list)):
                self.element += e
            else:
                self.element.append(e)
        else:
            raise Exception("Cannot insert into packet when packet not assembled")
    def extend(self, p : Packet[EV]):
        if(isinstance(self.element,list) and isinstance(p.element, list)):
            self.element.extend(cast(list[DeferredEvent[EV] | EV], p.element))
        else:
            raise Exception("Cannot extend non-assembled packet assemblers")
    def assemble(self):
        #Assembles the packet into a list of events
        if(callable(self.element)):
            called = self.element()
            if(not isinstance(called, list)):
                raise Exception("Packet assembler returned a non-assembled packet")
            self.element = called
    def __len__(self):
        if(not isinstance(self.element, list)):
            raise Exception("Tried to get length when packet not assembled yet")
        return len(self.element)
    def get_next_event(self) -> EV | None:
        if(not isinstance(self.element, list)):
            raise Exception("Tried to get next event when packet not assembled yet")
        else:
            if(len(self.element) == 0):
                return None
            else:
                next_item = self.element.pop(0)
                if(isinstance(next_item, DeferredEvent)):
                    return cast(EV, next_item._assemble())
                return cast(EV, next_item)

class DeferredEvent(Generic[EV]):
    def __init__(self, cls : type[EV], **kwargs):
        self.kwargs = kwargs
        self.cls = cls
    def _assemble(self) -> EV:
        resolved_kwargs = {
            k: (v() if isinstance(v, Callable) else v)
            for k, v in self.kwargs.items()
        }
        return self.cls(**resolved_kwargs)
class Event():
    def __init__(self, **kwargs):
        self.engine : engine.Engine | None = None
        self.event_listener_groups : dict[engine_constants.EngineGroup, list[event_listener.AbstractEventListener]] = {group : [] for group in engine_constants.EngineGroup}
        self.group_on = engine_constants.EngineGroup(0)
        self.groups_ordered : dict[engine_constants.EngineGroup, bool] = {group : False for group in engine_constants.EngineGroup}
        self.groups_constrained : dict[engine_constants.EngineGroup, bool] = {group : False for group in engine_constants.EngineGroup}
        self.core_args : Data = {}
        self.core_ran : bool = False

        self.generate_internal_listeners()
        for group in self.event_listener_groups.values():
            for listener in group:
                listener.attach_to_event(self)
        self._external_listeners_attached = False

        self._kwargs = kwargs
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
            self.core_ran = True
        return r
    
    def core(self, args :Data | None = None) ->Response:
        if(args is None):
            args = {}
        #you should override this!
        #note that, in place of ACCEPT, you should return CORE 
        raise NotImplementedError()
    def invert_core(self, args : Data | None = None) -> None:
        if(args is None):
            args = {}
        #this will only be relevant once core() is successfully run
        #args is populated instantaneously
        raise NotImplementedError()

    def generate_internal_listeners(self):
        #you should override this! this function should simply populate the event_listeners_groups
        raise NotImplementedError()
    
    def generate_core_response(self, 
                          response_type : ResponseType =ResponseType.CORE,
                          data :Data = {}) ->Response:
        #Helper function to generate a response packet for core() easier
        return Response(self, response_type, data)

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
        #attempts to add a listener if its a match. Returns True on success
        if(listener._should_attach(self)):
            self.event_listener_groups[listener.group].append(listener)
            listener.attach_to_event(self)
            return True
        return False
    def _detach_listeners(self):
        #detaches all listeners
        for group in self.event_listener_groups:
            for listener in self.event_listener_groups[group]:
                listener.detach_from_event()
    def propose(self, p : Packet, priority : int = 0):
        assert self.engine is not None
        self.engine._propose(p, priority)
    def forward(self, constraints : list[constrainer.Constraint], args :Data | None = None) ->Response:
        if(args is None):
            args = {}
        if(self.group_on.value == engine_constants.MAX_GROUP
           and len(self.event_listener_groups[self.group_on]) == 0):
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
            
            #step 1: constrain all event listeners 
            if(not self.groups_constrained[self.group_on] and len(self.event_listener_groups[self.group_on]) >= 1):
                for listener in self.event_listener_groups[self.group_on]:
                    for constraint in constraints:
                        if(constraint._should_attach(listener)):
                            listener.detach_from_event()
                            self.event_listener_groups[self.group_on].remove(listener)
                            return Response(self, ResponseType.ACCEPT, data = {'constrainer_announced': constraint.package()})
            #if all event listeners constrained, we can mark the group as constrained
            self.groups_constrained[self.group_on] = True
            #step 2: consider ordering if must be
            if(not self.groups_ordered[self.group_on]):
                if(self.group_on in [engine_constants.EngineGroup.EXTERNAL_MODIFIERS_1, engine_constants.EngineGroup.EXTERNAL_MODIFIERS_2, engine_constants.EngineGroup.EXTERNAL_MODIFIERS_3, engine_constants.EngineGroup.EXTERNAL_REACTORS] 
                     and len(self.event_listener_groups[self.group_on]) >= 2):
                    group_ordering = args.get('group_ordering')
                    if(group_ordering is not None):
                        if(self._validate_ordering(self.group_on, group_ordering)):
                            self.event_listener_groups[self.group_on] = group_ordering
                            self.groups_ordered[self.group_on] = True
                            return Response(self, ResponseType.ACCEPT, {})
                    return Response(self, ResponseType.REQUIRES_QUERY,
                                        {"query_type": "ordering", 'unordered_groups': self.event_listener_groups[self.group_on]})

            self.groups_ordered[self.group_on] = True
            #step 3: question whether to go through with the listener
            next_listener = self.event_listener_groups[self.group_on].pop(0)
            if(next_listener._invalidated or not bool(next_listener.event_effect())):
                #skip if invalidated
                return Response(self, ResponseType.ACCEPT)
            else:
                response = Response(self, ResponseType.ACCEPT)
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
                elif(response.response_type == ResponseType.INTERRUPT):
                    #if interrupt, when this event continues, it needs to run the listener again
                    self.event_listener_groups[self.group_on].insert(0, next_listener)
                elif(response.response_type in [ResponseType.FINISHED, ResponseType.SKIP]):
                    #if event is over with, detach all listeners 
                    self._detach_listeners()
                return response
        
        