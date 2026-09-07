from __future__ import annotations

import random
from ...avge_abstracts.AVGEEventListener import *
from ...avge_abstracts.AVGECard import *
from ...avge_abstracts.AVGEDeck import AVGEDeck, AVGEToolHolder
from ...engine.event import Event
from ...core.EventCatalog import *


class AVGEArrangerStatusReactor(AVGEEventReactor):
    '''ARRANGER status: whenever a carrying character takes damage, or has an attached
    tool discarded, offers to shuffle a random card from their discard back into their
    deck at a random position.'''
    def __init__(self, env : AVGEEnvironment):
        super().__init__(AVGEEngineID(None, ActionTypes.ENV, None), env, EngineGroup.EXTERNAL_REACTORS)

    def _affected_character(self, event: Event) -> AVGECharacterCard | None:
        if isinstance(event, AVGECardHPChangeEvent):
            if callable(event.modifier_type) or callable(event.target_card):
                return None
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return None
            return event.target_card

        if isinstance(event, TransferCard):
            if callable(event.card) or callable(event.deck_from) or callable(event.deck_to):
                return None
            if not isinstance(event.card, AVGEToolCard):
                return None
            if event.deck_to.deck_type != DeckType.DISCARD:
                return None
            if not isinstance(event.deck_from, AVGEToolHolder):
                return None
            return event.deck_from.parent_card

        return None

    def match(self, event: Event) -> bool:
        character = self._affected_character(event)
        return character is not None and len(character.statuses_attached[StatusEffect.ARRANGER]) > 0

    async def react(self, event: Event):
        character = self._affected_character(event)
        assert character is not None
        player = self.env.players[character.owner]
        discard = player.card_piles[DeckType.DISCARD]
        deck = player.card_piles[DeckType.DECK]
        if len(discard) == 0:
            return

        _id = AVGEEngineID(character, ActionTypes.PASSIVE, None)
        choice = await self.env.report(StringSelectionQuery(
            character.owner,
            "Arranger: Shuffle a random card from discard into deck?",
            1,
            ["Yes", "No"],
            ["Yes", "No"],
            False,
            False,
        ), _id)
        if choice[0] != "Yes":
            return

        chosen = random.choice(list(discard.cards_holding))

        def _reordering_with_chosen_shuffled_in(deck: AVGEDeck = deck, chosen: AVGECard = chosen):
            def gen() -> list[AVGECard]:
                rest = [c for c in deck.cards_holding if c is not chosen]
                idx = random.randint(0, len(rest))
                rest.insert(idx, chosen)
                return rest
            return gen

        event.push_event([
            TransferCard(_id, chosen, discard, deck, self.env),
            ReorderDeck(_id, deck, _reordering_with_chosen_shuffled_in(), self.env),
        ])
