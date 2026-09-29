from __future__ import annotations

from ...avge_abstracts.AVGEEventListener import *
from ...avge_abstracts.AVGECard import *
from ...engine.event import Event
from ...core.EventCatalog import *


class AVGEMaidDamageShieldRegulator(AVGEEventRegulator):
    '''MAID status: a character carrying MAID is immune to attack damage of 10 or less.
    Registered at INTERNAL_2, strictly after AVGEWeaknessModifier's INTERNAL_1 and before
    every external modifier. Ignoring the event prevents a later positive modifier from reviving
    damage that immunity already blocked.'''
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_2)

    def _eligible(self, event: Event) -> bool:
        if not isinstance(event, AVGECardHPChangeEvent):
            return False
        if callable(event.target_card) or callable(event.magnitude) or callable(event.modifier_type) or callable(event.change_type):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.id.calling_action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
            return False
        if event.magnitude > 10:
            return False
        if event.change_type == CardType.ALL:
            return False
        return len(event.target_card.statuses_attached[StatusEffect.MAID]) > 0

    def match(self, event: Event) -> bool:
        return self._eligible(event)

    async def respond(self, event: Event) -> ResponseStatus:
        await self.env.broadcast(BroadcastIO("Maid: This character is immune to all damage <= 10", default_timeout))
        return ResponseStatus.REGULATE_IGNORE
