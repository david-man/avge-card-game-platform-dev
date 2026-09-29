from __future__ import annotations

import random

from ...avge_abstracts.AVGECard import AVGECard, AVGESupporterCard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard, ReorderDeck
from ...engine.event import Event, Generator, Packet


class Richard(AVGESupporterCard):
    '''Swap your discard and deck piles entirely; each ends up independently
    reshuffled. Both piles' contents are snapshotted before any transfers happen,
    since transferring discard->deck first would otherwise contaminate the "original
    deck" snapshot needed for the second half of the swap.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="Richard",
                description=Richard.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, Richard):
                raise TypeError("Richard action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            discard = player.card_piles[DeckType.DISCARD]
            deck = player.card_piles[DeckType.DECK]
            _id = AVGEEngineID(acting_card, self.action_type, Richard)

            original_discard = list(discard.cards_holding)
            original_deck = list(deck.cards_holding)
            if not original_discard and not original_deck:
                return

            events: list[Event | Generator] = []
            events.extend(TransferCard(_id, c, discard, deck, env) for c in original_discard)
            events.extend(TransferCard(_id, c, deck, discard, env) for c in original_deck)

            def _shuffle_deck() -> list[AVGECard]:
                return random.sample(deck.cards_holding, len(deck.cards_holding))
            events.append(ReorderDeck(_id, deck, _shuffle_deck, env))

            def _shuffle_discard() -> list[AVGECard]:
                return random.sample(discard.cards_holding, len(discard.cards_holding))
            events.append(ReorderDeck(_id, discard, _shuffle_discard, env))

            env.push_packet(Packet(_id, events))
