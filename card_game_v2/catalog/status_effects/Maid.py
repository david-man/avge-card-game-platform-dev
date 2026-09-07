from __future__ import annotations

from ...avge_abstracts.AVGEEventListener import *
from ...avge_abstracts.AVGECard import *
from ...engine.event import Event
from ...core.EventCatalog import *


class AVGEMaidDamageShieldModifier(AVGEEventModifier):
    '''MAID status: a character carrying MAID is immune to attack damage of 10 or less.
    Must be registered after AVGEWeaknessModifier (both INTERNAL_1) in core_listeners()
    so this checks the post-weakness-crit magnitude, matching v1's actual attach order
    (Weakness modifier attached before Maid's on every AVGECardHPChange) - a crit that
    pushes a small hit over 10 is NOT shielded, by design/parity, not by accident.'''
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_1)

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

    async def modify(self, event: Event):
        assert isinstance(event, AVGECardHPChangeEvent)
        assert not callable(event.magnitude)
        event.modify_magnitude(-event.magnitude)
        await self.env.broadcast(BroadcastIO("Maid: This character is immune to all damage <= 10", default_timeout))
