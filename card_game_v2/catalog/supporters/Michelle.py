from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGECard, AVGESupporterCard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, default_timeout
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import CardSelectionQuery, Notification
from ...engine.event import Event, Generator, Packet


class Michelle(AVGESupporterCard):
    '''The opponent (not the caster) picks one card from their own hand to keep;
    everything else in their hand is discarded. It cannot be played on the first
    turn; the centralized validator rejects that play before consuming the supporter
    allowance or moving the card from hand.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="Michelle",
                description=Michelle.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
            return acting_card.env.round > 0

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, Michelle):
                raise TypeError("Michelle action requires its defining card")
            env = acting_card.env
            if env.round == 0:
                await env.report(Notification(
                    acting_card.owner, "Michelle cannot be played on the first turn.", default_timeout,
                ), AVGEEngineID(acting_card, self.action_type, Michelle))
                return

            opponent = env.get_opponent(acting_card.owner)
            opponent_hand = opponent.card_piles[DeckType.HAND]
            opponent_discard = opponent.card_piles[DeckType.DISCARD]
            if len(opponent_hand) <= 1:
                return

            _id = AVGEEngineID(acting_card, self.action_type, Michelle)
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
