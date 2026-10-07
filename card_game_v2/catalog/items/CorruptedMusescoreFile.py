from __future__ import annotations

from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, default_timeout
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import CardSelectionQuery, Notification
from ...engine.event import Event, Generator, Packet


class CorruptedMusescoreFile(AVGEItemCard):
    '''Discard a tool from one of your own characters, then search the deck for
    a non-item card to take to hand.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="CorruptedMusescoreFile",
                description=CorruptedMusescoreFile.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, CorruptedMusescoreFile):
                raise TypeError("CorruptedMusescoreFile action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
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
                await env.report(Notification(
                    acting_card.owner,
                    "Corrupted Musescore File found no tool to discard, so its search has no effect.",
                    default_timeout,
                ), AVGEEngineID(acting_card, self.action_type, CorruptedMusescoreFile))
                return

            _id = AVGEEngineID(acting_card, self.action_type, CorruptedMusescoreFile)
            source_pick = await env.report(CardSelectionQuery(
                acting_card.owner,
                "Corrupted Musescore File: Choose one of your characters with a tool attached.",
                1,
                cast(list[AVGECard], tool_targets),
                cast(list[AVGECard], own_chars),
                False,
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

            nonitem_choices = [c for c in deck.cards_holding if not isinstance(c, AVGEItemCard)]
            if nonitem_choices:
                deck_pick = await env.report(CardSelectionQuery(
                    acting_card.owner,
                    "Corrupted Musescore File: Choose a non-item from your deck to put into your hand.",
                    1,
                    cast(list[AVGECard], nonitem_choices),
                    list(deck.cards_holding),
                    False,
                    False,
                ), _id)
                chosen_item = deck_pick[0]
                events.append(TransferCard(_id, chosen_item, deck, hand, env))

            env.push_packet(Packet(_id, events))
