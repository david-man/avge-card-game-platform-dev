from __future__ import annotations

from typing import cast

from ...avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGESupporterCard, CardType
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard, ReorderDeck
from ...core.AVGEIOManager import CardSelectionQuery, StringSelectionQuery, RevealCards
from ...engine.event import Event, Generator, Packet


class Victoria(AVGESupporterCard):
    '''Choose a CardType (any but ALL), then optionally choose a deck character of
    that type to reveal and place on top of your deck, then optionally choose a
    second, different, matching character to reveal and take to hand. Same
    top-deck/hand shape as Lucas's supporter, independently implemented (gated by an
    explicit type choice here, rather than "not currently on your board").'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        deck = player.card_piles[DeckType.DECK]
        hand = player.card_piles[DeckType.HAND]
        _id = AVGEEngineID(self, ActionTypes.NONCHAR, Victoria)

        type_options = [t.value for t in CardType if t != CardType.ALL]
        chosen_type_str = (await env.report(StringSelectionQuery(
            self.owner,
            "Victoria: Choose a card type.",
            1,
            type_options,
            type_options,
            False,
            False,
        ), _id))[0]
        selected_type = CardType(chosen_type_str)

        matching: list[AVGECharacterCard] = [
            c for c in deck.cards_holding if isinstance(c, AVGECharacterCard) and c.card_type == selected_type
        ]

        deck_card: AVGECharacterCard | None = None
        if matching:
            picked = await env.report(CardSelectionQuery(
                self.owner,
                "Victoria: Choose a matching deck character to reveal and place on top of your deck.",
                1,
                cast(list[AVGECard], matching),
                cast(list[AVGECard], matching),
                True,
                False,
            ), _id)
            if picked:
                assert isinstance(picked[0], AVGECharacterCard)
                deck_card = picked[0]

        remaining_for_hand = matching
        if deck_card is not None:
            remaining_for_hand = [c for c in matching if c is not deck_card]

        hand_card: AVGECharacterCard | None = None
        if remaining_for_hand:
            picked = await env.report(CardSelectionQuery(
                self.owner,
                "Victoria: Choose another matching deck character to reveal and take to your hand.",
                1,
                cast(list[AVGECard], remaining_for_hand),
                cast(list[AVGECard], remaining_for_hand),
                True,
                False,
            ), _id)
            if picked:
                assert isinstance(picked[0], AVGECharacterCard)
                hand_card = picked[0]

        events: list[Event | Generator] = []
        if deck_card is not None:
            await env.broadcast(RevealCards(self.owner, [deck_card]))
            chosen = deck_card

            def _make_order(deck: AVGEDeck = deck, chosen: AVGECharacterCard = chosen):
                def gen() -> list[AVGECard]:
                    rest = [c for c in deck.cards_holding if c is not chosen]
                    return [chosen] + rest
                return gen
            events.append(ReorderDeck(_id, deck, _make_order(), env))

        if hand_card is not None:
            await env.broadcast(RevealCards(self.owner, [hand_card]))
            events.append(TransferCard(_id, hand_card, deck, hand, env))

        if events:
            env.push_packet(Packet(_id, events))
