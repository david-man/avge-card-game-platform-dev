import heapq as _heap
from typing import TypeVar, Generic
from .engine_constants import QueueStatus

T = TypeVar("T")

class EngineQueue(Generic[T]):
    def __init__(self):
        self.main_queue : list[tuple[int, int, T]]= []
        self.buffered_queue : list[tuple[int, T]] = []
        self.queue_status : QueueStatus = QueueStatus.OPEN
        self.event_counter : int = 0
    
    def inject(self, item : T, priority : int = 0):
        #forcibly injects an event into the main queue regardless of what the queue status is
        _heap.heappush(self.main_queue, (priority, self.event_counter, item))
        self.event_counter += 1
    def propose(self, item : T, priority : int = 0):
        #Proposes an event addition, which does different things based on what the queue status is
        if(self.queue_status == QueueStatus.OPEN):
            _heap.heappush(self.main_queue, (priority, self.event_counter, item))
            self.event_counter += 1
        elif(self.queue_status == QueueStatus.BUFFERED):
            self.buffered_queue.append((priority, item))
        else:
            return

    def queue_len(self):
        return len(self.main_queue)    
    
    def pop(self) -> T:
        if(len(self.main_queue) > 0):
            return _heap.heappop(self.main_queue)[2]
        else:
            return None
        
    def flush_buffer(self):
        #Flushes the buffer into the active queue and transitions into an open state
        if(self.queue_status == QueueStatus.BUFFERED):
            self.queue_status = QueueStatus.OPEN
            for priority, item in self.buffered_queue:
                self.propose(item, priority)
            self.buffered_queue = []

    def clear_buffer(self):
        #Clears the buffer and opens the active queue
        if(self.queue_status == QueueStatus.BUFFERED):
            self.queue_status = QueueStatus.OPEN
            self.buffered_queue = []

    def set_status(self, status : QueueStatus):
        #Sets the queue status
        self.queue_status = status
    
    def remove(self, to_remove : T):
        #Removes directly from main queue
        new_heap = []
        for priority, counter, item in self.main_queue:
            if(item != to_remove):
                _heap.heappush(new_heap, (priority, counter, item))
        self.main_queue = new_heap

    def remove_from_buffer(self, to_remove : T):
        #removes from the buffered queue if the current queue status is buffered
        if(self.queue_status == QueueStatus.BUFFERED):
            self.buffered_queue.remove(to_remove)