from __future__ import annotations

import random
from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, default_timeout
from ...core.EventCatalog import TransferCard, ReorderDeck
from ...core.AVGEIOManager import CardSelectionQuery, Notification
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

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="CastReserve",
                description=CastReserve.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, CastReserve):
                raise TypeError("CastReserve action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            opponent = env.get_opponent(acting_card.owner)
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

            _id = AVGEEngineID(acting_card, self.action_type, CastReserve)
            # allows_none=True only means "0 is a valid answer" - the query still lets a client submit
            # 1 or 2 cards, which would leave the opponent's follow-up query with fewer than 3 cards to
            # work from (and next() below with nothing left to find). So keep asking until the answer
            # is exactly 3 or none.
            while True:
                player_picked = await env.report(CardSelectionQuery(
                    acting_card.owner,
                    "Cast Reserve: Choose exactly 3 unique item cards from your deck, or choose none at all.",
                    3,
                    cast(list[AVGECard], unique_item_choices),
                    list(deck.cards_holding),
                    True,
                    False,
                ), _id)
                if len(player_picked) in (0, 3):
                    break
                await env.report(Notification(
                    acting_card.owner, "Cast Reserve: choose exactly 3 cards, or none at all.", default_timeout,
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
