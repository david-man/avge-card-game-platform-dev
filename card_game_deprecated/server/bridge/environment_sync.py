from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload

from ..formatting.frontend_formatter import environment_to_setup_payload as format_environment_to_setup_payload
from .setup_payload import environment_to_setup_payload


def sync_environment_commands(bridge: Any) -> list[str]:
    payload_getter = getattr(bridge, 'get_setup_payload', None)
    payload_raw: Any
    if callable(payload_getter):
        payload_raw = payload_getter()
    else:
        payload_raw = environment_to_setup_payload(
            bridge.env,
            format_environment_to_setup_payload=format_environment_to_setup_payload,
            p1_username=str(bridge.env.players['p1'].unique_id),
            p2_username=str(bridge.env.players['p2'].unique_id),
        )
    payload: JsonObject = payload_raw if isinstance(payload_raw, dict) else {}
    commands: list[str] = []

    for player_token, player_data in sorted(payload.get('players', {}).items()):
        frontend_player = bridge._player_id_to_frontend(player_token)
        attributes = player_data.get('attributes', {}) if isinstance(player_data, dict) else {}
        for attr_key, attr_value in attributes.items():
            if isinstance(attr_value, (int, float)):
                commands.append(f'stat {frontend_player} {attr_key} {int(attr_value)}')

    cards = payload.get('cards', []) if isinstance(payload.get('cards', []), list) else []
    base_cards: list[JsonObject] = []
    attached_tools: list[JsonObject] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        if card.get('cardType') == 'tool' and isinstance(card.get('attachedToCardId'), str):
            attached_tools.append(card)
        else:
            base_cards.append(card)

    for card in base_cards + attached_tools:
        card_id = card.get('id')
        holder_id = card.get('holderId')
        if not isinstance(card_id, str):
            continue

        avge_card_type = card.get('AVGECardType')
        if isinstance(avge_card_type, str) and avge_card_type.strip():
            commands.append(f'changetype {card_id} {bridge._card_type_command_token(avge_card_type)}')

        attached_to = card.get('attachedToCardId')
        if isinstance(attached_to, str) and card.get('cardType') == 'tool':
            commands.append(f'mv {card_id} {attached_to}')
        elif isinstance(holder_id, str):
            commands.append(f'mv {card_id} {holder_id}')

        if card.get('cardType') == 'character':
            hp = card.get('hp')
            max_hp = card.get('maxHp')
            if isinstance(hp, (int, float)) and isinstance(max_hp, (int, float)):
                commands.append(f'hp {card_id} {int(hp)} {int(max_hp)}')
            statuses = card.get('statusEffect', {})
            if isinstance(statuses, dict):
                for status_name in ('Arranger', 'Goon', 'Maid'):
                    count = statuses.get(status_name)
                    if isinstance(count, int):
                        commands.append(f'set_status {card_id} {status_name} {count}')

    energy_tokens = payload.get('energyTokens', []) if isinstance(payload.get('energyTokens', []), list) else []
    for token in energy_tokens:
        if not isinstance(token, dict):
            continue
        token_id = token.get('id')
        if not isinstance(token_id, str):
            continue
        attached_to = token.get('attachedToCardId')
        if isinstance(attached_to, str):
            commands.append(f'mv-energy {token_id} {attached_to}')
        else:
            holder_id = token.get('holderId')
            if isinstance(holder_id, str):
                commands.append(f'mv-energy {token_id} {holder_id}')

    commands.append(f'turn {bridge._player_id_to_frontend(bridge.env.player_turn.unique_id)}')
    bridge._append_phase_command_if_changed(commands, bridge.env.game_phase)
    return commands
