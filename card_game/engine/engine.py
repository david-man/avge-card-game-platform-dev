from __future__ import annotations
from .engine_queue import EngineQueue
from . import event
from . import event_listener
from .engine_constants import *
from card_game.constants import *

class Engine():
    def __init__(self):
        self.external_listeners : list[event_listener.AbstractEventListener] = []
        self.event_running : event.Event = None
        self._queue : EngineQueue[event.Event] = EngineQueue()
    def add_external_listener(self, listener : event_listener.AbstractEventListener):
        self.external_listeners.append(listener)
        listener.engine = self
    def remove_external_listener(self, listener : event_listener.AbstractEventListener):
        self.external_listeners.remove(listener)
        listener.engine = None

    def _propose_event(self, new_event : event.Event, priority : int = 0):
        #proposes an event addition in the standard fashion
        new_event.attach_to_engine(self)
        self._queue.propose(new_event, priority)

    def _inject_event(self, e : event.Event, priority : int = 0):
        #injects an event straight into the main queue. only meant for internal use(like by the environment)
        e.attach_to_engine(self)
        self._queue.inject(e, priority)

    def _refresh(self, event_succeeded : bool = False):
        #refreshes the engine after event finishes running
        if(event_succeeded):
            self._queue.flush_buffer()#actualize all proposed changes in the queue
            for listeners in self.event_running.event_listener_groups.values():
                #notify all event listeners that their event is over
                for listener in listeners:
                    listener.on_event_completion()
        else:
            self._queue.clear_buffer()#dispose of all proposed changes
        
        #remove all dead event listeners to prepare for the next event
        for listener in self.external_listeners:
            if(not listener.is_valid()):
                self.remove_external_listener(listener)

        self.event_running = None
    
    def forward(self, args : Data = {}) -> Response:
        if(self.event_running == None and self._queue.queue_len() == 0):
            return Response(self, response_type=ResponseType.NO_MORE_EVENTS)
        elif(self.event_running == None):
            #prepares a new event to run, closes the queue to external modification in advance
            self.event_running = self._queue.pop()
            self._queue.set_status(QueueStatus.CLOSED)
            for listener in self.external_listeners:
                #only attempt attach external listeners (the only ones that can expire) 
                #when the event is up next -- removes possibility of dead-on-arrival listeners
                self.event_running.attach_listener(listener)
            return Response(self, response_type=ResponseType.ACCEPT)
        else:
            if(self.event_running.group_on == EngineGroup.CORE):
                #opens the queue during buffer time
                self._queue.set_status(QueueStatus.BUFFERED)
            response = self.event_running.forward(args)
            if(response.response_type == ResponseType.FINISHED):
                #if finished properly, let this event go, flush the buffer, and open the queue
                self._refresh(True)
            elif(response.response_type == ResponseType.SKIP):
                #if not finished properly, drop all proposed events
                self._refresh(False)
            return response