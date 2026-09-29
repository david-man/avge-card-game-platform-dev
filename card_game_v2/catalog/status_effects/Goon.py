from __future__ import annotations

from ...avge_abstracts.AVGEEventListener import *
from ...avge_abstracts.AVGECard import *
from ...engine.event import Event
from ...core.EventCatalog import *


class AVGEGoonRetreatCostModifier(AVGEEventModifier):
    '''GOON status: +1 to the retreating character's own ACTIVE_CARD -> BENCH retreat
    leg's cost field (see TransferCard's own cost field and A2's retreat-cost fix) -
    a plain EXTERNAL_MODIFIERS_1 modifier, replacing the old regulator-plus-reactor
    pair this needed when the only things available were an independent affordability
    re-check and a reactor discarding a flat extra token on top of the base reactor's
    own always-full-price discard. No internal clamp needed (this only ever adds) -
    see KikisHeadband's identical -1 modifier for the general reasoning.'''
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.EXTERNAL_MODIFIERS_1)

    def match(self, event: Event) -> bool:
        return (
            isinstance(event, TransferCard)
            and not callable(event.card)
            and not callable(event.deck_from)
            and not callable(event.deck_to)
            and not callable(event.cost)
            and event.id.calling_action == ActionTypes.PLAYER_CHOICE
            and isinstance(event.card, AVGECharacterCard)
            and event.deck_from.deck_type == DeckType.ACTIVE_CARD
            and event.deck_to.deck_type == DeckType.BENCH
            and len(event.card.statuses_attached[StatusEffect.GOON]) > 0
        )

    async def modify(self, event: Event) -> None:
        assert isinstance(event, TransferCard)
        assert not callable(event.cost)
        event.cost += 1


class AVGEGoonStatusChangeReactor(AVGEEventReactor):
    '''GOON status: gaining the first stack grants +20 max HP and +20 current HP;
    losing the last stack removes the +20 max HP again.'''
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.EXTERNAL_REACTORS)

    def match(self, event: Event) -> bool:
        return (
            isinstance(event, AVGECardStatusChange)
            and not callable(event.status)
            and not callable(event.target)
            and event.status == StatusEffect.GOON
        )

    async def react(self, event: Event):
        assert isinstance(event, AVGECardStatusChange)
        assert isinstance(event.target, AVGECharacterCard)
        target = event.target
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        if (event.change == AVGEStatusModifier.ADD
                and len(target.statuses_attached[StatusEffect.GOON]) == 1
                and event.made_modification):
            event.push_event([
                AVGECardMaxHPChangeEvent(_id, target, 20, AVGEAttributeModifier.ADDITIVE, CardType.ALL, self.env),
                AVGECardHPChangeEvent(_id, target, 20, AVGEAttributeModifier.ADDITIVE, CardType.ALL, self.env),
            ])
        elif (event.change == AVGEStatusModifier.REMOVE
                and len(target.statuses_attached[StatusEffect.GOON]) == 0
                and event.made_modification):
            event.push_event([
                AVGECardMaxHPChangeEvent(_id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.ALL, self.env),
            ])
