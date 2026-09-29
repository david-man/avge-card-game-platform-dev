from __future__ import annotations

from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import CardSelectionQuery, Notification, default_timeout
from ...engine.event import Event, Generator, Packet


class IceSkates(AVGEItemCard):
    '''Swap your active character with a chosen benched character.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="IceSkates",
                description=IceSkates.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, IceSkates):
                raise TypeError("IceSkates action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            active_holder = player.card_piles[DeckType.ACTIVE_CARD]
            bench = player.card_piles[DeckType.BENCH]
            active = env.get_player_active(acting_card.owner)

            _id = AVGEEngineID(acting_card, self.action_type, IceSkates)
            bench_targets = [c for c in bench.cards_holding if isinstance(c, AVGECharacterCard)]
            if not bench_targets:
                await env.report(Notification(
                    acting_card.owner,
                    "Ice Skates was used, but there are no benched characters to switch with...",
                    default_timeout,
                ), _id)
                return
            picked = await env.report(CardSelectionQuery(
                acting_card.owner,
                "Ice Skates: Choose one benched character to switch with your active.",
                1,
                cast(list[AVGECard], bench_targets),
                cast(list[AVGECard], bench_targets),
                False,
                False,
            ), _id)
            bench_target = picked[0]
            assert isinstance(bench_target, AVGECharacterCard)

            events: list[Event | Generator] = [
                TransferCard(_id, bench_target, bench, active_holder, env),
                TransferCard(_id, active, active_holder, bench, env),
            ]
            env.push_packet(Packet(_id, events))
