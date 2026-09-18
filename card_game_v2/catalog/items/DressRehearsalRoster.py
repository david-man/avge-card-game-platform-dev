from __future__ import annotations

import random
from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, default_timeout
from ...core.EventCatalog import AVGEEnergyTransfer, TransferCard, ReorderDeck
from ...core.AVGEIOManager import CardSelectionQuery, Notification
from ...engine.event import Event, Generator, Packet


class DressRehearsalRoster(AVGEItemCard):
    '''Discard 1 energy each from 2 (not necessarily distinct) own in-play characters,
    then reshuffle up to 4 random discard cards into the deck at random positions.
    Requires at least 2 total energy among your in-play characters. Unlike v1, which
    re-prompts on an invalid combination (e.g. picking the same character twice without
    it having 2 energy), v2 has no retry loop for `CardSelectionQuery` - instead this
    just trusts the picks and relies on `AVGEEnergyTransfer`'s own built-in no-op-if-
    empty behavior, so an under-resourced pick simply discards less than 2 total energy
    rather than being rejected.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        deck = player.card_piles[DeckType.DECK]
        discard = player.card_piles[DeckType.DISCARD]

        in_play: list[AVGECharacterCard] = [
            c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
        ] + [
            c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
        ]
        _id = AVGEEngineID(self, ActionTypes.NONCHAR, DressRehearsalRoster)
        total_energy = sum(len(c.energy_tokens) for c in in_play)
        if total_energy < 2:
            await env.report(Notification(
                self.owner,
                "Not enough total energy in play for Dress Rehearsal Roster...", default_timeout,
            ), _id)
            return
        selected = await env.report(CardSelectionQuery(
            self.owner,
            "Dress Rehearsal Roster: Choose 2 (not necessarily distinct) characters to discard energy from.",
            2,
            cast(list[AVGECard], in_play),
            cast(list[AVGECard], in_play),
            False,
            True,
        ), _id)

        events: list[Event | Generator] = []
        for chosen in selected:
            assert isinstance(chosen, AVGECharacterCard)
            events.append(AVGEEnergyTransfer(_id, chosen, env, env))

        cards_to_shuffle = list(discard.cards_holding)
        if len(cards_to_shuffle) > 4:
            cards_to_shuffle = random.sample(cards_to_shuffle, 4)

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
