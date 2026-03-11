from ..engine.event import Event
from ..engine.event_listener import *
from ..abstract.card import Card
from ..constants import *
class AVGEEvent(Event):
    def __init__(self, flags : list[Flag],
                 catalyst_action : ActionTypes,
                 caller_card : Card):
        super().__init__(flags)
        self.catalyst_action = catalyst_action
        self.caller_card = caller_card