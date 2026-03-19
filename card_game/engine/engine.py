from __future__ import annotations
from .engine_queue import EngineQueue
from . import event
from . import event_listener
from .engine_constants import *
from card_game.constants import Data, Response, ResponseType
from copy import copy


class Engine():
    def __init__(self):
        self.external_listeners : list[event_listener.AbstractEventListener] = []
        self.external_listener_savestate : list[event_listener.AbstractEventListener] = None
        self.event_running : event.Event = None
        self.packet_running : event.EventPacket = []
        self.event_stack : event.EventPacket = []
        self._queue : EngineQueue[event.EventPacket] = EngineQueue()
    def add_external_listener(self, listener : event_listener.AbstractEventListener):
        self.external_listeners.append(listener)
        listener.engine = self
    def remove_external_listener(self, listener : event_listener.AbstractEventListener):
        self.external_listeners.remove(listener)
        listener.engine = None

    def _propose(self, new_event : event.Event | event.EventPacket, priority : int = 0):
        #proposes a singular event / EventPacket addition in the standard fashion
        if(isinstance(new_event, event.Event)):
            new_event = [new_event]
        for e in new_event:
            e.attach_to_engine(self)
        self._queue.propose(new_event, priority)

    def _inject_event(self, new_event : event.Event | event.EventPacket, priority : int = 0):
        #injects an event / EventPacket straight into the main queue. 
        #be VERY careful when working with this, since this action cannot be undone
        if(isinstance(new_event, event.Event)):
            new_event = [new_event]
        for e in new_event:
            e.attach_to_engine(self)
        self._queue.inject(new_event, priority)

    def _refresh(self, event_succeeded : bool = False):
        #refreshes the engine after an EVENT finishes running
        if(event_succeeded):
            self._queue.flush_buffer()#actualize all proposed changes in the queue

            
        else:
            #revert to old external listeners
            self.external_listeners = self.external_listener_savestate
            #dispose of all proposed changes
            self._queue.clear_buffer()
            #dispose of the packet completely
            self.packet_running = []
        
        #remove all dead external event listeners to prepare for the next event
        for listener in self.external_listeners:
            if(not listener.is_valid()):
                self.remove_external_listener(listener)

        #dispose of the event
        self.event_running = None
    
    def forward(self, args : Data | None = None) -> Response:

        if(args is None):
            args = {}
        if(self.event_running is None and len(self.packet_running) == 0 and self._queue.queue_len() == 0):
            return Response(self, response_type=ResponseType.NO_MORE_EVENTS)
        elif(self.event_running is None and len(self.packet_running) > 0):
            #prepares a new event from the current packet to run
            self.event_running = self.packet_running.pop(0)
            #re-closes the queue to prevent modification during prohibited periods
            self._queue.set_status(QueueStatus.CLOSED)
            #attach all necessary external listeners to the incoming packet
            for listener in self.external_listeners:
                self.event_running.attach_listener(listener)
            return Response(self, response_type=ResponseType.NEXT_EVENT)
        elif(self.event_running is None and len(self.packet_running) == 0 and self._queue.queue_len() > 0):
            #prepares a new packet from the current queue to run
            self.packet_running = self._queue.pop()
            #set a savestate for external listeners
            self.external_listener_savestate = [copy(listener) for listener in self.external_listeners]
            #resets event stack
            self.event_stack = []
            return Response(self, response_type=ResponseType.NEXT_PACKET)
        else:
            if(self.event_running.group_on == EngineGroup.CORE):
                #opens the buffer for CORE and all groups after
                self._queue.set_status(QueueStatus.BUFFERED)
            response = self.event_running.forward(args)
            if(response.response_type == ResponseType.FINISHED):
                #if the event finished properly
                if(len(self.packet_running) == 0):
                    #if the entire packet is done
                    #actualize ALL proposed events that happened during the packet
                    self._queue.flush_buffer()
                    #open the queue
                    self._queue.set_status(QueueStatus.OPEN)
                    #reset savestate
                    self.external_listener_savestate = None
                else:
                    self.event_stack.append(self.event_running)#tells the engine that this packet has run properly

                #make sure that all event listeners are still valid
                for listener in self.external_listeners:
                    if(not listener.is_valid()):
                        self.remove_external_listener(listener)
                
                #notify all valid event listeners that their event is over
                for listeners in self.event_running.event_listener_groups.values():
                    for listener in listeners:
                        listener.on_event_completion()
                #set event running to None
                self.event_running = None
            elif(response.response_type == ResponseType.SKIP):
                #if not finished properly

                #revert to old external listeners
                self.external_listeners = self.external_listener_savestate
                #dispose of all proposed additions
                self._queue.clear_buffer()
                #undo all changes that were made before
                while(len(self.event_stack) > 0):
                    e = self.event_stack.pop()#FILO order
                    e.invert_core(e.core_args)
                #dispose of the packet and event completely
                self.packet_running = []
                self.event_running = None
                #reset savestate
                self.external_listener_savestate = None
                

            return response