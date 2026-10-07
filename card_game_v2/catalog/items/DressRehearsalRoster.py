from __future__ import annotations

import random
from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, default_timeout
from ...core.EventCatalog import AVGEEnergyTransfer, TransferCard, ReorderDeck
from ...core.AVGEIOManager import CardSelectionQuery, Notification
from ...engine.event import Event, Generator, Packet


class DressRehearsalRoster(AVGEItemCard):
    '''Discard 1 energy from one of your in-play characters, then shuffle up to
    3 random discard cards into your deck.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="DressRehearsalRoster",
                description=DressRehearsalRoster.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, DressRehearsalRoster):
                raise TypeError("DressRehearsalRoster action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            deck = player.card_piles[DeckType.DECK]
            discard = player.card_piles[DeckType.DISCARD]

            in_play: list[AVGECharacterCard] = [
                c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            _id = AVGEEngineID(acting_card, self.action_type, DressRehearsalRoster)
            charged = [c for c in in_play if c.energy_tokens]
            if not charged:
                await env.report(Notification(
                    acting_card.owner,
                    "Dress Rehearsal Roster needs at least 1 energy in play.", default_timeout,
                ), _id)
                return
            selected = await env.report(CardSelectionQuery(
                acting_card.owner,
                "Dress Rehearsal Roster: Choose a character to discard 1 energy from.",
                1,
                cast(list[AVGECard], charged),
                cast(list[AVGECard], in_play),
                False,
                False,
            ), _id)

            events: list[Event | Generator] = []
            chosen = selected[0]
            assert isinstance(chosen, AVGECharacterCard)
            events.append(AVGEEnergyTransfer(_id, chosen, env, env))

            cards_to_shuffle = list(discard.cards_holding)
            if len(cards_to_shuffle) > 3:
                cards_to_shuffle = random.sample(cards_to_shuffle, 3)

            for card_to_shuffle in cards_to_shuffle:
                events.append(TransferCard(_id, card_to_shuffle, discard, deck, env))

                def _reordering_with_chosen_shuffled_in(deck: AVGEDeck = deck, chosen: AVGECard = card_to_shuffle):
                    def gen() -> list[AVGECard]:
                        rest = [c for c in deck.cards_holding if c is not chosen]
                        idx = random.randint(0, len(rest))
                        rest.insert(idx, chosen)
                        return rest
                    return gen

                events.append(ReorderDeck(_id, deck, _reordering_with_chosen_shuffled_in(), env))

            env.push_packet(Packet(_id, events))
