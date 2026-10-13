"""Provisional opening deal and atomic, passive-aware setup finalization."""
from __future__ import annotations

from collections.abc import Mapping

from ..avge_abstracts.AVGECard import AVGECard, AVGECharacterCard
from ..avge_abstracts.AVGEDeck import AVGEDeck, DeckType, transfer_card
from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ..avge_abstracts.AVGEID import AVGEEngineID
from ..constants import (
    ActionTypes, INITIAL_HAND_SIZE, MAX_BENCH_SIZE, SETUP_BLOCKED_CARDS, User,
)
from ..core.AVGEIOManager import (
    AVGEIO, BroadcastIO, EndOfTurn, Notification, RevealCards, ShowBoxedStrings,
)
from ..core.EventCatalog import TransferCard
from ..engine.event import Packet
from .listeners import default_core_listeners


class SetupError(ValueError):
    pass


class SetupPromptError(SetupError):
    pass


class _SetupIO(AVGEIO):
    """Resolve informational effects locally and fail immediately on a decision request."""

    async def report(self, io_obj):
        if isinstance(io_obj, (Notification, BroadcastIO, EndOfTurn, RevealCards, ShowBoxedStrings)):
            return None
        raise SetupPromptError(f"Setup passive requested {type(io_obj).__name__}")

    async def broadcast(self, io_obj):
        return None


def select_opening_cards(deck: AVGEDeck) -> tuple[AVGECharacterCard, list[AVGECard]]:
    """Choose an active and five opening cards, leaving setup-blocked cards in the deck."""
    available = [
        card for card in deck.cards_holding
        if type(card).__name__ not in SETUP_BLOCKED_CARDS
    ]
    starter = next((card for card in available if isinstance(card, AVGECharacterCard)), None)
    if starter is None:
        raise SetupError(f"{deck.deck_owner.id.name} has no eligible starting character")
    hand_cards = [card for card in available if card is not starter][:INITIAL_HAND_SIZE]
    if len(hand_cards) < INITIAL_HAND_SIZE:
        raise SetupError(f"{deck.deck_owner.id.name} has too few eligible opening cards")
    return starter, hand_cards


def deal_preview(env: AVGEEnvironment) -> None:
    """Deal visible options without firing passives that would later run a second time."""
    for player in env.players.values():
        deck = player.card_piles[DeckType.DECK]
        active = player.card_piles[DeckType.ACTIVE_CARD]
        hand = player.card_piles[DeckType.HAND]
        starter, hand_cards = select_opening_cards(deck)
        transfer_card(starter, deck, active)
        starter.deck_type = DeckType.ACTIVE_CARD
        for card in hand_cards:
            transfer_card(card, deck, hand)
            card.deck_type = DeckType.HAND


def validate_submission(
    env: AVGEEnvironment, user: User, active_card_id: str, bench_card_ids: list[str],
) -> dict[str, object]:
    if not isinstance(active_card_id, str) or not active_card_id:
        raise SetupError("Choose one active character.")
    if not isinstance(bench_card_ids, list) or any(not isinstance(x, str) or not x for x in bench_card_ids):
        raise SetupError("Bench cards must be an array of card IDs.")
    if len(bench_card_ids) > MAX_BENCH_SIZE:
        raise SetupError(f"The bench holds at most {MAX_BENCH_SIZE} characters.")
    selected = [active_card_id, *bench_card_ids]
    if len(set(selected)) != len(selected):
        raise SetupError("A character can occupy only one setup position.")
    player = env.players[user]
    candidates = [*player.card_piles[DeckType.HAND].cards_holding,
                  *player.card_piles[DeckType.ACTIVE_CARD].cards_holding]
    by_id = {card.cardID: card for card in candidates if isinstance(card, AVGECharacterCard)}
    for card_id in selected:
        card = by_id.get(card_id)
        if card is None:
            raise SetupError("Choose only your opening character cards.")
        if type(card).__name__ in SETUP_BLOCKED_CARDS:
            raise SetupError(f"{card} cannot be deployed during setup.")
    return {"active_card_id": active_card_id, "bench_card_ids": list(bench_card_ids)}


async def build_final_environment(
    preview: AVGEEnvironment,
    decks: Mapping[User, list[type[AVGECard]]],
    submissions: Mapping[User, dict[str, object]],
) -> AVGEEnvironment:
    io = _SetupIO()
    env = AVGEEnvironment(io, dict(decks), default_core_listeners())
    env.turn = preview.turn
    deal_id = AVGEEngineID(None, ActionTypes.ENV, None)
    placement_id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
    opening_deals = []
    placements = []

    async def reject_failed_packet(packet: Packet) -> None:
        raise SetupError(packet.rejection_reason or "A setup transfer or passive was rejected.")

    env.engine.on_packet_failed = reject_failed_packet
    for user in User:
        source = preview.players[user]
        target = env.players[user]
        target_deck = target.card_piles[DeckType.DECK]
        by_id = {card.cardID: card for card in target_deck.cards_holding}
        choice = submissions[user]
        active_id = choice["active_card_id"]
        bench_ids = choice["bench_card_ids"]
        assert isinstance(active_id, str) and isinstance(bench_ids, list)
        opening_active = source.card_piles[DeckType.ACTIVE_CARD].cards_holding[0]
        opening_hand = source.card_piles[DeckType.HAND].cards_holding
        hand = target.card_piles[DeckType.HAND]
        bench = target.card_piles[DeckType.BENCH]
        active = target.card_piles[DeckType.ACTIVE_CARD]

        # The preview's active is an opening card too. Put all six cards in the fresh hand
        # first, retaining the preview hand order and appending that original starter.
        for card in [*opening_hand, opening_active]:
            opening_deals.append(TransferCard(
                deal_id, by_id[card.cardID], target_deck, hand, env,
            ))

        # The chosen active enters play exactly once, through the same hand-to-bench path as
        # a normal character play. Moving it onward from bench does not reactivate its passive
        # or spend a turn swap. Do this before filling all five bench slots.
        placements.extend([
            TransferCard(placement_id, by_id[active_id], hand, bench, env),
            TransferCard(deal_id, by_id[active_id], bench, active, env),
        ])
        for card_id in bench_ids:
            placements.append(TransferCard(
                placement_id, by_id[card_id], hand, bench, env,
            ))

    env.push_packet(Packet(deal_id, [*opening_deals, *placements]))
    await env.engine.flush(lambda: False)
    for user in User:
        if not env.players[user].card_piles[DeckType.ACTIVE_CARD].cards_holding:
            raise SetupError("A setup passive left a player without an active character.")
        if any(type(card).__name__ in SETUP_BLOCKED_CARDS
               for card in env.players[user].card_piles[DeckType.HAND]):
            raise SetupError("A setup passive drew a card that cannot enter the opening hand.")
    return env
