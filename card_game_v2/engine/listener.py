from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from ..constants import *
if TYPE_CHECKING:
    from .event import Event, ResponseStatus, Packet


class EventListener(ABC):
    def __init__(self, id: ID, engine_group: EngineGroup):
        self.id = id
        self.engine_group = engine_group
        self.requires_cleanup = False

    @abstractmethod
    def match(self, event: Event) -> bool:
        '''Resolves whether the listener matches an event '''
        pass

    def cleanup(self):
        self.requires_cleanup = True


class EventRegulator(EventListener):
    @abstractmethod
    async def respond(self, event: Event) -> ResponseStatus:
        '''Returns whether this event is allowed to run or not'''
        pass


class EventModifier(EventListener):
    @abstractmethod
    async def modify(self, event: Event) -> None:
        '''Modifies the event accordingly'''
        pass


class EventReactor(EventListener):
    @abstractmethod
    async def react(self, event: Event) -> ResponseStatus | None:
        '''Reacts to the event. Internal reactors may return IGNORE, which makes it so the reactor skips over all future reactors'''
        pass


class PacketReactor(ABC):
    def __init__(self, id: ID):
        self.id = id
        self.requires_cleanup = False

    def cleanup(self):
        self.requires_cleanup = True
    @abstractmethod
    def match(self, packet: Packet) -> bool:
        '''Returns whether the packet matches this reactor'''
        pass

    @abstractmethod
    async def react(self, packet: Packet) -> None:
        '''Reacts to a given packet'''
        pass
