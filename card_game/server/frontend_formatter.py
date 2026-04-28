from __future__ import annotations

import json
import re
from typing import Any

from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ..avge_abstracts.AVGEEnvironment import GamePhase
from ..avge_abstracts.AVGECards import (
    AVGECard,
    AVGECharacterCard,
    AVGEItemCard,
    AVGEStadiumCard,
    AVGESupporterCard,
    AVGEToolCard,
)
from ..constants import CardType
from card_game.constants import StatusEffect


def _to_strenum_value(value: Any) -> str:
    """Return a stable string value for StrEnum or enum-like values."""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _card_type_from_instance(card: AVGECard) -> str:
    """Map AVGE card instances to the setup payload cardType string."""
    if isinstance(card, AVGECharacterCard):
        return "character"
    if isinstance(card, AVGEToolCard):
        return "tool"
    if isinstance(card, AVGEItemCard):
        return "item"
    if isinstance(card, AVGEStadiumCard):
        return "stadium"
    if isinstance(card, AVGESupporterCard):
        return "supporter"
    raise ValueError(f"Unsupported card class: {type(card).__name__}")


def _avge_card_type_for_payload(card: AVGECard) -> str:
    """
    Return AVGECardType for payload:
    - Character cards: use the card's CardType value.
    - Non-character cards: use "NONE".
    """
    if not isinstance(card, AVGECharacterCard):
        return "NONE"

    card_type = card.card_type
    if isinstance(card_type, CardType):
        return _to_strenum_value(card_type)
    return str(card_type).upper()


def _holder_id_for_card(env: AVGEEnvironment, card: AVGECard) -> str:
    """
    Build holderId from card location:
    - Stadium holder is always "stadium".
    - Otherwise: "{owner_id}-{pile_type}" based on constants.Pile values.
    """
    if card.cardholder == env.stadium_cardholder:
        return "stadium"

    if isinstance(card, AVGEToolCard) and card.card_attached is not None:
        # Attached tools live in TOOL pile internally, but frontend expects
        # board holder ids (active/bench/hand/discard/deck/stadium) for reloads.
        attached_card: AVGECard = card.card_attached
        seen_ids: set[str] = set()
        while isinstance(attached_card, AVGEToolCard) and attached_card.card_attached is not None:
            attached_id = getattr(attached_card, 'unique_id', None)
            if isinstance(attached_id, str) and attached_id in seen_ids:
                break
            if isinstance(attached_id, str):
                seen_ids.add(attached_id)
            attached_card = attached_card.card_attached

        if attached_card.cardholder == env.stadium_cardholder:
            return "stadium"

        if attached_card.player is not None and attached_card.cardholder is not None:
            owner_id = _to_strenum_value(attached_card.player.unique_id)
            pile_type = _to_strenum_value(attached_card.cardholder.pile_type)
            if pile_type != 'tool':
                return f"{owner_id}-{pile_type}"

    if card.player is None or card.cardholder is None:
        raise ValueError(f"Card has incomplete ownership/cardholder state: {card.unique_id}")

    owner_id = _to_strenum_value(card.player.unique_id)
    pile_type = _to_strenum_value(card.cardholder.pile_type)
    return f"{owner_id}-{pile_type}"


def _attached_to_card_id(card: AVGECard) -> str | None:
    if isinstance(card, AVGEToolCard) and card.card_attached is not None:
        return card.card_attached.unique_id
    return None


def _owner_id_for_card(card: AVGECard) -> str:
    if card.player is None:
        raise ValueError(f"Card has no owner/player attached: {card.unique_id}")
    return _to_strenum_value(card.player.unique_id)


def _status_effect_payload(card: AVGECard) -> dict[str, int]:
    """Build frontend status-effect counters for character cards."""
    if not isinstance(card, AVGECharacterCard):
        return {}

    statuses = getattr(card, "statuses_attached", {})
    if not isinstance(statuses, dict):
        return {"Goon": 0, "Arranger": 0, "Maid": 0}

    def _count(status_key: Any) -> int:
        attached = statuses.get(status_key, [])
        return len(attached) if isinstance(attached, list) else 0

    return {
        "Goon": _count(StatusEffect.GOON),
        "Arranger": _count(StatusEffect.ARRANGER),
        "Maid": _count(StatusEffect.MAID),
    }


def _format_card_class_name(card: AVGECard) -> str:
    """Convert class names like AVGEStadiumCard into AVGE Stadium Card."""
    name = type(card).__name__
    name = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", name)
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    return name


def _sorted_cards(env: AVGEEnvironment) -> list[AVGECard]:
    """
    Deterministic card ordering:
    - Numeric suffix sort when ids look like card_12.
    - Lexicographic fallback for everything else.
    """

    def sort_key(c: AVGECard) -> tuple[int, int, str]:
        uid = c.unique_id
        if "_" in uid:
            maybe_num = uid.rsplit("_", 1)[1]
            if maybe_num.isdigit():
                return (0, int(maybe_num), uid)
        return (1, 0, uid)

    return sorted(env.cards.values(), key=sort_key)


def _collect_energy_tokens(env: AVGEEnvironment) -> list[Any]:
    """Collect all known energy tokens without duplicates."""
    tokens_by_id: dict[str, Any] = {}

    for player in env.players.values():
        for token in player.energy:
            tokens_by_id[token.unique_id] = token

        for holder in player.cardholders.values():
            for card in holder:
                if isinstance(card, AVGECharacterCard):
                    for token in card.energy:
                        tokens_by_id[token.unique_id] = token

    for token in env.energy:
        tokens_by_id[token.unique_id] = token

    return sorted(tokens_by_id.values(), key=lambda t: t.unique_id)


def _frontend_phase_token(phase: GamePhase) -> str:
    if phase == GamePhase.PHASE_2:
        return 'phase2'
    if phase == GamePhase.ATK_PHASE:
        return 'atk'
    return 'no-input'


def _energy_holder_and_attachment(env: AVGEEnvironment, token: Any) -> tuple[str, str, str | None]:
    """
    Return (ownerId, holderId, attachedToCardId) for a token.

    holderId mapping:
    - token on player -> "shared-energy"
    - token on character card -> "shared-energy" and attachedToCardId is that card id
    - token in env energy pool -> "energy-discard"
    """
    holder = token.holder

    # Token attached to a character card.
    if isinstance(holder, AVGECharacterCard):
        owner_id = _to_strenum_value(holder.player.unique_id)
        return owner_id, 'shared-energy', holder.unique_id

    # Token in a player's energy reserve/pile.
    if hasattr(holder, "unique_id") and _to_strenum_value(getattr(holder, "unique_id", "")) in env.players:
        owner_id = _to_strenum_value(holder.unique_id)
        return owner_id, 'shared-energy', None

    # Token detached/voided into environment.
    if holder is env or holder is None:
        return 'shared', 'energy-discard', None

    # Fallback for unexpected custom holder shapes.
    owner_id = 'shared'
    if hasattr(holder, "player") and getattr(holder, "player") is not None:
        owner_id = _to_strenum_value(holder.player.unique_id)
    return owner_id, 'shared-energy', None


def environment_to_setup_payload(env: AVGEEnvironment) -> dict[str, Any]:
    """
    Convert an AVGEEnvironment into the setup payload format used by the frontend/router.

    Mapping rules:
    - cardType: inferred from AVGE card instance class.
    - AVGECardType: "NONE" for non-character; character card_type for character cards.
    - AVGECardClass: type(card).__name__.
    - ownerId: card owner/player unique_id.
    - holderId: "stadium" for environment stadium holder, otherwise
      "{owner_id}-{pile_type}" using constants.Pile values.
    """
    players_payload: dict[str, Any] = {}
    for player_id, player in sorted(env.players.items(), key=lambda kv: kv[0]):
        attr_payload = {
            _to_strenum_value(attr_key): attr_value
            for attr_key, attr_value in player.attributes.items()
        }
        players_payload[player_id] = {
            "username": _to_strenum_value(player.unique_id),
            "attributes": attr_payload,
        }

    cards_payload: list[dict[str, Any]] = []
    for card in _sorted_cards(env):
        card_type_str = _card_type_from_instance(card)
        is_character = isinstance(card, AVGECharacterCard)

        cards_payload.append(
            {
                "id": card.unique_id,
                "ownerId": _owner_id_for_card(card),
                "cardType": card_type_str,
                "holderId": _holder_id_for_card(env, card),
                "hp": int(getattr(card, "hp", 0)) if is_character else 0,
                "maxHp": int(getattr(card, "max_hp", 0)) if is_character else 0,
                "attachedToCardId": _attached_to_card_id(card),
                "AVGECardType": _avge_card_type_for_payload(card),
                "AVGECardClass": _format_card_class_name(card),
                "statusEffect": _status_effect_payload(card),
            }
        )

    energy_tokens_payload: list[dict[str, Any]] = []
    for token in _collect_energy_tokens(env):
        owner_id, holder_id, attached_to_card_id = _energy_holder_and_attachment(env, token)
        energy_tokens_payload.append(
            {
                "id": token.unique_id,
                "ownerId": owner_id,
                "holderId": holder_id,
                "attachedToCardId": attached_to_card_id,
            }
        )

    return {
        "roundNumber": int(env.round_id),
        "playerTurn": _to_strenum_value(env.player_turn.unique_id),
        "gamePhase": _frontend_phase_token(env.game_phase),
        "players": players_payload,
        "cards": cards_payload,
        "energyTokens": energy_tokens_payload,
    }


def environment_to_setup_json(env: AVGEEnvironment, indent: int = 2) -> str:
    """Return a pretty JSON string for the converted setup payload."""
    return json.dumps(environment_to_setup_payload(env), indent=indent) + "\n"
