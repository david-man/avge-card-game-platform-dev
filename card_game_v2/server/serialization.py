from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..avge_abstracts.AVGECard import AVGECard, AVGECharacterCard
from ..avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ..constants import User

if TYPE_CHECKING:
    from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ..avge_abstracts.AVGEPlayer import AVGEPlayer


_DECK_TYPE_BY_NAME = {deck_type.name: deck_type for deck_type in DeckType}


def card_to_wire(card: AVGECard) -> dict[str, Any]:
    '''Complete, non-redacted representation of a single card - every field visible to both
    players, per the "hiding is a frontend concern" design decision. No secret-vs-public split
    here at all.'''
    wire: dict[str, Any] = {
        "id": card.cardID,
        "class_name": type(card).__name__,
        "owner": card.owner.name,
        "deck_type": card.deck_type.name,
    }
    if isinstance(card, AVGECharacterCard):
        wire.update({
            "hp": card.hp,
            "max_hp": card.max_hp,
            "card_type": card.card_type.value,
            "retreat_cost": card.retreat_cost,
            "energy_count": len(card.energy_tokens),
            "statuses": [
                status.value for status, givers in card.statuses_attached.items() if len(givers) > 0
            ],
            "tools": [card_to_wire(tool) for tool in card.tools_attached.cards_holding],
        })
    return wire


def _pile_to_wire(deck: AVGEDeck) -> list[dict[str, Any]]:
    return [card_to_wire(card) for card in deck.cards_holding]


def _player_state(player: AVGEPlayer) -> dict[str, Any]:
    active_cards = player.card_piles[DeckType.ACTIVE_CARD].cards_holding
    return {
        "user": player.id.name,
        "active": card_to_wire(active_cards[0]) if active_cards else None,
        "bench": _pile_to_wire(player.card_piles[DeckType.BENCH]),
        "hand": _pile_to_wire(player.card_piles[DeckType.HAND]),
        "deck": _pile_to_wire(player.card_piles[DeckType.DECK]),
        "discard": _pile_to_wire(player.card_piles[DeckType.DISCARD]),
    }


def snapshot(env: AVGEEnvironment) -> dict[str, Any]:
    '''One complete, non-viewer-scoped snapshot of the whole game - both players' actual hand
    contents, exact deck order, everything. Sent once at game_start and once on
    opponent_reconnected/successful rejoin; incremental changes flow separately via the per-event
    update IOTypes (see core/AVGEIOManager.py).'''
    stadium_cards = env.stadium_cardholder.cards_holding
    return {
        "turn": env.turn.name,
        "round": env.round,
        "stadium": card_to_wire(stadium_cards[0]) if stadium_cards else None,
        "players": {
            User.PLAYER_1.name: _player_state(env.players[User.PLAYER_1]),
            User.PLAYER_2.name: _player_state(env.players[User.PLAYER_2]),
        },
    }


def resolve_card(env: AVGEEnvironment, card_id: str) -> AVGECard | None:
    '''Finds the live card object with the given wire id, searching every pile (including each
    character's own attached tools and the global stadium slot).'''
    for player in env.players.values():
        for deck in player.card_piles.values():
            for card in deck.cards_holding:
                if card.cardID == card_id:
                    return card
                if isinstance(card, AVGECharacterCard):
                    for tool in card.tools_attached.cards_holding:
                        if tool.cardID == card_id:
                            return tool
    for card in env.stadium_cardholder.cards_holding:
        if card.cardID == card_id:
            return card
    return None


def resolve_deck(env: AVGEEnvironment, owner: User | None, deck_type_name: str) -> AVGEDeck:
    '''Resolves a wire-level (owner, deck_type name) pair back to the live AVGEDeck it names.
    `owner` is None for the STADIUM deck (it has no owning player, matching how
    io_adapter._wire_deck_ref encodes it) and required for every other deck type.'''
    deck_type = _DECK_TYPE_BY_NAME[deck_type_name]
    if deck_type == DeckType.STADIUM:
        return env.stadium_cardholder
    if owner is None:
        raise KeyError(f"deck_type {deck_type_name!r} requires an owner")
    return env.players[owner].card_piles[deck_type]
