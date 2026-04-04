from __future__ import annotations
from enum import Enum, StrEnum

class QueueStatus(Enum):
    CLOSED = 0
    BUFFERED = 1
    OPEN = 2

class EngineGroup(Enum):
    EXTERNAL_MODIFIERS_1 = 0#used if you want something to come before internal prechecks
    INTERNAL_1 = 1#all internal prechecks & the weaknesses are calculated in here
    EXTERNAL_PRECHECK_1 = 2
    EXTERNAL_MODIFIERS_2 = 3#debuffs all go here
    EXTERNAL_MODIFIERS_3 = 4#any
    EXTERNAL_PRECHECK_2 = 5
    INTERNAL_2 = 6#i honestly don't think anything goes in here tbh
    CORE = 7
    EXTERNAL_POSTCHECK_1 = 8
    INTERNAL_3 = 9
    EXTERNAL_REACTORS = 10
    INTERNAL_4 = 11
    def succ(self):
        v = self.value + 1
        return EngineGroup(v)
MAX_GROUP = max(member.value for member in EngineGroup)
