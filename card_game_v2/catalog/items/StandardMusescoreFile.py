from __future__ import annotations

from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import CardSelectionQuery
from ...engine.event import Event, Generator, Packet


class StandardMusescoreFile(AVGEItemCard):
    '''Near-twin of `CorruptedMusescoreFile`: optionally discard a tool from one of your
    own characters; if you do, optionally also take a chosen non-item card from deck to
    hand. Declining the tool discard (or having no eligible character to begin with)
    ends the card there. Unlike CorruptedMusescoreFile's item search, the second pick
    here is itself optional (allows a decline) even once a tool has been discarded.'''

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

        _id = AVGEEngineID(self, ActionTypes.NONCHAR, StandardMusescoreFile)
        source_pick = await env.report(CardSelectionQuery(
            self.owner,
            "Standard Musescore File: Choose a character with a tool to discard (or None).",
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
        tool_to_discard = source.tools_attached.cards_holding[0]

        events: list[Event | Generator] = [
            TransferCard(_id, tool_to_discard, source.tools_attached, discard, env),
        ]

        non_item_choices = [c for c in deck.cards_holding if not isinstance(c, AVGEItemCard)]
        if non_item_choices:
            deck_pick = await env.report(CardSelectionQuery(
                self.owner,
                "Standard Musescore File: Choose a non-item card from your deck to put into your hand (or None).",
                1,
                non_item_choices,
                list(deck.cards_holding),
                True,
                False,
            ), _id)
            if deck_pick:
                events.append(TransferCard(_id, deck_pick[0], deck, hand, env))

        env.push_packet(Packet(_id, events))
