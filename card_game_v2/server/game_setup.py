from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

from ..avge_abstracts.AVGEDeck import DeckType
from ..avge_abstracts.AVGEID import AVGEEngineID
from ..constants import ActionTypes
from ..core.EventCatalog import TransferCard
from ..engine.event import Packet
from . import event_broadcasting
from .setup_stage import select_opening_cards

if TYPE_CHECKING:
    from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ..avge_abstracts.AVGEPlayer import AVGEPlayer
    from ..engine.event import Generator
    from ..engine.event import Packet as EnginePacket


async def _deal_starting_hand(env: AVGEEnvironment, player: AVGEPlayer) -> None:
    deck = player.card_piles[DeckType.DECK]
    hand = player.card_piles[DeckType.HAND]
    bench = player.card_piles[DeckType.BENCH]
    active = player.card_piles[DeckType.ACTIVE_CARD]
    _id = AVGEEngineID(None, ActionTypes.ENV, None)
    placement_id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)

    active_card, hand_cards = select_opening_cards(deck)
    # Draw before deploying the active card so its listeners cannot react to the opening hand.
    # Use the same hand -> bench -> active path as setup finalization.
    events: list[Event | Generator] = [TransferCard(_id, active_card, deck, hand, env)]
    events.extend(TransferCard(_id, card, deck, hand, env) for card in hand_cards)
    events.extend([
        TransferCard(placement_id, active_card, hand, bench, env),
        TransferCard(_id, active_card, bench, active, env),
    ])

    env.push_packet(Packet(_id, events))
    await env.engine.flush(lambda: False)


def _wire_event_broadcast_hooks(
    env: AVGEEnvironment,
    extra_on_packet_failed: Callable[[EnginePacket], Awaitable[None]] | None,
) -> None:
    async def handle_packet_failed(packet: EnginePacket) -> None:
        # extra_on_packet_failed (GameSession's own lifecycle logging) is composed in here, at
        # the single place on_packet_failed gets assigned, rather than as a second mutation of
        # this attribute from session.py after the fact - that used to make correctness depend on
        # call order between two separate files, with no pipeline/ordering guarantee if a third
        # listener were ever added.
        await env.broadcast(event_broadcasting.action_rejected_update(env, packet.rejection_reason))
        if extra_on_packet_failed is not None:
            await extra_on_packet_failed(packet)

    env.engine.on_packet_failed = handle_packet_failed
    env.event_updates_enabled = True


async def perform_initial_setup(
    env: AVGEEnvironment,
    extra_on_packet_failed: Callable[[EnginePacket], Awaitable[None]] | None = None,
) -> None:
    '''Deals each player's opening hand and starting active card (the engine has no built-in
    equivalent - this must run before the first PhasePickCard is ever seeded), then enables
    catalog event updates and wires on_packet_failed for rejection resync.
    `extra_on_packet_failed`, if given, runs after the broadcast on every packet rejection - the
    caller's hook into the same event, composed in directly rather than wrapped on afterward.'''
    for player in env.players.values():
        await _deal_starting_hand(env, player)
    _wire_event_broadcast_hooks(env, extra_on_packet_failed)
