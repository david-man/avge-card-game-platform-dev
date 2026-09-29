from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import CardSelectionQuery, RevealCards, Notification, default_timeout
from ...engine.event import Packet


class PrintedScore(AVGEItemCard):
    '''Reveal the opponent's hand, and the opponent picks one card from it to discard. Cannot be played on the first turn, or if the opponent's hand is empty.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="PrintedScore",
                description=PrintedScore.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
            opponent = acting_card.env.get_opponent(acting_card.owner)
            return (
                acting_card.env.round > 0
                and len(opponent.card_piles[DeckType.HAND]) > 0
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, PrintedScore):
                raise TypeError("PrintedScore action requires its defining card")
            env = acting_card.env
            _id = AVGEEngineID(acting_card, self.action_type, PrintedScore)
            if env.round == 0:
                await env.report(Notification(
                    acting_card.owner, "Cannot play Printed Score on the first turn.", default_timeout,
                ), _id)
                return

            opponent = env.get_opponent(acting_card.owner)
            opponent_hand = opponent.card_piles[DeckType.HAND]
            opponent_discard = opponent.card_piles[DeckType.DISCARD]
            if len(opponent_hand) == 0:
                await env.report(Notification(
                    acting_card.owner, "Printed Score: Opponent has no cards in hand.", default_timeout,
                ), _id)
                return
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
