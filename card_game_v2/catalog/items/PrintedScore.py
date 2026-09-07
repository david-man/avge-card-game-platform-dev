from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import CardSelectionQuery, RevealCards, BroadcastIO, default_timeout
from ...engine.event import Packet


class PrintedScore(AVGEItemCard):
    '''Reveal the opponent's hand, and the opponent picks one card from it to discard. Cannot be played on the first turn, or if the opponent's hand is empty.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        if env.round == 0:
            await env.broadcast(BroadcastIO("Cannot play Printed Score on the first turn.", default_timeout))
            return

        opponent = env.get_opponent(self.owner)
        opponent_hand = opponent.card_piles[DeckType.HAND]
        opponent_discard = opponent.card_piles[DeckType.DISCARD]
        if len(opponent_hand) == 0:
            await env.broadcast(BroadcastIO("Printed Score: Opponent has no cards in hand.", default_timeout))
            return

        _id = AVGEEngineID(self, ActionTypes.NONCHAR, PrintedScore)
        hand_choices = list(opponent_hand.cards_holding)
        picked = (await env.report(CardSelectionQuery(
            opponent.id,
            "Printed Score: Choose one revealed hand card to discard.",
            1,
            hand_choices,
            hand_choices,
            False,
            False,
        ), _id))[0]

        await env.broadcast(RevealCards(opponent.id, hand_choices))
        env.push_packet(Packet(_id, [TransferCard(_id, picked, opponent_hand, opponent_discard, env)]))
