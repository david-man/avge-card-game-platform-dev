from __future__ import annotations

from ...avge_abstracts.AVGEEventListener import *
from ...avge_abstracts.AVGECard import *
from ...constants import ResponseStatus
from ...engine.event import Event
from ...core.EventCatalog import *


class AVGEGoonRetreatCostRegulator(AVGEEventRegulator):
    '''GOON status: retreating (active -> bench) costs 1 additional energy on top of the
    card's own retreat_cost. Checked independently against the retreating card's own
    energy/cost, so it doesn't depend on however the base retreat-cost validity check
    is wired.'''
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_1)

    def match(self, event: Event) -> bool:
        return (
            isinstance(event, TransferCard)
            and not callable(event.card)
            and not callable(event.deck_from)
            and not callable(event.deck_to)
            and event.id.calling_action == ActionTypes.PLAYER_CHOICE
            and isinstance(event.card, AVGECharacterCard)
            and event.deck_from.deck_type == DeckType.ACTIVE_CARD
            and event.deck_to.deck_type == DeckType.BENCH
            and len(event.card.statuses_attached[StatusEffect.GOON]) > 0
        )

    async def respond(self, event: Event) -> ResponseStatus:
        assert isinstance(event, TransferCard)
        assert isinstance(event.card, AVGECharacterCard)
        if len(event.card.energy_tokens) < event.card.retreat_cost + 1:
            return ResponseStatus.REGULATE_FAIL
        return ResponseStatus.REGULATE_PASS


class AVGEGoonRetreatCostReactor(AVGEEventReactor):
    '''GOON status: discards 1 additional energy on top of whatever the base retreat
    reactor already discards, for the same retreat.'''
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.INTERNAL_3)

    def match(self, event: Event) -> bool:
        return (
            isinstance(event, TransferCard)
            and not callable(event.card)
            and not callable(event.deck_from)
            and not callable(event.deck_to)
            and event.id.calling_action == ActionTypes.PLAYER_CHOICE
            and isinstance(event.card, AVGECharacterCard)
            and event.deck_from.deck_type == DeckType.ACTIVE_CARD
            and event.deck_to.deck_type == DeckType.BENCH
            and len(event.card.statuses_attached[StatusEffect.GOON]) > 0
        )

    async def react(self, event: Event):
        assert isinstance(event, TransferCard)
        assert isinstance(event.card, AVGECharacterCard)
        event.push_event([AVGEEnergyTransfer(
            AVGEEngineID(None, ActionTypes.ENV, None),
            event.card,
            self.env,
            self.env,
        )])


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
