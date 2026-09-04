from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from typing import TYPE_CHECKING
from enum import Enum

from .record import History
from ..constants import ResponseStatus
if TYPE_CHECKING:
    from .event import Packet
    from .listener import EventListener, PacketReactor
    from .constrainer import Constrainer
    from .engine_io import IOManager
    from .global_cache import *


@dataclass
class Message:
    message_id: str


class DirectionalChange(Enum):
    FRONT = 0
    BACK = 1


class Engine:
    def __init__(self, io_manager: IOManager, global_cache : Cache[Any]):
        self.current_packet: Packet | None = None
        self.listeners: set[EventListener] = set([])
        self.packet_listeners: set[PacketReactor] = set([])
        self.constrainers: set[Constrainer] = set([])
        self.history: History = History()

        self._packet_queue: deque[Packet] = deque([])
        self._buffered_changes: list[tuple[DirectionalChange, Packet]] = []

        self.io_manager = io_manager  # this io_manager should take in an IOType object, parse it and send it to the users, and return once the users have properly responded with something

        self.global_cache = global_cache

        self.terminate_flag : bool = False #When terminate_flag is set, the game engine will finish the current event before terminating.

    def add_listener(self, listener: EventListener):
        '''Adds an event listener to the engine'''
        self.listeners.add(listener)

    def remove_listener(self, listener: EventListener):
        '''Removes an event listener from the engine'''
        self.listeners.remove(listener)

    def add_packet_listener(self, packet_listener: PacketReactor):
        '''Adds a packet listener from the engine'''
        self.packet_listeners.add(packet_listener)

    def remove_packet_listener(self, packet_listener: PacketReactor):
        '''Removes a packet listener from the engine'''
        self.packet_listeners.remove(packet_listener)

    def add_constrainer(self, constrainer: Constrainer):
        '''Adds a constrainer to the engine'''
        # Step 1: Check that this constrainer isn't constrained by anything
        for c in self.constrainers:
            if (c.match(constrainer)):
                return
        # Step 2: Remove all constrainers that this constrainer constrains and then add it
        self.constrainers = set(
            [c for c in self.constrainers if not constrainer.match(c)])
        self.constrainers.add(constrainer)

    def remove_constrainer(self, constrainer: Constrainer):
        '''Removes a constrainer from the engine'''
        self.constrainers.remove(constrainer)

    def push_packet(self, packet: Packet):
        '''Adds a packet to the front of the queue such that it runs right after the current one'''
        packet.set_engine(self)
        self._buffered_changes.append((DirectionalChange.FRONT, packet))

    def append_packet(self, packet: Packet):
        '''Adds a packet to the back of the queue such that it runs after all other packets currently in the queue'''
        packet.set_engine(self)
        self._buffered_changes.append((DirectionalChange.BACK, packet))

    def _reset_buffer(self):
        '''Resets the buffer'''
        self._buffered_changes = []

    def _flush_buffer(self):
        '''Flushes the buffered changes into the core queue'''
        for direction, packet in self._buffered_changes:
            if (direction == DirectionalChange.FRONT):
                self._packet_queue.appendleft(packet)
            else:
                self._packet_queue.append(packet)
        self._reset_buffer()

    

    async def flush(self):
        while self._packet_queue and not self.terminate_flag:
            self.current_packet = self._packet_queue.popleft()

            ## Checkpoint listeners, constrainers, etc.
            self.current_listeners = set(
                [listener for listener in self.listeners])
            self.current_constrainers = set(
                [constrainer for constrainer in self.constrainers])
            self.current_packet_reactors = set(
                [reactor for reactor in self.packet_listeners])

            ## Run packet
            response = await self.current_packet.flush()
            if(self.terminate_flag):
                break

            ## Watch response. If fail, unwind cache, reset the proposed packet additions, and flush history. If game end, immediately stop. Otherwise, set everything in stone
            if (response == ResponseStatus.REGULATE_FAIL):
                self.listeners = self.current_listeners
                for listener in self.listeners:
                    listener.requires_cleanup = False
                self.constrainers = self.current_constrainers
                for constrainer in self.constrainers:
                    constrainer.requires_cleanup = False
                self.packet_listeners = self.current_packet_reactors
                for listener in self.packet_listeners:
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
                self.listeners = set([listener for listener in self.listeners if not listener.requires_cleanup])
                self.constrainers = set([constrainer for constrainer in self.constrainers if not constrainer.requires_cleanup])
                self.packet_listeners = set([listener for listener in self.packet_listeners if not listener.requires_cleanup])
