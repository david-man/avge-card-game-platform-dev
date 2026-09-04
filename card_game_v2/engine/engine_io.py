from __future__ import annotations
from dataclasses import dataclass
from abc import ABC, abstractmethod
import asyncio
from ..constants import User, ID
from typing import Any
from .listener import EventListener
from .record import History, HistoricalStatus


@dataclass
class IOType[T](ABC):
    '''This class is internal. Do NOT override it'''


@dataclass
class UserIOType[T](IOType[T]):
    '''This class defines an IO type object, whereby the inputs are given by the dataclass parameters of this object and the output type is given by the generic'''
    user_for: User


@dataclass
class ListenerReorderIO(IOType[list[EventListener]], ABC):
    listeners: list[EventListener]

    def check_user_io(self, user_input: list[EventListener]):
        return len(user_input) == len(self.listeners) and all([listener in self.listeners for listener in user_input])


class IOException(Exception):
    '''Inherit from this class for your own exceptions'''
    pass


@dataclass
class PendingIO[T]:
    io_obj: IOType[T]
    future_obj: asyncio.Future[T]


class IOManager(ABC):
    def __init__(self):
        self.pending: dict[User, PendingIO[Any]] = {}

    @abstractmethod
    def resolve_users[T](self, io: IOType[T]) -> User:
        """Resolves the appropriate user. Mostly used JUST for resolving the reordering IO"""
        pass

    @abstractmethod
    async def send[T](self, user: User, io: IOType[T]):
        """Send a packet to the appropriate user. Returns the user it sent to"""
        pass

    @abstractmethod
    async def retry[T](self, user: User, io: IOType[T], error: IOException):
        """Retry a packet to the appropriate user."""
        pass

    @abstractmethod
    def deserialize[T](self, io: IOType[T], data: dict[str, Any]) -> T:
        """Convert frontend data into T based on a pending IO. Raises an exception on incorrect data"""
        pass

    async def receive[T](self, user: User, data: Any, history: History | None = None, historical_id: ID | None = None) -> None:
        '''Receives some data and, if formatted correctly, puts it into the future object and automatically places it inside the corresponding historical object as a PENDING transaction IF a history and historical id are provided'''
        from .event import IOEvent  # deferred: event.py imports ListenerReorderIO from this module, so this import must stay out of module scope to avoid a circular import
        pending_io = self.pending.get(user, None)
        if pending_io is not None and not pending_io.future_obj.done():
            try:
                deserialized_data = self.deserialize(pending_io.io_obj, data)
                if (deserialized_data is not None):
                    if (history is not None and historical_id is not None):
                        history.add_record(HistoricalStatus.PENDING,
                                           IOEvent(historical_id, pending_io.io_obj, deserialized_data))
                    pending_io.future_obj.set_result(deserialized_data)
            except IOException as e:
                await self.retry(user, pending_io.io_obj, e)

    async def report[T](self, io: IOType[T]) -> T:
        '''Processes an IO object request and returns the result'''
        future: asyncio.Future[T] = asyncio.get_running_loop().create_future()
        if (isinstance(io, UserIOType)):
            user = io.user_for
        else:
            user = self.resolve_users(io)
        if user in self.pending.keys():
            await self.pending[user].future_obj
        self.pending[user] = PendingIO(io, future)
        try:
            await self.send(user, io)
            return await future
        finally:
            self.pending.pop(user, None)
