from ..engine.constrainer import *
from typing import Tuple
from enum import StrEnum
from .AVGEEvent import AVGEEvent
from ..constants import AVGEEngineID
class AVGEConstrainerType(StrEnum):
    ENV = "ENV"
    ATK_1 = 'ATK_1'
    ACTIVE = 'ACTIVE'#an action type for abilities that are phrased like "once per turn, you may..."
    ATK_2 = "ATK_2"
    PASSIVE = "PASSIVE"#an action type exclusively used for stuff like follow-up atks

class AVGEConstraint(Constraint[AVGEEvent]):
    def __init__(self, identifier : AVGEEngineID):
        super().__init__()
        self.identifier= identifier