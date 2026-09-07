from __future__ import annotations

from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import CardSelectionQuery
from ...engine.event import Event, Generator, Packet


class CorruptedMusescoreFile(AVGEItemCard):
    '''Optionally discard a tool from one of your own characters; if you do, and your
    deck has any item in it, also take a chosen item from deck to hand. Declining the
    tool discard (or having no eligible character to begin with) ends the card there -
    no item search happens without first discarding a tool.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        deck = player.card_piles[DeckType.DECK]
        hand = player.card_piles[DeckType.HAND]
        discard = player.card_piles[DeckType.DISCARD]

        own_chars: list[AVGECharacterCard] = [
            c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
        ] + [
            c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
        ]
        tool_targets = [c for c in own_chars if len(c.tools_attached.cards_holding) > 0]
        if not tool_targets:
            return

        _id = AVGEEngineID(self, ActionTypes.NONCHAR, CorruptedMusescoreFile)
        source_pick = await env.report(CardSelectionQuery(
            self.owner,
            "Corrupted Musescore File: Choose one of your characters with a tool attached.",
            1,
            cast(list[AVGECard], tool_targets),
            cast(list[AVGECard], own_chars),
            True,
            False,
        ), _id)
        if not source_pick:
            return

        source = source_pick[0]
        assert isinstance(source, AVGECharacterCard)
        tool_choice = source.tools_attached.cards_holding[0]

        events: list[Event | Generator] = [
            TransferCard(_id, tool_choice, source.tools_attached, discard, env),
        ]

        item_choices = [c for c in deck.cards_holding if isinstance(c, AVGEItemCard)]
        if item_choices:
            deck_pick = await env.report(CardSelectionQuery(
                self.owner,
                "Corrupted Musescore File: Choose an item from your deck to put into your hand.",
                1,
                cast(list[AVGECard], item_choices),
                list(deck.cards_holding),
                False,
                False,
            ), _id)
            chosen_item = deck_pick[0]
            events.append(TransferCard(_id, chosen_item, deck, hand, env))

        env.push_packet(Packet(_id, events))
