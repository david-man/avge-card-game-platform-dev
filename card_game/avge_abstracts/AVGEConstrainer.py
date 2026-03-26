from ..engine.constrainer import *
from typing import Tuple
from enum import StrEnum
from ..abstract.card import Card

class AVGEConstrainerType(StrEnum):
    ENV = "ENV"
    ATK_1 = 'ATK_1'
    ACTIVE = 'ACTIVE'#an action type for abilities that are phrased like "once per turn, you may..."
    ATK_2 = "ATK_2"
    PASSIVE = "PASSIVE"#an action type exclusively used for stuff like follow-up atks


type AVGEConstrainerID = Tuple[Card, AVGEConstrainerType]
class AVGEConstraint(Constraint[AVGEConstrainerID]):
    pass