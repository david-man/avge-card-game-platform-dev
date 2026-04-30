from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload

from ...avge_abstracts.AVGEEnvironment import GamePhase
from ...avge_abstracts.AVGECards import (
    AVGECharacterCard,
    AVGEItemCard,
    AVGEStadiumCard,
    AVGESupporterCard,
    AVGEToolCard,
)
from ...constants import ActionTypes
from ...internal_events import AtkPhase, InputEvent, Phase2
from ..logging import log_energy_move, log_input_trace


def phase2_args_from_frontend_event(
    bridge: Any,
    event_name: str,
    data: JsonObject,
) -> JsonObject | None:
    if event_name == 'phase2_attack_button_clicked':
        return {'next': 'atk'}

    if event_name == 'tool_attached':
        tool_id = bridge._pick_str(data, 'tool_card_id')
        target_id = bridge._pick_str(data, 'attached_to_card_id')
        tool = bridge._get_card(tool_id)
        attach_to = bridge._get_character_card(target_id)
        if isinstance(tool, AVGEToolCard) and isinstance(attach_to, AVGECharacterCard):
            return {'next': 'tool', 'tool': tool, 'attach_to': attach_to}

    if event_name == 'item_supporter_use':
        card_id = bridge._card_id_from_payload(data)
        card = bridge._get_card(card_id)
        if isinstance(card, AVGEItemCard):
            return {'next': 'item', 'item_card': card}
        if isinstance(card, AVGESupporterCard):
            return {'next': 'supporter', 'supporter_card': card}

    if event_name == 'card_moved':
        card = bridge._get_card(bridge._card_id_from_payload(data))
        to_zone = bridge._pick_str(data, 'to_zone_id')
        if card is None or not to_zone:
            return None

        to_zone = bridge._normalize_zone_id(to_zone)
        current_zone = bridge._card_zone_id(card)
        if not current_zone:
            return None

        if to_zone == 'stadium' and isinstance(card, AVGEStadiumCard):
            return {'next': 'stadium', 'stadium_card': card}

        if isinstance(card, AVGECharacterCard):
            if current_zone.endswith('-bench') and to_zone.endswith('-active'):
                return {'next': 'swap', 'bench_card': card}
            if current_zone.endswith('-hand') and to_zone.endswith('-bench'):
                return {'next': 'hand2bench', 'hand2bench': card}

    if event_name == 'energy_moved':
        to_attached = bridge._pick_str(data, 'to_attached_to_card_id')
        to_zone = bridge._pick_str(data, 'to_zone_id')
        energy_id = bridge._pick_str(data, 'energy_id')
        target_card: AVGECharacterCard | None = None
        if to_attached:
            target_card = bridge._get_character_card(to_attached)
        elif isinstance(to_zone, str):
            normalized_to_zone = bridge._normalize_zone_id(to_zone)
            if normalized_to_zone.endswith('-bench') or normalized_to_zone.endswith('-active'):
                target_card = bridge._get_character_card(bridge._pick_str(data, 'to_card_id'))

        if isinstance(target_card, AVGECharacterCard):
            selected_token = bridge._get_energy_token(energy_id)
            if selected_token is not None:
                return {'next': 'energy', 'attach_to': target_card, 'token': selected_token}
            return {'next': 'energy', 'attach_to': target_card}

    # Allow card_action active ability in phase2.
    if event_name == 'card_action':
        action = bridge._normalize_action_name(data.get('action'))
        if action == 'activate_ability':
            card = bridge._get_character_card(bridge._card_id_from_payload(data))
            if card is not None:
                bridge._queue_active_ability_interrupt(card, bridge.env._engine.event_running)

    return None


def apply_frontend_event(
    bridge: Any,
    event_name: str,
    data: JsonObject,
) -> tuple[list[str], JsonObject | None]:
    commands: list[str] = []
    engine = bridge.env._engine
    running = engine.event_running

    if event_name == 'input_result':
        log_input_trace(
            'bridge_apply_input_result_start',
            running_type=type(running).__name__ if running is not None else 'None',
            payload_keys=sorted(data.keys()),
        )
        ordering_args = bridge._parse_ordering_query_result(data)
        if ordering_args is not None:
            log_input_trace(
                'bridge_apply_input_result_ordering_query',
                result_keys=sorted(ordering_args.keys()),
            )
            return commands, ordering_args

    # Backend state is authoritative for phase navigation.
    if event_name == 'phase2_attack_button_clicked':
        if bridge.env.game_phase == GamePhase.PHASE_2:
            return commands, {'next': 'atk'}
        return commands, None

    if event_name == 'atk_skip_button_clicked':
        if bridge.env.game_phase == GamePhase.ATK_PHASE:
            return commands, {'type': ActionTypes.SKIP}
        return commands, None

    if event_name == 'surrender_result':
        winner_command = bridge._winner_command_from_surrender_payload(data)
        if winner_command is not None:
            commands.append(winner_command)
        return commands, None

    if isinstance(running, InputEvent) and event_name == 'input_result':
        input_args = bridge._parse_frontend_input_result(running, data)
        if input_args is not None:
            bridge._clear_pending_input_query_state()
            log_input_trace(
                'bridge_apply_input_result_accepted',
                input_keys=sorted(input_args.keys()),
            )
            return commands, input_args
        log_input_trace('bridge_apply_input_result_rejected')
        commands.extend(bridge._notify_both('Input result rejected by backend parser.'))
        return commands, None

    if event_name == 'input_result':
        log_input_trace(
            'bridge_apply_input_result_no_running_input_event',
            running_type=type(running).__name__ if running is not None else 'None',
        )
        return commands, None

    if event_name == 'energy_moved':
        running_name = type(running).__name__ if running is not None else 'None'
        game_phase = bridge._frontend_phase_token(bridge.env.game_phase)
        in_phase2 = isinstance(running, Phase2) or (running is None and bridge.env.game_phase == GamePhase.PHASE_2)
        if not in_phase2:
            log_energy_move(
                status='ignored',
                reason='not_phase2',
                running=running_name,
                game_phase=game_phase,
                payload=data,
            )
            commands.extend(bridge._notify_both(f'Ignored energy move request: backend phase is {bridge._frontend_phase_token(bridge.env.game_phase)}'))
            return commands, None

        phase_args = phase2_args_from_frontend_event(bridge, event_name, data)
        if phase_args is not None:
            attach_to = phase_args.get('attach_to') if isinstance(phase_args, dict) else None
            token = phase_args.get('token') if isinstance(phase_args, dict) else None
            log_energy_move(
                status='accepted',
                reason='valid_phase2_attach',
                running=running_name,
                game_phase=game_phase,
                payload=data,
                attach_to=str(getattr(attach_to, 'unique_id', None)),
                token=str(getattr(token, 'unique_id', None)),
            )
            return commands, phase_args

        log_energy_move(
            status='ignored',
            reason='invalid_target_or_token',
            running=running_name,
            game_phase=game_phase,
            payload=data,
        )
        commands.extend(bridge._notify_both('Ignored energy move request: missing/invalid energy target or token.'))
        return commands, None

    if event_name == 'card_action':
        action = bridge._normalize_action_name(data.get('action'))
        card_id = bridge._card_id_from_payload(data)
        card = bridge._get_character_card(card_id)
        if action == 'activate_ability':
            if card is not None:
                commands.extend(bridge._queue_active_ability_interrupt(card, running))
            return commands, None

        if isinstance(running, AtkPhase) or (running is None and bridge.env.game_phase == GamePhase.ATK_PHASE):
            active = bridge.env.get_active_card(bridge.env.player_turn.unique_id)
            if isinstance(active, AVGECharacterCard) and card is not None and active.unique_id == card.unique_id:
                if action == 'atk1':
                    return commands, {'type': ActionTypes.ATK_1}
                if action == 'atk2':
                    return commands, {'type': ActionTypes.ATK_2}

    if isinstance(running, Phase2) or (running is None and bridge.env.game_phase == GamePhase.PHASE_2):
        phase_args = phase2_args_from_frontend_event(bridge, event_name, data)
        if phase_args is not None:
            return commands, phase_args

    return commands, None
