from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import Notification, default_timeout
from ...engine.event import Event, Generator, Packet


class ConcertTicket(AVGEItemCard):
    '''Draws up to 4 cards' worth of hand (formula counts this card itself, since it's
    still physically in hand at play time and only leaves via the normal post-play
    discard - see V2_MIGRATION_PLAN.md). Cannot be played as the only card in hand.

    The centralized play validator rejects the root packet when that prerequisite is
    not met, so the card stays in hand and no play-side state is consumed.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="ConcertTicket",
                description=ConcertTicket.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
            hand = acting_card.env.players[acting_card.owner].card_piles[DeckType.HAND]
            return len(hand) > 1

        def unavailable_reason(self, action_card: AVGECard, acting_card: AVGECard) -> str:
            return "Concert Ticket needs another card in your hand."

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, ConcertTicket):
                raise TypeError("ConcertTicket action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            hand = player.card_piles[DeckType.HAND]
            deck = player.card_piles[DeckType.DECK]

            _id = AVGEEngineID(acting_card, self.action_type, ConcertTicket)
            current_hand_size = len(hand)
            if current_hand_size == 1:
                await env.report(Notification(
                    acting_card.owner,
                    "Concert Ticket cannot be played as the only card in hand.", default_timeout,
                ), _id)
                return

            draw_needed = max(0, 4 - current_hand_size)
            draw_count = min(draw_needed, len(deck))
            if draw_count == 0:
                return
            # deck.get_top() must be resolved lazily (once per draw, at that draw's own
            # execution time) - resolving it eagerly here would have every TransferCard in
            # this list reference the same, not-yet-moved top card.
            events: list[Event | Generator] = [
                TransferCard(_id, lambda: deck.get_top(), deck, hand, env) for _ in range(draw_count)
            ]
            env.push_packet(Packet(_id, events))
