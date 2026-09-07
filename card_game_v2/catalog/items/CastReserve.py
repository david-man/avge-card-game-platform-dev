from __future__ import annotations

import random
from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard, ReorderDeck
from ...core.AVGEIOManager import CardSelectionQuery
from ...engine.event import Event, Generator, Packet


class CastReserve(AVGEItemCard):
    '''Owner may choose 3 uniquely-typed items from their deck (or decline entirely);
    if they do, the OPPONENT picks 2 of those 3 to shuffle back into the deck at random
    positions, and the leftover one goes to the owner's hand.

    v1 offers the full (possibly type-duplicated) item list and re-prompts if the
    owner's 3 picks aren't uniquely typed; v2 has no retry loop for
    `CardSelectionQuery`, so this instead only ever *offers* one representative item
    per distinct type up front - any 3 picks from that pre-filtered list are
    automatically type-unique, with the same end result and no possibility of an
    invalid submission. If fewer than 3 distinct item types exist in the deck, the card
    has nothing valid to offer and is a no-op.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        opponent = env.get_opponent(self.owner)
        deck = player.card_piles[DeckType.DECK]
        hand = player.card_piles[DeckType.HAND]

        seen_types: set[type[AVGECard]] = set()
        unique_item_choices: list[AVGEItemCard] = []
        for c in deck.cards_holding:
            if isinstance(c, AVGEItemCard) and type(c) not in seen_types:
                seen_types.add(type(c))
                unique_item_choices.append(c)
        if len(unique_item_choices) < 3:
            return

        _id = AVGEEngineID(self, ActionTypes.NONCHAR, CastReserve)
        player_picked = await env.report(CardSelectionQuery(
            self.owner,
            "Cast Reserve: Either choose 3 unique item cards from your deck or choose none at all.",
            3,
            cast(list[AVGECard], unique_item_choices),
            list(deck.cards_holding),
            True,
            False,
        ), _id)
        if not player_picked:
            return

        selected_three = player_picked
        opponent_picked = await env.report(CardSelectionQuery(
            opponent.id,
            "Cast Reserve: Choose 2 of the chosen items to shuffle back.",
            2,
            selected_three,
            selected_three,
            False,
            False,
        ), _id)

        card_to_hand = next(c for c in selected_three if c not in opponent_picked)
        shuffle_back = tuple(opponent_picked)

        events: list[Event | Generator] = [TransferCard(_id, card_to_hand, deck, hand, env)]

        def _reordering_with_both_shuffled_in(deck: AVGEDeck = deck, shuffle_back: tuple[AVGECard, ...] = shuffle_back):
            def gen() -> list[AVGECard]:
                rest = [c for c in deck.cards_holding if c not in shuffle_back]
                for chosen in shuffle_back:
                    idx = random.randint(0, len(rest))
                    rest.insert(idx, chosen)
                return rest
            return gen

        events.append(ReorderDeck(_id, deck, _reordering_with_both_shuffled_in(), env))
        env.push_packet(Packet(_id, events))
