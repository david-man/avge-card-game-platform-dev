from __future__ import annotations
from typing import TYPE_CHECKING
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

    def retrieve_chapter(self, increment: int = 0):
        '''Retrieves the latest chapter if increment is not given, and if it is, retries the T - increment chapter'''
        if (increment >= len(self.records) or increment < 0):
            raise IndexError()
        else:
            return self.records[-(increment + 1)]
