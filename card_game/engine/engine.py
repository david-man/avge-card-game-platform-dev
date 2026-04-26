from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Generic, TypeVar, cast, Type, Tuple, Any
from .engine_queue import EngineQueue
from .event import Event, Packet
from .engine_constants import *
from card_game.constants import Data, Response, ResponseType, Interrupt

if TYPE_CHECKING:
    from . import event_listener
    from . import constrainer

EV = TypeVar("EV", bound=Event)
class HistoryState(Enum):
    FORMALIZED = 0
    NONFORMALIZED = 1
    UNDONE = 2
class EngineHistory(Generic[EV]):
    def __init__(self, chapter_start : int = 0):
        self.history : dict[int, list[Tuple[EV, HistoryState]]] = {0: []}
        self._chapter : int = chapter_start
    def set_unformalized_changes(self, new_state : HistoryState) -> list[EV]:
        if(len(self.history[self._chapter]) == 0):
            raise IndexError()
        else:
            new_history : list[Tuple[EV, HistoryState]] = []
            to_return : list[EV] = []
            for event, state in self.history[self._chapter]:
                if(state != HistoryState.NONFORMALIZED):
                    new_history.append((event, state))
                else:
                    new_history.append((event, new_state))
                    to_return.append(event)
            self.history[self._chapter] = new_history
            return to_return
    def propose_event(self, event : EV):
        self.history[self._chapter].append((event, HistoryState.NONFORMALIZED))
    def new_chapter(self):
        if(len(self.history[self._chapter ]) > 0 and self.history[self._chapter][-1][1] == HistoryState.NONFORMALIZED):
            raise Exception("You cannot make a new chapter while the last one hasn't been fully formalized!")
        self._chapter += 1
        self.history[self._chapter] = []
    def search(self, chapter : int, event_type : Type[EV], kwargs : dict[str, Any], index_to_start : int = 0, specific_state : HistoryState = HistoryState.FORMALIZED) -> Tuple[EV | None, int]:
        #Searches for the earliest event in a chapter given a set of (not necessarily complete) kwargs. Second element is the index if found, -1 if not
        if(chapter not in self.history.keys()):
            return None, -1
        if(len(self.history[chapter]) <= index_to_start):
            return None, -1
        for i, (event, state) in enumerate(self.history[chapter][index_to_start:], start=index_to_start):
            if(isinstance(event, event_type)):
                if(not state == specific_state):
                    continue
                matched = True
                for kwarg_key, kwarg_val in kwargs.items():
                    if(kwarg_key not in event._kwargs or event._kwargs[kwarg_key] != kwarg_val):
                        matched = False
                        break
                if(not matched):
                    continue
                return event, i
        return None, -1
class Engine(Generic[EV]):
    type Gen = Callable[[], list[EV | Gen]]
    def __init__(self):
        self._constraints : list[constrainer.Constraint[EV]] = []#list of active constraints
        self._constraints_backup : list[constrainer.Constraint[EV]] = []
        self._packet_reactors : list[event_listener.AbstractPacketListener] = []
        self._queued_responses : list[Response] = []
        self._external_listeners : list[event_listener.AbstractEventListener[EV]] = []
        self._external_listeners_backup : list[event_listener.AbstractEventListener[EV]] = []
        self.event_history = EngineHistory[EV]()
        self.event_running : EV | None = None
        self.packet_running : Packet[EV] = Packet([])
        self.listeners_attached_during_packet : set[event_listener.AbstractEventListener] = set([])
        self._queue : EngineQueue[Packet[EV]] = EngineQueue()

    def add_constraint(self, constraint : 'constrainer.Constraint[EV]'):
        #first, check if this constrainer falls under other constrainers. if it does, drop it.
        for c in self._constraints:
            if(c.match(constraint)):
                return
        #now that we know it falls under no constraints, we can add it to the active constraints
        self._constraints.append(constraint)

        #check all of the active constraints that aren't this 
        #and see if any of them fall under this one. if they do, deactivate them
        deactivated_constrainers : list[constrainer.Constraint[EV]]= []
        for c in self._constraints[:-1]:
            if(constraint.match(c)):
                deactivated_constrainers.append(c)
                c.invalidate()
        #update constraints to not contain any deactivated constrainers
        self._constraints = [c for c in self._constraints if c not in deactivated_constrainers]

    def _probe_constraints(self):
        #Probes constraints to make sure they're all still active.
        deactivated_constrainers : list[constrainer.Constraint[EV]]= []
        for c in self._constraints:
            c.update_status()
            if(c._invalidated):
                deactivated_constrainers.append(c)
        self._constraints = [c for c in self._constraints if c not in deactivated_constrainers]

    def add_listener(self, listener : event_listener.AbstractEventListener[EV]):
        self._external_listeners.append(listener)
        listener.engine = self

    def add_packet_listener(self, listener : event_listener.AbstractPacketListener[EV]):
        self._packet_reactors.append(listener)
        listener.engine = self
    
    def _probe_listeners(self):
        #Probes listeners to make sure they're all still active.
        deactivated_listeners : list[event_listener.AbstractEventListener[EV]]= []
        for l in self._external_listeners:
            l.update_status()
            if(l._invalidated):
                deactivated_listeners.append(l)
        self._external_listeners = [l for l in self._external_listeners if l not in deactivated_listeners]

    def _probe_packet_listeners(self):
        #Probes packet listeners to make sure they're all still active.
        deactivated_listeners : list[event_listener.AbstractPacketListener[EV]]= []
        for l in self._packet_reactors:
            l.update_status()
            if(l._invalidated):
                deactivated_listeners.append(l)
        self._packet_reactors = [l for l in self._packet_reactors if l not in deactivated_listeners]

    def peek_n(self, n : int = 1):
        #gets the main queue
        return [self.packet_running] + self._queue.peek_n(n - 1)
    
    def external_interrupt(self, packet : Packet[EV]):
        if(self.event_running is not None):
            self.packet_running.insert(0, [self.event_running])
        #put the requested events in front of the existing packet
        self._queue.insert(packet, -100000)
        self.event_running = None
        self.packet_running = Packet([])
    def _propose(self, new_packet : Packet[EV], priority : int = 0):
        #proposes an addition in the standard fashion
        self._queue.propose(new_packet, priority)
    
    def _ff(self) -> None:#marks the current event to be FF'd on the next forward call
        if(not self.event_running is None):
            self.event_running._ff()

    def _extend(self, packet : list[EV | Gen]):
        #extends the current running PACKET with the given
        self.packet_running.append(packet)

    def _extend_event(self, packet : list[EV | Gen]):
        #extends the current running EVENT with the givne
        self.packet_running.insert(0, packet)
        
    def forward(self, args : dict | None = None) -> Response:
        if(args is None):
            args = {}
        if(len(self._queued_responses) > 0):
            return self._queued_responses.pop(0)
        if(self.event_running is None and len(self.packet_running) == 0 and self._queue.queue_len() == 0):
            return Response(ResponseType.NO_MORE_EVENTS, Data())
        elif(self.event_running is None and len(self.packet_running) == 0 and self._queue.queue_len() > 0):
            #prepares a new packet from the current queue to run
            self.packet_running = self._queue.pop()
            
            #backup all constraints
            self._constraints_backup = []
            for c in self._constraints:
                self._constraints_backup.append(c)
            #backup all listeners
            self._external_listeners_backup = []
            for l in self._external_listeners:
                self._external_listeners_backup.append(l)
            #reset listeners run
            self.listeners_attached_during_packet = set([])
            return Response(ResponseType.NEXT_PACKET, Data())
        elif(self.event_running is None and len(self.packet_running) > 0):
            #prepares a fresh event from the current packet to run
            self.event_running = self.packet_running.get_next_event()
            if(self.event_running is None):
                return self.forward(args)
            else:
                self.event_running.attach_to_engine(self)
                
                #attach all required external listeners
                if(not self.event_running._external_listeners_attached):
                    for listener in self._external_listeners:
                        attached = self.event_running.attach_listener(listener)
                        if(attached):
                            self.listeners_attached_during_packet.add(listener)
                    self.event_running._external_listeners_attached = True
                return Response(ResponseType.NEXT_EVENT, Data())
        else:
            assert self.event_running is not None
            if(self.event_running.group_on == EngineGroup.CORE):
                #opens the buffer for CORE and all groups after
                self._queue.set_status(QueueStatus.BUFFERED)
            response = self.event_running.forward(self._constraints, args)
            if(response.response_type == ResponseType.GAME_END):
                return response
            elif(response.response_type == ResponseType.INTERRUPT):
                assert isinstance(response.data, Interrupt)
                #place the interrupted event back into the packet
                self.packet_running.insert(0, [self.event_running])
                #put the requested events in front of the existing packet
                requested_addition : list[EV | Engine.Gen] = response.data.insertion #type: ignore
                self.packet_running.insert(0, requested_addition)
                self.event_running = None
            elif(response.response_type == ResponseType.FINISHED or response.response_type == ResponseType.FAST_FORWARD):
                #if an event finished properly
                #note: this does NOT necessarily mean the packet is complete. only on packet completion are changes truly committed
                if(len(self.packet_running) == 0):
                    #if the entire packet is done and all packet listeners are checked
                    #actualize ALL proposed events that happened during the packet
                    self._queue.flush_buffer()
                    #rebuffer the queue immediately
                    self._queue.set_status(QueueStatus.BUFFERED)
                    #probe all constraints to ensure that the only ones left are the ones still active
                    self._probe_constraints()
                    #probe all listeners to ensure that the only ones left are the ones still active
                    self._probe_listeners()
                    self._probe_packet_listeners()
                    #reset the backups, committing the changes
                    self._constraints_backup = []
                    self._external_listeners_backup = []
                    #change the response type to FINISHED_PACKET
                    response.response_type = ResponseType.FINISHED_PACKET
                    #formalize history
                    self.event_history.set_unformalized_changes(HistoryState.FORMALIZED)
                    #set event running to None
                    self.event_running = None
                    #notify all event listeners that their packet finished successfully
                    for listener in self.listeners_attached_during_packet:
                        listener.on_packet_completion()

                    #packet listener responses
                    for listener in self._packet_reactors:
                        if(listener._should_attach(self.packet_running, ResponseType.FINISHED_PACKET)):
                            self._queued_responses.append(listener.react(self.packet_running))
                    #flush in the events made by the packet listeners
                    self._queue.flush_buffer()
                else:
                    #if just one event in many are done/ff'd

                    #tells the engine that this event in the packet has run properly
                    self.event_history.propose_event(self.event_running)
                    #probe constraints
                    self._probe_constraints()
                    #probe listeners
                    self._probe_listeners()
                    #set event running to None
                    self.event_running = None
            elif(response.response_type == ResponseType.SKIP):
                #if not finished properly
                #revert to pre-packet event constrainers
                for c in self._constraints:
                    if(c not in self._constraints_backup):
                        c.invalidate()
                self._constraints = self._constraints_backup
                #before the backup, all invalidated constraints were cleared out, so this is fine
                for c in self._constraints:
                    c._invalidated = False
                #revert to pre-packet event listeners
                for l in self._external_listeners:
                    if(l not in self._external_listeners_backup):
                        l.invalidate()
                self._external_listeners = self._external_listeners_backup
                for l in self._external_listeners:
                    l._invalidated = False
                #dispose of all proposed additions to the event queue and reopen the buffer
                self._queue.clear_buffer()
                #undo all changes that were made in events that ran in the packet before the current one
                to_undo = self.event_history.set_unformalized_changes(HistoryState.UNDONE)
                while(len(to_undo) > 0):
                    e = to_undo.pop()#FILO order
                    if(e.core_ran):
                        e.invert_core(e.core_args)
                if(self.event_running.core_ran):
                    #undo this event's core if it went through
                    self.event_running.invert_core(self.event_running.core_args)
                
                #probe packet listeners 
                self._probe_packet_listeners()
                #packet listener responses
                for listener in self._packet_reactors:
                    if(listener._should_attach(self.packet_running, ResponseType.SKIP)):
                        self._queued_responses.append(listener.react(self.packet_running))
                self._queue.flush_buffer()
                #dispose of the packet and event completely
                self.packet_running = Packet([])
                self.event_running = None
                #reset the backups
                self._constraints_backup = []
                self._external_listeners_backup = []

                
                    
            return response