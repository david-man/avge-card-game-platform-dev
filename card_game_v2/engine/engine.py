from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from .record import History, HistoricalStatus
from ..constants import ResponseStatus, ID
if TYPE_CHECKING:
    from .event import Event, Packet
    from .listener import EventListener, PacketReactor, IOListener
    from .constrainer import Constrainer
    from .engine_io import IOManager, IOType, IOListenerReorderIO
    from .global_cache import *


@dataclass
class Message:
    message_id: str


class Engine:
    def __init__(self, io_manager: IOManager, global_cache : Cache[Any]):
        self.current_packet: Packet | None = None
        self.listeners: list[EventListener] = []
        self.packet_listeners: list[PacketReactor] = []
        self.constrainers: list[Constrainer] = []
        self.io_listeners : list[IOListener] = []
        self.history: History = History()

        self._packet_queue: deque[Packet] = deque([])
        self._buffered_pushes : list[Packet] = []
        self._buffered_appends : list[Packet] = []

        self.io_manager = io_manager  # this io_manager should take in an IOType object, parse it and send it to the users, and return once the users have properly responded with something

        self.global_cache = global_cache

        self.terminate_flag : bool = False #When terminate_flag is set, the game engine will finish the current event before terminating.

        self.on_event_committed: Callable[[Event], Awaitable[None]] | None = None
        self.on_packet_failed: Callable[[Packet], Awaitable[None]] | None = None

    def add_listener(self, listener: EventListener):
        '''Adds an event listener to the engine'''
        self.listeners.append(listener)

    def add_packet_listener(self, packet_listener: PacketReactor):
        '''Adds a packet listener from the engine'''
        self.packet_listeners.append(packet_listener)

    def add_io_listener(self, io_listener : IOListener):
        '''Adds an io listener to the engine'''
        self.io_listeners.append(io_listener)

    def search_history[EV: Event](self,
                                   event_type: type[EV],
                                   kwargs: dict[str, Any] | None = None,
                                   increment: int = 0,
                                   index_to_start: int = 0,
                                   specific_status: HistoricalStatus = HistoricalStatus.IMMUTABLE,
                                   attribute_search: bool = False) -> tuple[EV | None, int]:
        '''Searches history for the earliest matching event. See History.search for details.'''
        return self.history.search(event_type, kwargs, increment, index_to_start, specific_status, attribute_search)

    def add_constrainer(self, constrainer: Constrainer):
        '''Adds a constrainer to the engine'''
        # Step 1: Check that this constrainer isn't constrained by anything
        for c in self.constrainers:
            if (c.match(constrainer)):
                return
        # Step 2: Remove all constrainers that this constrainer constrains and then add it
        self.constrainers = [c for c in self.constrainers if not constrainer.match(c)]
        self.constrainers.append(constrainer)


    def push_packet(self, packet: Packet):
        '''Adds a packet to the front of the queue such that it runs right after the current one'''
        packet.set_engine(self)
        self._buffered_pushes.append(packet)

    def append_packet(self, packet: Packet):
        '''Adds a packet to the back of the queue such that it runs after all other packets currently in the queue'''
        packet.set_engine(self)
        self._buffered_appends.append(packet)

    def _reset_buffer(self):
        '''Resets the buffer'''
        self._buffered_pushes = []
        self._buffered_appends = []

    def _flush_buffer(self):
        '''Flushes the buffered changes into the core queue. Does it in a way such that the first push and first append happen before the last push and the last append'''
        for packet in reversed(self._buffered_pushes):
            self._packet_queue.appendleft(packet)
        for packet in self._buffered_appends:
            self._packet_queue.append(packet)
        self._reset_buffer()

    async def broadcast(self, io_obj : IOType[None]):
        '''Specific broadcast request that blasts an IO object to all users'''
        await self.io_manager.broadcast(io_obj)

    async def report[T](self, io_obj : IOType[T], io_id : ID) -> T:
        from .event import IOEvent
        resp = await self.io_manager.report(io_obj)
        active_listeners = [listener for listener in self.io_listeners if listener.match(io_obj)]
        if(len(active_listeners) >= 2):
            active_listeners = await self.io_manager.report(IOListenerReorderIO(active_listeners, io_obj))
        for listener in active_listeners:
            resp = await listener.modify(io_obj, resp)
        self.history.add_record(HistoricalStatus.PENDING, IOEvent(io_id, io_obj, resp))
        return resp

    async def flush(self, new_chapter_condition : Callable[[], bool]):
        # bootstraps any preexisting proposed buffered changes; required for seeding starting packets
        self._flush_buffer()
        while self._packet_queue and not self.terminate_flag:
            self.current_packet = self._packet_queue.popleft()

            ## Checkpoint listeners, constrainers, etc.
            self.current_listeners = [listener for listener in self.listeners]
            self.current_constrainers = [constrainer for constrainer in self.constrainers]
            self.current_packet_reactors = [reactor for reactor in self.packet_listeners]
            self.current_io_listeners = [listener for listener in self.io_listeners]

            ## Run packet
            response = await self.current_packet.flush()
            if(self.terminate_flag):
                break

            ## Watch response. If fail, unwind cache, reset the proposed packet additions, and flush history. If game end, immediately stop. Otherwise, set everything in stone
            if (response == ResponseStatus.REGULATE_FAIL):
                if self.on_packet_failed is not None:
                    await self.on_packet_failed(self.current_packet)
                self.listeners = self.current_listeners
                for listener in self.listeners:
                    listener.requires_cleanup = False
                self.constrainers = self.current_constrainers
                for constrainer in self.constrainers:
                    constrainer.requires_cleanup = False
                self.packet_listeners = self.current_packet_reactors
                for listener in self.packet_listeners:
                    listener.requires_cleanup = False
                self.io_listeners = self.current_io_listeners
                for listener in self.io_listeners:
                    listener.requires_cleanup = False
                self.global_cache.unwind()
                self._reset_buffer()
                self.history.flush_records()
            else:
                for reactor in self.packet_listeners:
                    if (reactor.match(self.current_packet)):
                        await reactor.react(self.current_packet)
                self.global_cache.solidy_changes()
                self._flush_buffer()
                self.history.solidify_records()
                self.listeners = [listener for listener in self.listeners if not listener.requires_cleanup]
                self.constrainers = [constrainer for constrainer in self.constrainers if not constrainer.requires_cleanup]
                self.packet_listeners = [listener for listener in self.packet_listeners if not listener.requires_cleanup]
                self.io_listeners = [listener for listener in self.io_listeners if not listener.requires_cleanup]

            if(new_chapter_condition()):
                self.history.new_chapter()
