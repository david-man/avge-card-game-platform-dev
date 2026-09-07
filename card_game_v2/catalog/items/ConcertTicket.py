from __future__ import annotations

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import BroadcastIO, default_timeout
from ...engine.event import Event, Generator, Packet


class ConcertTicket(AVGEItemCard):
    '''Draws up to 4 cards' worth of hand (formula counts this card itself, since it's
    still physically in hand at play time and only leaves via the normal post-play
    discard - see V2_MIGRATION_PLAN.md). Cannot be played as the only card in hand.

    v1 treats that "only card in hand" case as a full cancel - the card is never even
    consumed. v2's item dispatch always discards the played card in a follow-up packet
    (see Phase2.act()), queued independently of play_card()'s own effects, so there is
    no clean way to also cancel that discard from here; this instead just skips the
    draw effect and still lets the card be discarded normally.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        hand = player.card_piles[DeckType.HAND]
        deck = player.card_piles[DeckType.DECK]

        current_hand_size = len(hand)
        if current_hand_size == 1:
            await env.broadcast(BroadcastIO(
                "Concert Ticket cannot be played as the only card in hand.", default_timeout,
            ))
            return

        draw_needed = max(0, 4 - current_hand_size)
        draw_count = min(draw_needed, len(deck))
        if draw_count == 0:
            return

        _id = AVGEEngineID(self, ActionTypes.NONCHAR, ConcertTicket)
        # deck.get_top() must be resolved lazily (once per draw, at that draw's own
        # execution time) - resolving it eagerly here would have every TransferCard in
        # this list reference the same, not-yet-moved top card.
        events: list[Event | Generator] = [
            TransferCard(_id, lambda: deck.get_top(), deck, hand, env) for _ in range(draw_count)
        ]
        env.push_packet(Packet(_id, events))
