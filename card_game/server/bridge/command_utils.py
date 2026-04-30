from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload

from ...avge_abstracts.AVGEEnvironment import GamePhase
from ...avge_abstracts.AVGECards import AVGECard, AVGECharacterCard
from ...constants import Pile
from ...internal_events import ReorderCardholder, TransferCard


def card_type_command_token(card_type: object) -> str:
    lookup = {
        'ALL': 'NONE',
        'NONE': 'NONE',
        'WW': 'WW',
        'PERC': 'PERC',
        'PIANO': 'PIANO',
        'STRING': 'STRING',
        'GUITAR': 'GUITAR',
        'CHOIR': 'CHOIR',
        'BRASS': 'BRASS',
    }
    key = str(getattr(card_type, 'value', card_type)).upper()
    return lookup.get(key, 'NONE')


def energy_target_command_arg(bridge: Any, target: Any) -> str | None:
    if isinstance(target, AVGECharacterCard):
        return target.unique_id
    if hasattr(target, 'unique_id'):
        uid = str(target.unique_id)
        if uid in {'p1', 'p2'}:
            return f'{uid}-energy'
    if target is bridge.env or target is None:
        return 'energy-discard'
    return None


def transfer_target_command_arg(bridge: Any, event: TransferCard) -> str | None:
    if event.pile_to == bridge.env.stadium_cardholder:
        return 'stadium'

    player = getattr(event.pile_to, 'player', None)
    pile_type = getattr(event.pile_to, 'pile_type', None)

    # Tool cardholders are card-attached slots and should be targeted by parent card id,
    # not by synthetic pile ids like p1-tool/p2-tool.
    if pile_type == Pile.TOOL:
        parent = getattr(event.pile_to, 'parent_card', None)
        if parent is not None:
            return parent.unique_id
        return None

    if player is None or pile_type is None:
        return None
    return f'{player.unique_id}-{pile_type}'


def normalize_zone_id(raw_zone: str) -> str:
    return raw_zone.strip().lower()


def reorder_target_command_arg(bridge: Any, event: ReorderCardholder) -> str | None:
    holder = getattr(event, 'cardholder', None)
    if holder is None:
        return None

    if holder == bridge.env.stadium_cardholder:
        return 'stadium'

    player = getattr(holder, 'player', None)
    pile_type = getattr(holder, 'pile_type', None)
    if player is None or pile_type is None:
        return None

    return normalize_zone_id(f'{player.unique_id}-{pile_type}')


def card_zone_id(bridge: Any, card: AVGECard | None) -> str | None:
    if card is None:
        return None

    holder = getattr(card, 'cardholder', None)
    if holder is None:
        return None

    if holder == bridge.env.stadium_cardholder:
        return 'stadium'

    player = getattr(holder, 'player', None)
    pile_type = getattr(holder, 'pile_type', None)
    if player is None or pile_type is None:
        return None
    return f'{player.unique_id}-{pile_type}'


def frontend_phase_token(phase: GamePhase) -> str:
    if phase == GamePhase.PHASE_2:
        return 'phase2'
    if phase == GamePhase.ATK_PHASE:
        return 'atk'
    return 'no-input'


def player_id_to_frontend(player_id: object) -> str:
    value = str(getattr(player_id, 'value', player_id)).lower()
    return 'player-1' if value == 'p1' else 'player-2'


def pick_str(data: JsonObject, *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def card_id_from_payload(data: JsonObject) -> str | None:
    return pick_str(data, 'card_id')


def get_card(bridge: Any, card_id: str | None) -> AVGECard | None:
    if not card_id:
        return None

    direct = bridge.env.cards.get(card_id)
    if direct is not None:
        return direct

    target = card_id.lower()
    for key, card in bridge.env.cards.items():
        if key.lower() == target:
            return card
    return None


def get_character_card(bridge: Any, card_id: str | None) -> AVGECharacterCard | None:
    card = get_card(bridge, card_id)
    if isinstance(card, AVGECharacterCard):
        return card
    return None


def get_energy_token(bridge: Any, token_id: str | None):
    if not token_id:
        return None

    normalized_token_id = token_id.lower()

    for player in bridge.env.players.values():
        for token in player.energy:
            token_uid = str(getattr(token, 'unique_id', ''))
            if token_uid.lower() == normalized_token_id:
                return token

        for holder in player.cardholders.values():
            for card in holder:
                if isinstance(card, AVGECharacterCard):
                    for token in card.energy:
                        token_uid = str(getattr(token, 'unique_id', ''))
                        if token_uid.lower() == normalized_token_id:
                            return token

    for token in bridge.env.energy:
        token_uid = str(getattr(token, 'unique_id', ''))
        if token_uid.lower() == normalized_token_id:
            return token

    return None


def csv_from_display_entries(values: object) -> str:
    if not isinstance(values, list):
        return ''
    result: list[str] = []
    for value in values:
        if value is None:
            result.append('none')
            continue
        uid = getattr(value, 'unique_id', None)
        if isinstance(uid, str):
            result.append(uid)
        else:
            result.append(str(value))
    return ','.join(result)


def command_token(raw: str) -> str:
    normalized = (raw or '').strip()
    if not normalized:
        return 'message'
    return normalized.replace(' ', '_')


def canonical_event_name(raw_event_type: object) -> str:
    return str(raw_event_type or '').strip().lower()


def normalize_action_name(raw_action: object) -> str:
    return str(raw_action or '').strip().lower()
