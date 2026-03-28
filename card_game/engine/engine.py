from __future__ import annotations
from typing import Tuple
from .engine_queue import EngineQueue
from . import event
from . import event_listener
from . import constrainer
from .engine_constants import *
from card_game.constants import Data, Response, ResponseType, INTERRUPT_KEY

class Engine():
    def __init__(self):
        self._constraints : list[constrainer.Constraint] = []#list of active constraints
        self._constraints_backup : list[constrainer.Constraint] = None

        self._external_listeners : list[event_listener.AbstractEventListener] = []
        self._external_listeners_backup : list[event_listener.AbstractEventListener] = None

        self.event_running : event.Event = None
        self.packet_running : event.AssemblyPacket = []
        self.listeners_run_during_packet : set[event_listener.AbstractEventListener] = set([])
        self.event_stack : list[event.Event] = []
        self._queue : EngineQueue[event.AssemblyPacket] = EngineQueue()
    def add_constraint(self, constraint : 'constrainer.Constraint'):
        #first, check if this constrainer falls under other constrainers. if it does, drop it.
        for c in self._constraints:
            if(c.match(constraint)):
                return
        #now that we know it falls under no constraints, we can add it to the active constraints
        self._constraints.append(constraint)

        #check all of the active constraints that aren't this 
        #and see if any of them fall under this one. if they do, deactivate them
        deactivated_constrainers : list[constrainer.Constraint]= []
        for c in self._constraints[:-1]:
            if(constraint.match(c)):
                deactivated_constrainers.append(c)
                c.invalidate()
        #update constraints to not contain any deactivated constrainers
        self._constraints = [c for c in self._constraints if c not in deactivated_constrainers]

    def _probe_constraints(self):
        #Probes constraints to make sure they're all still active.
        deactivated_constrainers : list[constrainer.Constraint]= []
        for c in self._constraints:
            c.update_status()
            if(c._invalidated):
                deactivated_constrainers.append(c)
        self._constraints = [c for c in self._constraints if c not in deactivated_constrainers]

    def add_listener(self, listener : event_listener.AbstractEventListener):
        self._external_listeners.append(listener)
    
    def _probe_listeners(self):
        #Probes listeners to make sure they're all still active.
        deactivated_listeners : list[event_listener.AbstractEventListener]= []
        for l in self._external_listeners:
            l.update_status()
            if(l._invalidated):
                deactivated_listeners.append(l)
        self._external_listeners = [l for l in self._external_listeners if l not in deactivated_listeners]
    
    def _propose(self, new_event : event.Event | list[event.Event | event.EventAssembler] | event.EventAssembler, priority : int = 0):
        #proposes an addition in the standard fashion
        reprocessed_packet : list[event.EventAssembler] = []
        if(not isinstance(new_event, list)):
            new_event = [new_event]
        for e in new_event:
            if(isinstance(e, event.Event)):
                reprocessed_packet.append(e._package_into_assembler())
            else:
                reprocessed_packet.append(e)
        self._queue.propose(reprocessed_packet, priority)
    
    def forward(self, args : Data  = {}) -> Response:
        if(self.event_running is None and len(self.packet_running) == 0 and self._queue.queue_len() == 0):
            return Response(self, response_type=ResponseType.NO_MORE_EVENTS)
        elif(self.event_running is None and len(self.packet_running) > 0):
            #prepares a fresh event from the current packet to run
            
            self.event_running = self.packet_running.pop(0)
            if(isinstance(self.event_running, event.EventAssembler)):
                #assemble
                self.event_running = self.event_running.assemble()
                self.event_running._prepare_post_assemble()
                self.event_running.attach_to_engine(self)
                #attach all external listeners to the incoming packet
                for listener in self._external_listeners:
                    self.event_running.attach_listener(listener)
                        
            return Response(self, response_type=ResponseType.NEXT_EVENT)
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
            #resets event stack
            self.event_stack = []
            #reset listeners run
            self.listeners_run_during_packet = set([])
            return Response(self, response_type=ResponseType.NEXT_PACKET)
        else:
            if(self.event_running.group_on == EngineGroup.CORE):
                #opens the buffer for CORE and all groups after
                self._queue.set_status(QueueStatus.BUFFERED)
            if(not self.event_running._ready):
                raise Exception("Tried to run event that wasn't ready!")
            response = self.event_running.forward(self._constraints, args)
            if(response.response_type == ResponseType.GAME_END):
                return response
            elif(response.response_type == ResponseType.INTERRUPT):
                #probe constraints
                self._probe_constraints()
                #probe listeners
                self._probe_listeners()
                #place the interrupted event back into the packet
                self.packet_running.insert(0, self.event_running)
                #put the requested events in front of the existing packet
                updated_packet = []
                requested_addition = response.data.get(INTERRUPT_KEY, [])
                if(not isinstance(requested_addition, list)):
                    requested_addition = [requested_addition]
                for packet in requested_addition:
                    if(not isinstance(packet, event.Event) and not isinstance(packet, event.EventAssembler)):
                        raise Exception("Attempted to update packet with a non-event")
                    elif(isinstance(packet, event.Event)):
                        packet = packet._package_into_assembler()
                    updated_packet.append(packet)
                updated_packet.extend(self.packet_running)
                self.packet_running = updated_packet
                self.event_running = None
            elif(response.response_type == ResponseType.FINISHED or response.response_type == ResponseType.FAST_FORWARD):
                #if an event finished properly
                #note: this does NOT necessarily mean the packet is complete. only on packet completion are changes truly committed
                
                #add all listeners run during the event in the WIDEST FORM POSSIBLE
                for listeners in self.event_running.event_listener_groups.values():
                    for listener in listeners:
                        self.listeners_run_during_packet.add(listener)
                
                if(len(self.packet_running) == 0):
                    #if the entire packet is done
                    #actualize ALL proposed events that happened during the packet
                    self._queue.flush_buffer()
                    #open the queue
                    self._queue.set_status(QueueStatus.OPEN)
                    #probe all constraints to ensure that the only ones left are the ones still active
                    self._probe_constraints()
                    #probe all listeners to ensure that the only ones left are the ones still active
                    self._probe_listeners()
                    #reset the backups, committing the changes
                    self._constraints_backup = None
                    self._external_listeners_backup = None
                    #change the response type to FINISHED_PACKET
                    response.response_type = ResponseType.FINISHED_PACKET
                    #set event running to None
                    self.event_running = None
                    #notify all event listeners that their packet finished successfully
                    for listener in self.listeners_run_during_packet:
                        listener.on_packet_completion()
                else:
                    #if just one event in many are done/ff'd

                    #tells the engine that this event in the packet has run properly
                    self.event_stack.append(self.event_running)
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
                while(len(self.event_stack) > 0):
                    e = self.event_stack.pop()#FILO order
                    if(e.core_ran):
                        e.invert_core(e.core_args)
                if(self.event_running.core_ran):
                    #undo this event's core if it went through
                    self.event_running.invert_core(self.event_running.core_args)
                #dispose of the packet and event completely
                self.packet_running = []
                self.event_running = None
                #reset the backups
                self._constraints_backup = None
                self._external_listeners_backup = None
            return response