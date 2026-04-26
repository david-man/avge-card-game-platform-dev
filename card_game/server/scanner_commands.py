from __future__ import annotations

import shlex
from typing import Any, Callable


def _split_command(raw_command: str) -> list[str]:
    try:
        return shlex.split(raw_command)
    except ValueError:
        return raw_command.strip().split()


def _to_non_negative_int(raw_value: str, error_label: str) -> int:
    value = int(raw_value)
    if value < 0:
        raise ValueError(f'{error_label} must be a non-negative integer')
    return value


def _to_float(raw_value: str) -> float:
    return float(raw_value)


def _normalize_player(raw_value: str, context: str) -> str:
    value = raw_value
    if value not in {'player-1', 'player-2'}:
        raise ValueError(f'{context} must be player-1 or player-2')
    return value


def _normalize_attached_card(raw_value: str) -> str:
    return 'none' if raw_value == 'none' else raw_value


def _normalize_mv(card_id: str, holder_id: str, index: int | None) -> str:
    if index is None:
        return f'mv {card_id} {holder_id}'
    return f'mv {card_id} {holder_id} {index}'


def _normalize_rm(energy_id: str) -> str:
    return f'rm {energy_id}'


def _normalize_energy_target(raw_target: str) -> str:
    normalized_lower = raw_target.strip().lower()
    if normalized_lower in {'p1-energy', 'p2-energy', 'shared-energy'}:
        return 'shared-energy'
    if normalized_lower == 'energy-discard':
        return 'energy-discard'
    return raw_target


def _normalize_mv_energy(energy_id: str, target_id: str) -> str:
    normalized_target = _normalize_energy_target(target_id)
    return f'mv-energy {energy_id} {normalized_target}'


def _normalize_create_energy(token_id: str, owner: str, holder_id: str, attached_card_id: str) -> str:
    return f'create_energy {token_id} {owner} {holder_id} {attached_card_id}'


def _normalize_create_card(
    card_id: str,
    owner: str,
    card_type: str,
    holder_id: str,
    card_class: str,
    has_atk_1: str,
    has_active: str,
    has_atk_2: str,
    hp: float,
    max_hp: float,
    attached_card_id: str,
) -> str:
    return (
        f'create_card {card_id} {owner} {card_type} {holder_id} {card_class} '
        f'{has_atk_1} {has_active} {has_atk_2} {hp:g} {max_hp:g} {attached_card_id}'
    )


def _normalize_phase(phase_value: str) -> str:
    return f'phase {phase_value}'


def _normalize_turn(player: str) -> str:
    return f'turn {player}'


def _normalize_stat(player: str, attribute: str, value: float) -> str:
    return f'stat {player} {attribute} {value:g}'


def _normalize_flip(card_id: str) -> str:
    return f'flip {card_id}'


def _normalize_hp(card_id: str, hp_value: float, max_hp: float) -> str:
    return f'hp {card_id} {hp_value:g} {max_hp:g}'


def _normalize_maxhp(card_id: str, max_hp: float) -> str:
    return f'maxhp {card_id} {max_hp:g}'


def _normalize_border(card_id: str, hex_color: str) -> str:
    return f'border {card_id} {hex_color}'


def _normalize_changetype(card_id: str, avge_card_type: str) -> str:
    return f'changetype {card_id} {avge_card_type}'


def _normalize_notify_target(raw_value: str) -> str:
    value = raw_value
    if value == 'both':
        return 'both'
    return _normalize_player(value, 'notify target')


def _normalize_notify(target_player: str, message: str, timeout: int) -> str:
    return f'notify {target_player} {message} {int(timeout)}'


def _normalize_winner(target_player: str) -> str:
    return f'winner {target_player}'


def _normalize_reveal(target_player: str, cards: str) -> str:
    return f'reveal {target_player} {cards}'


def _normalize_boom(card_id: str, asset_tail: str | None) -> str:
    if not asset_tail:
        return f'boom {card_id}'
    return f'boom {card_id} {asset_tail}'


def _normalize_view(view_mode: str | None) -> str:
    if view_mode is None:
        return 'view'
    return f'view {view_mode}'


def _normalize_help() -> str:
    return 'help'


def _normalize_shuffle_animation() -> str:
    return 'shuffle-animation'


def _normalize_unselect_all() -> str:
    return 'unselect-all'


def _normalize_input(input_type: str, message_with_args: str) -> str:
    normalized_type = input_type.replace('_', '-').replace(' ', '-')
    return f'input {normalized_type} {message_with_args}'


def _normalize_set_status(card_id: str, status_effect: str, count: int) -> str:
    return f'set_status {card_id} {status_effect} {count}'


def mv(tokens: list[str]) -> str:
    if len(tokens) < 2 or len(tokens) > 3:
        raise ValueError('Usage: mv [cardid] [cardholderid|target_character_id] [index?]')

    card_id = tokens[0]
    holder_id = tokens[1]
    index = _to_non_negative_int(tokens[2], 'mv index') if len(tokens) == 3 else None
    return _normalize_mv(card_id, holder_id, index)


def rm(tokens: list[str]) -> str:
    if len(tokens) != 1:
        raise ValueError('Usage: rm [energyid]')
    energy_id = tokens[0]
    return _normalize_rm(energy_id)


def mv_energy(tokens: list[str]) -> str:
    if len(tokens) != 2:
        raise ValueError('Usage: mv-energy [energyid] [target_card_id|shared-energy|energy-discard]')
    energy_id = tokens[0]
    target_id = tokens[1]
    return _normalize_mv_energy(energy_id, target_id)


def create_energy(tokens: list[str]) -> str:
    if len(tokens) != 4:
        raise ValueError('Usage: create_energy [energyid] [player-1|player-2] [energyholderid] [attached_card_id|none]')
    token_id = tokens[0]
    owner = _normalize_player(tokens[1], 'create_energy owner')
    holder_id = tokens[2]
    attached_card_id = _normalize_attached_card(tokens[3])
    return _normalize_create_energy(token_id, owner, holder_id, attached_card_id)


def create_card(tokens: list[str]) -> str:
    if len(tokens) != 11:
        raise ValueError(
            'Usage: create_card [cardid] [player-1|player-2] [character|tool|item|stadium|supporter] '
            '[cardholderid] [card_class] [has_atk_1] [has_active] [has_atk_2] [hp] [maxhp] [attached_card_id|none]'
        )

    card_id = tokens[0]
    owner = _normalize_player(tokens[1], 'create_card owner')
    card_type = tokens[2]
    if card_type not in {'character', 'tool', 'item', 'stadium', 'supporter'}:
        raise ValueError('create_card type must be character, tool, item, stadium, or supporter')

    holder_id = tokens[3]
    card_class = tokens[4]
    has_atk_1 = tokens[5]
    has_active = tokens[6]
    has_atk_2 = tokens[7]
    hp = _to_float(tokens[8])
    max_hp = _to_float(tokens[9])
    attached_card_id = _normalize_attached_card(tokens[10])

    return _normalize_create_card(
        card_id,
        owner,
        card_type,
        holder_id,
        card_class,
        has_atk_1,
        has_active,
        has_atk_2,
        hp,
        max_hp,
        attached_card_id,
    )


def phase(tokens: list[str]) -> str:
    if len(tokens) != 1:
        raise ValueError('Usage: phase [no-input|phase2|atk]')
    phase_value = tokens[0]
    if phase_value not in {'no-input', 'phase2', 'atk'}:
        raise ValueError('phase must be one of: no-input, phase2, atk')
    return _normalize_phase(phase_value)


def turn(tokens: list[str]) -> str:
    if len(tokens) != 1:
        raise ValueError('Usage: turn [player-1|player-2]')
    player = _normalize_player(tokens[0], 'turn')
    return _normalize_turn(player)


def stat(tokens: list[str]) -> str:
    if len(tokens) != 3:
        raise ValueError('Usage: stat [player-1|player-2] [attribute] [value]')
    player = _normalize_player(tokens[0], 'stat player')
    attribute = tokens[1]
    value = _to_float(tokens[2])
    return _normalize_stat(player, attribute, value)


def flip(tokens: list[str]) -> str:
    if len(tokens) != 1:
        raise ValueError('Usage: flip [cardid]')
    card_id = tokens[0]
    return _normalize_flip(card_id)


def hp(tokens: list[str]) -> str:
    if len(tokens) != 3:
        raise ValueError('Usage: hp [cardid] [hp] [maxhp]')
    card_id = tokens[0]
    hp_value = _to_float(tokens[1])
    max_hp = _to_float(tokens[2])
    return _normalize_hp(card_id, hp_value, max_hp)


def maxhp(tokens: list[str]) -> str:
    if len(tokens) != 2:
        raise ValueError('Usage: maxhp [cardid] [maxhp]')
    card_id = tokens[0]
    max_hp = _to_float(tokens[1])
    if max_hp < 0:
        raise ValueError('maxhp value must be non-negative')
    return _normalize_maxhp(card_id, max_hp)


def border(tokens: list[str]) -> str:
    if len(tokens) != 2:
        raise ValueError('Usage: border [cardid] [hex]')
    card_id = tokens[0]
    hex_color = tokens[1]
    return _normalize_border(card_id, hex_color)


def changetype(tokens: list[str]) -> str:
    if len(tokens) != 2:
        raise ValueError('Usage: changetype [cardid] [NONE|WW|PERC|PIANO|STRING|GUITAR|CHOIR|BRASS]')
    card_id = tokens[0]
    raw_type = tokens[1].upper()
    normalized_type = 'NONE' if raw_type == 'ALL' else raw_type
    if normalized_type not in {'NONE', 'WW', 'PERC', 'PIANO', 'STRING', 'GUITAR', 'CHOIR', 'BRASS'}:
        raise ValueError('changetype type must be one of: NONE, WW, PERC, PIANO, STRING, GUITAR, CHOIR, BRASS')
    return _normalize_changetype(card_id, normalized_type)


def notify(tokens: list[str]) -> str:
    if len(tokens) < 3:
        raise ValueError('Usage: notify [player-1|player-2|both] [msg] [timeout]')

    target_player = _normalize_notify_target(tokens[0])
    try:
        timeout = int(tokens[-1])
    except ValueError as exc:
        raise ValueError('notify timeout must be an integer') from exc

    message_tokens = tokens[1:-1]

    message = ' '.join(message_tokens).strip()
    if not message:
        raise ValueError('notify message must not be empty')

    return _normalize_notify(target_player, message, timeout=timeout)


def winner(tokens: list[str]) -> str:
    if len(tokens) != 1:
        raise ValueError('Usage: winner [player-1|player-2]')
    target_player = _normalize_player(tokens[0], 'winner target')
    return _normalize_winner(target_player)


def reveal(tokens: list[str]) -> str:
    if len(tokens) < 2:
        raise ValueError('Usage: reveal [player-1|player-2] [list of cards]')
    target_player = _normalize_player(tokens[0], 'reveal target')
    cards = ' '.join(tokens[1:])
    return _normalize_reveal(target_player, cards)


def boom(tokens: list[str]) -> str:
    if len(tokens) < 1:
        raise ValueError('Usage: boom [cardid] [asset?]')
    card_id = tokens[0]
    asset_tail = ' '.join(tokens[1:]) if len(tokens) > 1 else None
    return _normalize_boom(card_id, asset_tail)


def view(tokens: list[str]) -> str:
    if len(tokens) == 0:
        return _normalize_view(None)
    if len(tokens) != 1:
        raise ValueError('Usage: view [admin|player-1|player-2]')

    view_mode = tokens[0]
    if view_mode not in {'admin', 'player-1', 'player-2'}:
        raise ValueError('view must be admin, player-1, or player-2')
    return _normalize_view(view_mode)


def help_command(tokens: list[str]) -> str:
    if tokens:
        raise ValueError('Usage: help')
    return _normalize_help()


def shuffle_animation(tokens: list[str]) -> str:
    if tokens:
        raise ValueError('Usage: shuffle-animation')
    return _normalize_shuffle_animation()


def unselect_all(tokens: list[str]) -> str:
    if tokens:
        raise ValueError('Usage: unselect-all')
    return _normalize_unselect_all()


def input_command(tokens: list[str]) -> str:
    if len(tokens) < 2:
        raise ValueError('Usage: input [type] [msg] [..args]')
    input_type = tokens[0]
    message_with_args = ' '.join(tokens[1:])
    return _normalize_input(input_type, message_with_args)


def set_status(tokens: list[str]) -> str:
    if len(tokens) != 3:
        raise ValueError('Usage: set_status [card_id] [status_effect] [count]')
    card_id = tokens[0]
    status_effect = tokens[1]
    count = _to_non_negative_int(tokens[2], 'set_status count')
    return _normalize_set_status(card_id, status_effect, count)


COMMAND_HANDLERS: dict[str, Callable[[list[str]], str]] = {
    'help': help_command,
    '?': help_command,
    'mv': mv,
    'rm': rm,
    'mv-energy': mv_energy,
    'mvenergy': mv_energy,
    'create_energy': create_energy,
    'create-energy': create_energy,
    'create_card': create_card,
    'create-card': create_card,
    'phase': phase,
    'game-phase': phase,
    'turn': turn,
    'player-turn': turn,
    'stat': stat,
    'flip': flip,
    'hp': hp,
    'maxhp': maxhp,
    'max-hp': maxhp,
    'border': border,
    'changetype': changetype,
    'change-type': changetype,
    'input': input_command,
    'set_status': set_status,
    'set-status': set_status,
    'notify': notify,
    'winner': winner,
    'reveal': reveal,
    'boom': boom,
    'view': view,
    'shuffle-animation': shuffle_animation,
    'unselect-all': unselect_all,
    'unselectall': unselect_all,
}


def normalize_scanner_command(raw_command: str) -> tuple[str, str]:
    tokens = _split_command(raw_command)
    if not tokens:
        raise ValueError('Scanner command cannot be empty')

    action = tokens[0]
    handler = COMMAND_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f'Unknown scanner command: {action}')

    normalized = handler(tokens[1:])
    return action, normalized