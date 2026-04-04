from __future__ import annotations

from ..engine.event import Event
from ..engine.event_listener import *
from typing import TYPE_CHECKING
from ..constants import *

if TYPE_CHECKING:
    from ..abstract.card import Card
    from .AVGEEnvironment import AVGEEnvironment

class AVGEEvent(Event):
    def __init__(self,
                 catalyst_action : ActionTypes,
                 caller_card : Card | None,
                 **kwargs):
        super().__init__(catalyst_action = catalyst_action, caller_card = caller_card, **kwargs)
        self.catalyst_action = catalyst_action
        self.caller_card = caller_card
        self.env : AVGEEnvironment = self.caller_card.env if not self.caller_card is None else None
        self.temp_cache = {}