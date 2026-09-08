from __future__ import annotations

from typing import cast

from ...avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGESupporterCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard, ReorderDeck
from ...core.AVGEIOManager import CardSelectionQuery, RevealCards
from ...engine.event import Event, Generator, Packet


class Lucas(AVGESupporterCard):
    '''Choose a deck character whose type isn't currently on your board - reveal it
    and place it on top of your deck (**not** to hand - confirmed against v1 source,
    correcting the survey gloss which said both picks go to hand). Then, optionally,
    choose a *second* such character (excluding the first pick's own type too) to
    reveal and take directly to hand.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        deck = player.card_piles[DeckType.DECK]
        hand = player.card_piles[DeckType.HAND]
        _id = AVGEEngineID(self, ActionTypes.NONCHAR, Lucas)

        board_chars: list[AVGECharacterCard] = [
            c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
        ] + [
            c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
        ]
        board_types = {c.card_type for c in board_chars}

        eligible: list[AVGECharacterCard] = [
            c for c in deck.cards_holding if isinstance(c, AVGECharacterCard) and c.card_type not in board_types
        ]

        top_deck_card: AVGECharacterCard | None = None
        if eligible:
            picked = await env.report(CardSelectionQuery(
                self.owner,
                "Lucas: Choose a deck character (a type not currently on your board) to reveal and place on top of your deck.",
                1,
                cast(list[AVGECard], eligible),
                cast(list[AVGECard], eligible),
                True,
                False,
            ), _id)
            if picked:
                assert isinstance(picked[0], AVGECharacterCard)
                top_deck_card = picked[0]

        remaining_eligible = eligible
        if top_deck_card is not None:
            remaining_eligible = [
                c for c in eligible if c is not top_deck_card and c.card_type != top_deck_card.card_type
            ]

        hand_card: AVGECharacterCard | None = None
        if remaining_eligible:
            picked = await env.report(CardSelectionQuery(
                self.owner,
                "Lucas: Choose another deck character (a different type) to reveal and take to your hand.",
                1,
                cast(list[AVGECard], remaining_eligible),
                cast(list[AVGECard], remaining_eligible),
                True,
                False,
            ), _id)
            if picked:
                assert isinstance(picked[0], AVGECharacterCard)
                hand_card = picked[0]

        events: list[Event | Generator] = []
        if top_deck_card is not None:
            await env.broadcast(RevealCards(self.owner, [top_deck_card]))
            chosen = top_deck_card

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
