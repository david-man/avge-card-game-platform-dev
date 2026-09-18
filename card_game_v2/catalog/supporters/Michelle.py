from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGECard, AVGESupporterCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, default_timeout
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import CardSelectionQuery, Notification
from ...engine.event import Event, Generator, Packet


class Michelle(AVGESupporterCard):
    '''The opponent (not the caster) picks one card from their own hand to keep;
    everything else in their hand is discarded. Can't be played on the first turn -
    v1 fully cancels its own play in that case; v2's `play_card() -> None` has no
    "cancel myself" channel, so this migration just skips the effect instead (same
    simplification already established by Otamatone/MainHall's identical
    restriction).'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        if env.round == 0:
            await env.report(Notification(
                self.owner, "Michelle cannot be played on the first turn.", default_timeout,
            ), AVGEEngineID(self, ActionTypes.NONCHAR, Michelle))
            return

        opponent = env.get_opponent(self.owner)
        opponent_hand = opponent.card_piles[DeckType.HAND]
        opponent_discard = opponent.card_piles[DeckType.DISCARD]
        if len(opponent_hand) <= 1:
            return

        _id = AVGEEngineID(self, ActionTypes.NONCHAR, Michelle)
        picked = await env.report(CardSelectionQuery(
            opponent.id,
            "Michelle: Choose one card from your hand to keep - the rest will be discarded.",
            1,
            opponent_hand.cards_holding,
            opponent_hand.cards_holding,
            False,
            False,
        ), _id)
        keep_card = picked[0]

        events: list[Event | Generator] = [
            TransferCard(_id, hand_card, opponent_hand, opponent_discard, env)
            for hand_card in list(opponent_hand.cards_holding)
            if hand_card is not keep_card
        ]
        if events:
            env.push_packet(Packet(_id, events))
