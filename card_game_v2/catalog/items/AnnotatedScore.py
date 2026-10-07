from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import CardSelectionQuery, Notification, default_timeout
from ...engine.event import Event, Generator, Packet


class AnnotatedScore(AVGEItemCard):
    '''Owner reveals the opponent's hand and picks one card from it to discard, then
    picks a different card from the opponent's discard to return to the opponent's
    hand - both picks made by the OWNER, not the opponent (unlike e.g. PrintedScore,
    where the opponent picks). Net effect: the owner swaps one of the opponent's hand
    cards for a different discard card, entirely at the owner's discretion.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="AnnotatedScore",
                description=AnnotatedScore.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
            opponent = acting_card.env.get_opponent(acting_card.owner)
            return (
                len(opponent.card_piles[DeckType.HAND]) > 0
                and len(opponent.card_piles[DeckType.DISCARD]) > 0
            )

        def unavailable_reason(self, action_card: AVGECard, acting_card: AVGECard) -> str:
            opponent = acting_card.env.get_opponent(acting_card.owner)
            if len(opponent.card_piles[DeckType.HAND]) == 0:
                return "Annotated Score needs a card in your opponent's hand."
            return "Annotated Score needs a card in your opponent's discard pile."

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, AnnotatedScore):
                raise TypeError("AnnotatedScore action requires its defining card")
            env = acting_card.env
            opponent = env.get_opponent(acting_card.owner)
            opponent_hand = opponent.card_piles[DeckType.HAND]
            opponent_discard = opponent.card_piles[DeckType.DISCARD]

            _id = AVGEEngineID(acting_card, self.action_type, AnnotatedScore)
            if len(opponent_hand) == 0 or len(opponent_discard) == 0:
                await env.report(Notification(
                    acting_card.owner,
                    "Annotated Score cannot be played: the opponent's hand or discard is empty.",
                    default_timeout,
                ), _id)
                return

            hand_choices = list(opponent_hand.cards_holding)
            hand_pick = (await env.report(CardSelectionQuery(
                acting_card.owner,
                "Annotated Score: Choose one revealed opponent hand card to discard.",
                1,
                hand_choices,
                hand_choices,
                False,
                False,
            ), _id))[0]

            discard_choices = list(opponent_discard.cards_holding)
            discard_pick = (await env.report(CardSelectionQuery(
                acting_card.owner,
                "Annotated Score: Choose a different opponent discard card to return to their hand.",
                1,
                discard_choices,
                discard_choices,
                False,
                False,
            ), _id))[0]

            events: list[Event | Generator] = [
                TransferCard(_id, hand_pick, opponent_hand, opponent_discard, env),
                TransferCard(_id, discard_pick, opponent_discard, opponent_hand, env),
            ]
            env.push_packet(Packet(_id, events))
