from __future__ import annotations
from typing import TYPE_CHECKING, Any
from enum import Enum
from ..constants import *
if TYPE_CHECKING:
    from .event import Event


class HistoricalStatus(Enum):
    PENDING = 0
    IMMUTABLE = 1


class History:
    def __init__(self):
        self._contains_pending = False
        self.records: list[list[tuple[HistoricalStatus, Event]]] = [[]]

    def add_record(self, status: HistoricalStatus, event: Event):
        self.records[-1].append((status, event))
        if (status == HistoricalStatus.PENDING):
            self._contains_pending = True

    def solidify_records(self):
        '''Sets all pending records to immutable'''
        self.records[-1] = [(HistoricalStatus.IMMUTABLE, i)
                            for _, i in self.records[-1]]
        self._contains_pending = False

    def flush_records(self):
        '''Deletes all pending records'''
        self.records[-1] = [(s, i) for s, i in self.records[-1]
                            if s == HistoricalStatus.IMMUTABLE]
        self._contains_pending = False

    def new_chapter(self):
        if (self._contains_pending):
            raise Exception(
                "You cannot create a new chapter while there are still pending records")
        self.records.append([])

    def _get_chapter(self, increment: int = 0) -> list[tuple[HistoricalStatus, Event]]:
        '''Retrieves the latest chapter if increment is not given, and if it is, gives the T - increment chapter'''
        if (increment >= len(self.records) or increment < 0):
            raise IndexError()
        else:
            return self.records[-(increment + 1)]

    def search[T: Event](self,
               event_type: type[T],
               kwargs: dict[str, Any] | None = None,
               increment: int = 0,
               index_to_start: int = 0,
               specific_status: HistoricalStatus = HistoricalStatus.IMMUTABLE,
               attribute_search: bool = False) -> tuple[T | None, int]:
        '''Searches for the earliest event of the given type in a chapter (0 = current, 1 = the one before, etc.)
        matching a set of (not necessarily complete) kwargs, starting at index_to_start.
        If attribute_search is True, kwargs are matched against the event's attributes (via getattr);
        otherwise they're matched against the raw kwargs the event was constructed with.
        Returns (event, index) on a match, or (None, -1) if nothing matches.'''
        if (kwargs is None):
            kwargs = {}
        try:
            chapter = self._get_chapter(increment)
        except IndexError:
            return None, -1
        if (index_to_start >= len(chapter) or index_to_start < 0):
            return None, -1
        for i, (status, event) in enumerate(chapter[index_to_start:], start=index_to_start):
            if (not isinstance(event, event_type)):
                continue
            if (status != specific_status):
                continue
            matched = True
            for key, val in kwargs.items():
                if (attribute_search):
                    if (getattr(event, key, None) != val):
                        matched = False
                        break
                else:
                    if (event._kwargs.get(key, None) != val): #type: ignore
                        matched = False
                        break
            if (not matched):
                continue
            return event, i
        return None, -1
