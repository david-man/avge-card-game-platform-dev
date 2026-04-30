"""Bridge feature modules for game runner refactors."""

from .setup_defaults import (
    apply_selected_cards_to_setup,
    blank_player_setup,
    resolve_catalog_card_class,
    selected_cards_from_env,
)
from .setup_payload import (
    build_default_setup_payload_from_environment,
    build_environment_from_default_setups,
    environment_to_setup_json,
    environment_to_setup_payload,
)
from .notifications import (
    normalize_notify_timeout,
    notify_from_notify,
    notify_targets_from_players,
    notification_commands_from_payload,
    reveal_commands_for_players,
)
from .input_queries import (
    build_input_command,
    build_ordering_listener_state,
    build_ordering_query_command,
    parse_frontend_input_result,
    parse_ordered_selection_tokens,
    resolve_ordered_listeners,
    should_skip_duplicate_ordering_query,
)
from .pending_input_query import (
    clear_pending_input_query_state,
    is_pending_input_query_already_queued,
    is_pending_input_query_in_flight,
    is_waiting_for_pending_input_query_for_bridge,
    is_waiting_for_pending_input_query,
    normalize_pending_input_query_command,
    queue_pending_input_query_resend,
    should_wait_for_ordering_result,
    should_wait_for_pending_input_result,
)
from .response_commands import (
    commands_from_response,
)
from .frontend_events import (
    apply_frontend_event,
    phase2_args_from_frontend_event,
)
from .engine_drain import (
    auto_advance_when_idle,
    drain_engine,
)
from .environment_sync import (
    sync_environment_commands,
)
from .active_ability import (
    queue_active_ability_interrupt,
)
from .winner_resolution import (
    frontend_player_token,
    normalize_winner_label,
    player_from_frontend_token,
    winner_command_from_environment,
    winner_command_from_surrender_payload,
    winner_label_for_token,
)
from .outbound_pump import (
    pump_outbound_until_next_command,
)
from .frontend_router import (
    build_frontend_event_response,
    handle_frontend_event_locked,
)
from .response_payloads import (
    animation_payload_from_response,
    fallback_payload_command,
    response_payloads_for_commands,
)
from .startup_cycle import (
    bootstrap_phase_cycle,
    prime_engine_for_frontend_inputs,
)
from .response_introspection import (
    current_response_source,
    has_nonempty_payload,
    is_plain_data_payload,
    log_engine_response_entry,
    response_data_keys,
    response_source_summary,
    should_emit_core_commands_before_reactors,
)
from .command_utils import (
    canonical_event_name,
    card_id_from_payload,
    card_type_command_token,
    card_zone_id,
    command_token,
    csv_from_display_entries,
    energy_target_command_arg,
    frontend_phase_token,
    get_card,
    get_character_card,
    get_energy_token,
    normalize_action_name,
    normalize_zone_id,
    pick_str,
    player_id_to_frontend,
    reorder_target_command_arg,
    transfer_target_command_arg,
)
from .init_setup import (
    build_player_setup_for_init,
)
from .ack_flow import (
    accept_frontend_ack,
    append_phase_command_if_changed,
    emit_next_command_if_ready,
)
from .ordering_query_flow import (
    build_ordering_query_command_for_bridge,
    parse_ordering_query_result_for_bridge,
)
from .frontend_enqueue import (
    enqueue_frontend_event_work,
)
from .clone_setup import (
    clone_with_init_setup,
)

__all__ = [
    'blank_player_setup',
    'resolve_catalog_card_class',
    'selected_cards_from_env',
    'apply_selected_cards_to_setup',
    'build_environment_from_default_setups',
    'build_default_setup_payload_from_environment',
    'environment_to_setup_payload',
    'environment_to_setup_json',
    'normalize_notify_timeout',
    'notify_targets_from_players',
    'notify_from_notify',
    'reveal_commands_for_players',
    'notification_commands_from_payload',
    'build_input_command',
    'parse_frontend_input_result',
    'build_ordering_listener_state',
    'should_skip_duplicate_ordering_query',
    'build_ordering_query_command',
    'parse_ordered_selection_tokens',
    'resolve_ordered_listeners',
    'clear_pending_input_query_state',
    'is_waiting_for_pending_input_query',
    'is_waiting_for_pending_input_query_for_bridge',
    'normalize_pending_input_query_command',
    'queue_pending_input_query_resend',
    'is_pending_input_query_in_flight',
    'is_pending_input_query_already_queued',
    'should_wait_for_ordering_result',
    'should_wait_for_pending_input_result',
    'commands_from_response',
    'apply_frontend_event',
    'phase2_args_from_frontend_event',
    'auto_advance_when_idle',
    'drain_engine',
    'sync_environment_commands',
    'queue_active_ability_interrupt',
    'winner_command_from_surrender_payload',
    'winner_command_from_environment',
    'frontend_player_token',
    'player_from_frontend_token',
    'winner_label_for_token',
    'normalize_winner_label',
    'pump_outbound_until_next_command',
    'build_frontend_event_response',
    'handle_frontend_event_locked',
    'animation_payload_from_response',
    'response_payloads_for_commands',
    'fallback_payload_command',
    'bootstrap_phase_cycle',
    'prime_engine_for_frontend_inputs',
    'response_source_summary',
    'current_response_source',
    'response_data_keys',
    'should_emit_core_commands_before_reactors',
    'is_plain_data_payload',
    'has_nonempty_payload',
    'log_engine_response_entry',
    'card_type_command_token',
    'energy_target_command_arg',
    'transfer_target_command_arg',
    'reorder_target_command_arg',
    'card_zone_id',
    'frontend_phase_token',
    'player_id_to_frontend',
    'card_id_from_payload',
    'pick_str',
    'get_card',
    'get_character_card',
    'get_energy_token',
    'csv_from_display_entries',
    'command_token',
    'canonical_event_name',
    'normalize_action_name',
    'normalize_zone_id',
    'build_player_setup_for_init',
    'accept_frontend_ack',
    'emit_next_command_if_ready',
    'append_phase_command_if_changed',
    'build_ordering_query_command_for_bridge',
    'parse_ordering_query_result_for_bridge',
    'enqueue_frontend_event_work',
    'clone_with_init_setup',
]
