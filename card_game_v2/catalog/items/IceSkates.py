from __future__ import annotations

from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import CardSelectionQuery, BroadcastIO, default_timeout
from ...engine.event import Event, Generator, Packet


class IceSkates(AVGEItemCard):
    '''Swap your active character with a chosen benched character.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        active_holder = player.card_piles[DeckType.ACTIVE_CARD]
        bench = player.card_piles[DeckType.BENCH]
        active = env.get_player_active(self.owner)

        bench_targets = [c for c in bench.cards_holding if isinstance(c, AVGECharacterCard)]
        if not bench_targets:
            await env.broadcast(BroadcastIO(
                "Ice Skates was used, but there are no benched characters to switch with...",
                default_timeout,
            ))
            return

        _id = AVGEEngineID(self, ActionTypes.NONCHAR, IceSkates)
        picked = await env.report(CardSelectionQuery(
            self.owner,
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
