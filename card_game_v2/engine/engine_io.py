from __future__ import annotations
from dataclasses import dataclass
from abc import ABC, abstractmethod
import asyncio
from ..constants import User
from typing import Any
from .listener import EventListener, IOListener


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

@dataclass
class IOListenerReorderIO[T](IOType[list[IOListener]], ABC):
    listeners : list[IOListener]
    io_obj : IOType[T]
    def check_user_io(self, user_input: list[IOListener]):
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

    async def receive[T](self, user: User, data: Any) -> None:
        '''Receives some data and, if formatted correctly, puts it into the future object'''
        pending_io = self.pending.get(user, None)
        if pending_io is not None and not pending_io.future_obj.done():
            try:
                deserialized_data = self.deserialize(pending_io.io_obj, data)
                if (deserialized_data is not None):
                    pending_io.future_obj.set_result(deserialized_data)
            except IOException as e:
                await self.retry(user, pending_io.io_obj, e)

    async def _dispatch[T](self, user: User, io: IOType[T]) -> T:
        '''Sends an IO object to a specific user and awaits their response'''
        future: asyncio.Future[T] = asyncio.get_running_loop().create_future()
        if user in self.pending.keys():
            await self.pending[user].future_obj
        self.pending[user] = PendingIO(io, future)
        try:
            await self.send(user, io)
            return await future
        finally:
            self.pending.pop(user, None)

    async def report[T](self, io: IOType[T]) -> T:
        '''Processes an IO object request and returns the result'''
        if (isinstance(io, UserIOType)):
            user = io.user_for
        else:
            user = self.resolve_users(io)
        return await self._dispatch(user, io)

    async def broadcast(self, io: IOType[None]) -> None:
        '''Specific broadcast request that blasts an IO object to all users'''
        await asyncio.gather(*(self._dispatch(user, io) for user in User))

