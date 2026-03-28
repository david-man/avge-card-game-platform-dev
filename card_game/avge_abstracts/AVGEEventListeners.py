from ..engine.event_listener import *
from typing import Tuple
from enum import StrEnum
from ..abstract.card import Card


class AVGEEventListenerType(StrEnum):
    ENV = "ENV"
    ATK_1 = 'ATK_1'
    ACTIVE = 'ACTIVE'#an action type for abilities that are phrased like "once per turn, you may..."
    ATK_2 = "ATK_2"
    PASSIVE = "PASSIVE"#an action type exclusively used for stuff like follow-up atks
    NONCHAR = 'NONCHAR'#any non-character card's event listener

type AVGEListenerID = Tuple[Card, AVGEEventListenerType]

class AVGEAbstractEventListener(AbstractEventListener[AVGEListenerID]):
    pass

class AVGEModifier(ModifierEventListener[AVGEListenerID]):
    pass

class AVGEPostcheck(PostCheckEventListener[AVGEListenerID]):
    pass

class AVGEAssessor(AssessorEventListener[AVGEListenerID]):
    pass

class AVGEReactor(ReactorEventListener[AVGEListenerID]):
    pass
