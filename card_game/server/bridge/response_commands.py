from __future__ import annotations

from typing import Any

from ...avge_abstracts.AVGEEnvironment import GamePhase
from ...constants import (
    AtkPhaseData,
    Data,
    Notify,
    OrderingQuery,
    Phase2Data,
    Pile,
    Response,
    ResponseType,
)
from ...internal_events import (
    AtkPhase,
    AVGECardHPChange,
    AVGECardMaxHPChange,
    AVGECardStatusChange,
    AVGECardTypeChange,
    AVGEEnergyTransfer,
    AVGEPlayerAttributeChange,
    EmptyEvent,
    InputEvent,
    Phase2,
    PhasePickCard,
    PlayCharacterCard,
    ReorderCardholder,
    TransferCard,
    TurnEnd,
)
from ..logging import log_ack_trace_bridge


def commands_from_response(bridge: Any, response: Response) -> list[str]:
    commands: list[str] = []
    response_data = response.data
    source = bridge._current_response_source(response)

    if response.response_type != ResponseType.REQUIRES_QUERY:
        bridge._clear_pending_ordering_query_state()

    if response.response_type == ResponseType.ACCEPT:
        commands.extend(bridge._notification_commands_from_payload(response_data))
        return commands

    if response.response_type == ResponseType.SKIP:
        commands.extend(bridge._notification_commands_from_payload(response_data))
        commands.append('resync')
        bridge._force_environment_sync_pending = True
        return commands

    if response.response_type == ResponseType.FAST_FORWARD:
        commands.extend(bridge._notification_commands_from_payload(response_data))
        return commands

    if response.response_type == ResponseType.GAME_END:
        if len(commands) == 0:
            commands.extend(bridge._fallback_payload_command(response, response_data))
        return commands

    if response.response_type == ResponseType.REQUIRES_QUERY:
        if isinstance(response_data, OrderingQuery):
            ordering_command = bridge._build_ordering_query_command(response_data)
            if ordering_command is not None:
                commands.append(ordering_command)
            return commands

        bridge._clear_pending_ordering_query_state()

        if isinstance(response_data, Phase2Data):
            bridge._append_phase_command_if_changed(commands, GamePhase.PHASE_2)
            return commands

        if isinstance(response_data, AtkPhaseData):
            bridge._append_phase_command_if_changed(commands, GamePhase.ATK_PHASE)
            return commands

        if isinstance(source, (PhasePickCard, Phase2, AtkPhase)) or isinstance(response_data, (Phase2Data, AtkPhaseData)):
            # Phase events may surface as REQUIRES_QUERY (for example Phase2
            # waiting for player action) without emitting a CORE response.
            # Keep frontend phase HUD/state in sync in this path too.
            bridge._append_phase_command_if_changed(commands, bridge.env.game_phase)
        if isinstance(source, InputEvent):
            query_data = getattr(source, 'query_data', Data())
            if not isinstance(query_data, Data):
                log_ack_trace_bridge(
                    'uncovered_input_query_data',
                    payload_type=type(query_data).__name__,
                )
                commands.extend(bridge._notify_both('UNHANDLED_QUERY_DATA'))
                return commands

            if bridge._pending_input_query_event is source:
                pending_command = bridge._pending_input_query_command
                if isinstance(pending_command, str) and pending_command.strip():
                    log_ack_trace_bridge('duplicate_input_query_blocked_by_latch')
                    return commands
                bridge._clear_pending_input_query_state()

            input_command = bridge._build_input_command(source, query_data)
            if input_command:
                normalized_input_command = input_command.strip()
                commands.append(normalized_input_command)
                bridge._pending_input_query_event = source
                bridge._pending_input_query_command = normalized_input_command
            else:
                payload_name = type(query_data).__name__
                log_ack_trace_bridge(
                    'uncovered_input_query_data',
                    payload_type=payload_name,
                )
                if not bridge._is_plain_data_payload(query_data):
                    commands.extend(bridge._notify_both(f'UNHANDLED_{payload_name}'))
            return commands

        if isinstance(response_data, Notify):
            commands.extend(bridge._notify_from_notify(response_data))
        if len(commands) == 0:
            commands.extend(bridge._fallback_payload_command(response, response_data))
        return commands

    if response.response_type != ResponseType.CORE:
        if len(commands) == 0:
            commands.extend(bridge._fallback_payload_command(response, response_data))
        return commands

    payload_notification_commands = bridge._notification_commands_from_payload(response_data)

    def _return_core_commands() -> list[str]:
        commands.extend(payload_notification_commands)
        return commands

    if isinstance(source, AVGECardHPChange):
        commands.append(f'hp {source.target_card.unique_id} {int(source.target_card.hp)} {int(source.target_card.max_hp)}')
        return _return_core_commands()

    if isinstance(source, AVGECardMaxHPChange):
        commands.append(f'maxhp {source.target_card.unique_id} {int(source.target_card.max_hp)}')
        return _return_core_commands()

    if isinstance(source, AVGECardTypeChange):
        card_type = bridge._card_type_command_token(source.target_card.card_type)
        commands.append(f'changetype {source.target_card.unique_id} {card_type}')
        return _return_core_commands()

    if isinstance(source, AVGECardStatusChange):
        status_key = str(source.status_effect).split('.')[-1]
        status_name = {
            'ARR': 'Arranger',
            'GOON': 'Goon',
            'MAID': 'Maid',
        }.get(status_key, status_key.title())
        count = len(source.target.statuses_attached[source.status_effect])
        commands.append(f'set_status {source.target.unique_id} {status_name} {count}')
        return _return_core_commands()

    if isinstance(source, AVGEEnergyTransfer):
        energy_target = bridge._energy_target_command_arg(source.target)
        if energy_target:
            commands.append(f'mv-energy {source.token.unique_id} {energy_target}')
        return _return_core_commands()

    if isinstance(source, AVGEPlayerAttributeChange):
        player_token = bridge._player_id_to_frontend(source.target_player.unique_id)
        commands.append(f'stat {player_token} {source.attribute} {int(source.target_player.attributes[source.attribute])}')
        return _return_core_commands()

    if isinstance(source, TransferCard):
        move_target = bridge._transfer_target_command_arg(source)
        if move_target:
            same_holder_transfer = source.pile_from == source.pile_to
            pile_to_type = getattr(source.pile_to, 'pile_type', None)
            if same_holder_transfer and pile_to_type in {Pile.DECK, Pile.DISCARD}:
                commands.append(
                    f'shuffle-single-card {source.card.unique_id} {bridge._normalize_zone_id(move_target)}'
                )
            else:
                commands.append(f'mv {source.card.unique_id} {move_target}')
        return _return_core_commands()

    if isinstance(source, ReorderCardholder):
        target_holder_id = bridge._reorder_target_command_arg(source)
        if target_holder_id:
            commands.append(f'shuffle-animation {target_holder_id}')
        else:
            commands.append('shuffle-animation')
        return _return_core_commands()

    if isinstance(source, PlayCharacterCard):
        if len(commands) == 0 and len(payload_notification_commands) == 0:
            commands.extend(bridge._fallback_payload_command(response, response_data))

        return _return_core_commands()

    if isinstance(source, PhasePickCard):
        bridge._append_phase_command_if_changed(commands, bridge.env.game_phase)
        return _return_core_commands()

    if isinstance(source, Phase2):
        bridge._append_phase_command_if_changed(commands, bridge.env.game_phase)
        return _return_core_commands()

    if isinstance(source, AtkPhase):
        bridge._append_phase_command_if_changed(commands, bridge.env.game_phase)
        return _return_core_commands()

    if isinstance(source, InputEvent):
        # Successful input application has no direct frontend mutation command.
        return _return_core_commands()

    if isinstance(source, TurnEnd):
        bridge._force_environment_sync_pending = True
        return _return_core_commands()

    if isinstance(source, EmptyEvent):
        return _return_core_commands()

    if len(commands) == 0 and len(payload_notification_commands) == 0:
        commands.extend(bridge._fallback_payload_command(response, response_data))

    return _return_core_commands()
