from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

from ..avge_abstracts.AVGECard import AVGECharacterCard
from ..avge_abstracts.AVGEDeck import DeckType
from ..avge_abstracts.AVGEID import AVGEEngineID
from ..constants import ActionTypes, INITIAL_HAND_SIZE
from ..core.EventCatalog import TransferCard
from ..engine.event import Packet
from . import event_broadcasting

if TYPE_CHECKING:
    from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ..avge_abstracts.AVGEPlayer import AVGEPlayer
    from ..engine.event import Event, Generator
    from ..engine.event import Packet as EnginePacket


async def _deal_starting_hand(env: AVGEEnvironment, player: AVGEPlayer) -> None:
    deck = player.card_piles[DeckType.DECK]
    hand = player.card_piles[DeckType.HAND]
    active = player.card_piles[DeckType.ACTIVE_CARD]
    _id = AVGEEngineID(None, ActionTypes.ENV, None)

    # The deck's own order is already fully shuffled by whoever built it (server/decks.py's
    # build_preset_decks/build_game_deck) before it ever reaches here - so "the first character
    # found from the top" is a uniformly random character selection, not necessarily (and, once
    # decks can contain non-character cards, not safely assumable to be) deck.cards_holding[0].
    # deck.transfer_card removes by identity (list.remove), not index, so pulling a card from the
    # middle of the pile is no different from pulling the top one.
    active_card = next(
        (c for c in deck.cards_holding if isinstance(c, AVGECharacterCard)), None,
    )
    if active_card is None:
        raise ValueError(
            f"{player.id.name}'s deck contains no character card to start with - this should be "
            "unreachable for any deck that passed deck_rules.validate_deck_cards()."
        )
    events: list[Event | Generator] = [TransferCard(_id, active_card, deck, active, env)]
    for _ in range(INITIAL_HAND_SIZE):
        # Lazy - each of these 5 draws must read the CURRENT top of deck at the moment it
        # actually runs (not when this function builds the packet), since earlier draws in the
        # same packet have already shifted what's on top. Same idiom as SteinertBasement's own
        # duplicate-draw reactor.
        events.append(TransferCard(_id, lambda: deck.cards_holding[0], deck, hand, env))

    env.push_packet(Packet(_id, events))
    await env.engine.flush(lambda: False)


def _wire_event_broadcast_hooks(
    env: AVGEEnvironment,
    extra_on_packet_failed: Callable[[EnginePacket], Awaitable[None]] | None,
) -> None:
    async def handle_event_committed(event: Event) -> None:
        update = event_broadcasting.event_to_update_io(event)
        if update is not None:
            await env.broadcast(update)

    async def handle_packet_failed(packet: EnginePacket) -> None:
        # extra_on_packet_failed (GameSession's own lifecycle logging) is composed in here, at
        # the single place on_packet_failed gets assigned, rather than as a second mutation of
        # this attribute from session.py after the fact - that used to make correctness depend on
        # call order between two separate files, with no pipeline/ordering guarantee if a third
        # listener were ever added.
        await env.broadcast(event_broadcasting.action_rejected_update(env, packet.rejection_reason))
        if extra_on_packet_failed is not None:
            await extra_on_packet_failed(packet)

    env.engine.on_event_committed = handle_event_committed
    env.engine.on_packet_failed = handle_packet_failed


async def perform_initial_setup(
    env: AVGEEnvironment,
    extra_on_packet_failed: Callable[[EnginePacket], Awaitable[None]] | None = None,
) -> None:
    '''Deals each player's opening hand and starting active card (the engine has no built-in
    equivalent - this must run before the first PhasePickCard is ever seeded), and wires
    env.engine.on_event_committed/on_packet_failed to broadcast the per-event update IOTypes.
    `extra_on_packet_failed`, if given, runs after the broadcast on every packet rejection - the
    caller's hook into the same event, composed in directly rather than wrapped on afterward.'''
    for player in env.players.values():
        await _deal_starting_hand(env, player)
    _wire_event_broadcast_hooks(env, extra_on_packet_failed)
