from __future__ import annotations
from inspect import signature
from collections.abc import Callable
from collections import deque
from typing import Any, TYPE_CHECKING
from ..constants import *
from abc import ABC, abstractmethod
from .engine_io import ListenerReorderIO
from .listener import EventRegulator, EventModifier, EventReactor
from .record import HistoricalStatus
if TYPE_CHECKING:
    from .engine import Engine
    from .listener import EventListener
    from .engine_io import IOType

type Generator = Callable[[], list[Event | Generator]]

ARRANGEABLE_GROUPS = [EngineGroup.EXTERNAL_MODIFIERS_1, EngineGroup.EXTERNAL_MODIFIERS_2,
                      EngineGroup.EXTERNAL_MODIFIERS_3, EngineGroup.EXTERNAL_REACTORS]
MAX_GROUP = max(member.value for member in EngineGroup)


class Event(ABC):
    def __init__(self, id: ID, **kwargs: Any) -> None:
        self.id = id
        self._parent_packet: Packet | None = None
        self._kwargs = kwargs
        for kwarg in self._kwargs:
            setattr(self, kwarg, self._kwargs[kwarg])
        self.scrachboard: dict[str, Any] = {}
        self.requires_rollback = False

    def _resolve_kwargs(self):
        '''Resolves all lambda keyword arguments'''
        for kwarg in self._kwargs.keys():
            if callable(self._kwargs[kwarg]):
                if (len(signature(self._kwargs[kwarg]).parameters) == 0):
                    setattr(self, kwarg, self._kwargs[kwarg]())
                else:
                    raise Exception(
                        "You inputted a non-zero argument lambda as a kwarg for an event, which is not allowed")
            else:
                setattr(self, kwarg, self._kwargs[kwarg])

    @abstractmethod
    async def act(self) -> None:
        '''Defines what the event does'''
        pass

    @abstractmethod
    def rollback(self) -> None:
        '''Defines how exactly to roll back the event assuming all proposed events/packets, all cache changes (implemented by AVGEEnvironment), and all listener changes are internally reverted'''
        pass

    # External API endpoints

    def push_event(self, event: Event | Generator | list[Event | Generator]):
        '''Adds a event or list of events to the front of the packet such that it runs right after the current one'''
        assert self._parent_packet is not None
        self._parent_packet.push_event(event)

    async def interrupt(self, events: Event | Generator | list[Event | Generator]) -> ResponseStatus:
        '''Pauses this event to immediately run the given event(s) first, following the same
        rules/flow as packet flush, then resumes right where it left off.'''
        assert self._parent_packet is not None
        return await self._parent_packet.interrupt(events)

    def append_event(self, event: Event | Generator | list[Event | Generator]):
        '''Adds a event or list of events to the back of the packet such that it runs after everything else currently in the packet'''
        assert self._parent_packet is not None
        self._parent_packet.append_event(event)


class Change(Enum):
    REMOVE = 0
    ADD = 1


class _InterruptRegulateFail(Exception):
    '''Internal control-flow signal raised by interrupt() when one of the events it ran fails.
    It unwinds through whatever listener code (and however many nested interrupts) triggered it,
    all the way up to flush(), since only flush() knows it's safe to roll everything back.'''

    def __init__(self, response: ResponseStatus):
        self.response = response


class Packet:
    def __init__(self, id: ID, element: list[Event | Generator]):
        self.id = id
        self._call_stack: list[deque[Event | Generator]] = [deque(element)]
        # stores events that have gone through properly
        self.event_log: list[Event] = []
        self._rollback_log: list[Event] = []
        self.current_event: Event | None = None
        self._engine : Engine | None = None

        self._requested_event_pushes : list[Event | Generator] = []
        self._requested_event_appends : list[Event | Generator] = []

    def _rollback_all(self):
        for event in reversed(self._rollback_log):
            event.rollback()

    async def _flush_event(self, event : Event) -> ResponseStatus:
        '''Runs through an event'''
        assert self._engine is not None
        for group in EngineGroup:
            if (group == EngineGroup.CORE):
                await event.act()
                event.requires_rollback = True
                self._rollback_log.append(event)
            else:
                # Step 1: Gather the required listeners for the required group
                ordering: list[EventListener] = [
                    listener for listener in self._engine.listeners if not listener.requires_cleanup and listener.engine_group == group and listener.match(event)
                ]
                # Step 2: Cull listeners based on constrainers
                ordering = [listener for listener in ordering if not any(
                    [constrainer.match(listener) for constrainer in self._engine.constrainers])]
                # Step 3: Rearrange order if necessary
                if (group in ARRANGEABLE_GROUPS and len(ordering) > 1):
                    ordering = await self._engine.io_manager.report(ListenerReorderIO(ordering))
                # Step 4: Walk through ordering
                for listener in ordering:
                    if (isinstance(listener, EventRegulator)):
                        resp = await listener.respond(event)
                        assert resp in [ResponseStatus.REGULATE_FAIL,  ResponseStatus.REGULATE_PASS, ResponseStatus.REGULATE_IGNORE]
                        if (resp != ResponseStatus.REGULATE_PASS):
                            #early breakout if no pass
                            return resp
                    elif (isinstance(listener, EventModifier)):
                        await listener.modify(event)
                    elif (isinstance(listener, EventReactor)):
                        resp = await listener.react(event)
                        if(resp == ResponseStatus.REACTOR_SKIP):
                            return resp
                        else:
                            assert resp is None
        #  If you've gotten here, return Success
        return ResponseStatus.SUCCESS

    async def _run_queue(self, queue: deque[Event | Generator]) -> ResponseStatus:
        '''Resolves and runs every event/generator in queue, in order, using the exact same
        per-event pipeline as flush(): generator expansion, kwarg resolution, the full listener
        group walk, and event_log/history bookkeeping on success.

        Does not roll back on failure - the caller decides that, since a failure here may need
        to unwind state belonging to an outer, still-paused event too (see interrupt()).'''
        assert self._engine is not None
        while queue and not self._engine.terminate_flag:
            # keep trying to resolve the first element until it is an event, and then set it to be the current event
            next_event = queue.popleft()
            while callable(next_event):
                event_list = next_event()
                if (len(event_list) == 0):
                    next_event = None
                else:
                    next_event = event_list.pop(0)
                    for e in reversed(event_list):
                        queue.appendleft(e)
            self.current_event = next_event

            self._requested_event_appends = []
            self._requested_event_pushes = []
            # fully resolve the keyword arguments for current event and then run it
            if self.current_event is not None:
                self.current_event._resolve_kwargs()  # type: ignore
                self.current_event._parent_packet = self  # type: ignore
                response = await self._flush_event(self.current_event)
            else:
                response = None

            if (response is not None):
                if (response == ResponseStatus.REGULATE_FAIL):
                    return response

                elif (response == ResponseStatus.REGULATE_IGNORE):
                    #don't add to logs or history if response is ignore, since we, in effect, have purely skipped the event
                    continue

                else:
                    assert self.current_event is not None
                    self.event_log.append(self.current_event)
                    self._engine.history.add_record(
                        HistoricalStatus.PENDING, self.current_event)
                    queue = self._call_stack[-1]
                    for e in reversed(self._requested_event_pushes):  # type: ignore
                        queue.appendleft(e)
                    for e in (self._requested_event_appends):  # type: ignore
                        queue.append(e)
        return ResponseStatus.SUCCESS

    async def flush(self) -> ResponseStatus:
        assert self._engine is not None
        try:
            response = await self._run_queue(self._call_stack[-1])
        except _InterruptRegulateFail as failure:
            response = failure.response

        if (response == ResponseStatus.REGULATE_FAIL):
            self._rollback_all()

        return response

    # External API endpoints

    async def interrupt(self, events: Event | Generator | list[Event | Generator]) -> ResponseStatus:
        '''Pauses whichever event is currently running through this packet to immediately run
        `events` first, following the exact same rules/flow as flush() (generator expansion,
        listener groups, event_log/history bookkeeping). Once the interrupting events finish,
        the original event resumes exactly where it left off.

        Safe to call from within an event's act(), or from a regulator/modifier/reactor
        listening to it - and safe to call again from within an interrupting event itself
        (nested interrupts), since each call only pauses/resumes its own caller.'''
        assert self._engine is not None
        event_list: list[Event | Generator] = events if isinstance(events, list) else [events]  # type: ignore

        interrupt_queue: deque[Event | Generator] = deque(event_list)
        paused_event = self.current_event
        paused_requested_event_pushes = self._requested_event_pushes
        paused_requested_event_appends = self._requested_event_appends
        self._requested_event_pushes = []
        self._requested_event_appends = []
        self._call_stack.append(interrupt_queue)
        try:
            response = await self._run_queue(interrupt_queue)
        finally:
            self._call_stack.pop()
            self.current_event = paused_event
            self._requested_event_appends = paused_requested_event_appends
            self._requested_event_pushes = paused_requested_event_pushes

        if (response == ResponseStatus.REGULATE_FAIL):
            # can't roll back here: the paused event above us may itself still need unwinding,
            # and only flush() at the very top knows once everything has stopped moving
            raise _InterruptRegulateFail(response)

        return response

    def push_event(self, event: Event | Generator | list[Event | Generator]):
        '''Adds a event or list of events to the front of the currently executing queue
        (the packet's main queue, or the innermost active interrupt's queue) such that
        it runs right after the current one'''
        self._requested_event_pushes.append(event) if not isinstance(event, list) else self._requested_event_pushes.extend(event) # type: ignore

    def append_event(self, event: Event | Generator | list[Event | Generator]):
        '''Adds a event or list of events to the back of the currently executing queue
        (the packet's main queue, or the innermost active interrupt's queue) such that
        it runs after everything else in that queue'''
        self._requested_event_appends.append(event) if not isinstance(event, list) else self._requested_event_appends.extend(event) # type: ignore

    def set_engine(self, engine : Engine):
        self._engine = engine


class IOEvent(Event):
    '''This class exists PURELY to help store historical records about IO transactions'''

    def __init__[T](self, id: ID, io_obj: IOType[T], result: T):
        super().__init__(id, io_obj=io_obj, result=result)
        self.io_obj = io_obj
        self.result = result

    async def act(self):
        raise Exception("You should never be running an IOEvent")

    def rollback(self):
        raise Exception("You should never be rolling back an IOEvent")