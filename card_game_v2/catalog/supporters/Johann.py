from __future__ import annotations

from typing import Sequence

from ...avge_abstracts.AVGECard import (
    AVGECard, AVGEItemCard, AVGEStadiumCard, AVGESupporterCard, AVGEToolCard,
)
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard, TurnEnd
from ...core.AVGEIOManager import CardSelectionQuery
from ...engine.event import Event, Generator, Packet


class Johann(AVGESupporterCard):
    '''Pick up to 3 discarded non-character cards - at most 1 Supporter, 1
    Item-or-Tool, and 1 Stadium - back to hand, then ends the turn. v1 enforces the
    "at most 1 per category" rule via a custom retry-validated single query; v2 has
    no such retry loop (same limitation already solved for CastReserve), so this
    instead runs three independent, separately-scoped queries - one per category -
    which structurally guarantees the same at-most-1-each result without ever needing
    to validate or retry.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        discard = player.card_piles[DeckType.DISCARD]
        hand = player.card_piles[DeckType.HAND]
        _id = AVGEEngineID(self, ActionTypes.NONCHAR, Johann)

        async def _pick_one(candidates: Sequence[AVGECard], prompt: str) -> AVGECard | None:
            if not candidates:
                return None
            picked = await env.report(CardSelectionQuery(
                self.owner, prompt, 1, list(candidates), list(candidates), True, False,
            ), _id)
            return picked[0] if picked else None

        supporters = [c for c in discard.cards_holding if isinstance(c, AVGESupporterCard) and c is not self]
        items_or_tools = [c for c in discard.cards_holding if isinstance(c, (AVGEItemCard, AVGEToolCard))]
        stadiums = [c for c in discard.cards_holding if isinstance(c, AVGEStadiumCard)]

        pick_supporter = await _pick_one(supporters, "Johann: Choose a discarded Supporter to take to your hand (optional).")
        pick_item_or_tool = await _pick_one(items_or_tools, "Johann: Choose a discarded Item or Tool to take to your hand (optional).")
        pick_stadium = await _pick_one(stadiums, "Johann: Choose a discarded Stadium to take to your hand (optional).")

        events: list[Event | Generator] = [
            TransferCard(_id, chosen, discard, hand, env)
            for chosen in (pick_supporter, pick_item_or_tool, pick_stadium)
            if chosen is not None
        ]
        events.append(TurnEnd(_id, env))

        env.push_packet(Packet(_id, events))
