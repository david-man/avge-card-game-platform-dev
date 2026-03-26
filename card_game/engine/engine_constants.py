from __future__ import annotations
from enum import Enum, StrEnum

class QueueStatus(Enum):
    CLOSED = 0
    BUFFERED = 1
    OPEN = 2

class EngineGroup(Enum):
    INTERNAL_1 = 1
    FIRST_EXTERNAL_PRECHECK = 2
    EXTERNAL_MODIFIERS = 3
    SECOND_EXTERNAL_PRECHECK = 4
    INTERNAL_2 = 5
    CORE = 6
    INTERNAL_3 = 7
    FIRST_EXTERNAL_POSTCHECK = 8
    EXTERNAL_REACTORS = 9
    SECOND_EXTERNAL_POSTCHECK = 10
    INTERNAL_4 = 11
    def succ(self):
        v = self.value + 1
        return EngineGroup(v)
