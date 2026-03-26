from __future__ import annotations
from enum import Enum, StrEnum

class QueueStatus(Enum):
    CLOSED = 0
    BUFFERED = 1
    OPEN = 2

class EngineGroup(Enum):
    INTERNAL_1 = 1
    EXTERNAL_PRECHECK_1 = 2
    EXTERNAL_MODIFIERS_1 = 3
    EXTERNAL_PRECHECK_2 = 4
    INTERNAL_2 = 5
    EXTERNAL_PRECHECK_3 = 6
    EXTERNAL_MODIFIERS_2 = 7
    EXTERNAL_PRECHECK_4 = 8
    INTERNAL_3 = 9
    CORE = 10
    INTERNAL_4 = 11
    EXTERNAL_POSTCHECK_1 = 12
    EXTERNAL_REACTORS = 13
    EXTERNAL_POSTCHECK_2 = 14
    INTERNAL_5 = 15
    def succ(self):
        v = self.value + 1
        return EngineGroup(v)
MAX_GROUP = max(member.value for member in EngineGroup)
