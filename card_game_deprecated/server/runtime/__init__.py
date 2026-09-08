"""Runtime server feature modules."""

from .config import env_csv, resolve_init_finalize_timeout_seconds
from .init_stage import (
    build_finalized_bridge_from_init_submissions,
    enqueue_init_state_for_connected_clients,
    init_state_body_for_slot,
    other_slot,
    remove_pending_packets_by_type,
    validate_init_setup_submission,
)
from .session_binding import (
    expected_slot_for_router_session,
    recover_reconnect_token_for_expected_slot,
    short_session_id,
)
from .lifecycle import (
    mark_room_finished_once,
    notify_router_room_finished,
    schedule_both_disconnected_termination_if_needed,
    schedule_process_termination,
)
from .environment_sync import environment_body_for_client, enqueue_environment_for_connected_clients
from .bridge_adapter import extract_bridge_commands, bridge_requests_force_environment_sync
from .packet_dispatch import (
    augment_protocol_response_with_pending_peer_ack,
    blocked_pending_command_for_slot,
    effective_protocol_slot,
    emit_pending_packets_to_connected_clients,
    issue_environment_resync_packet_for_source,
    protocol_packets_emit_payload_for_slot,
)
from .command_flow import (
    emit_pending_peer_ack_status_to_connected_clients,
    emit_ready_commands_to_connected_clients,
    enqueue_bridge_commands,
)
from .bridge_runtime import (
    force_environment_sync_for_connected_clients,
    handle_bridge_runtime_error,
)
from .protocol_service import process_protocol_packet
from .transport_disconnect import handle_transport_sid_disconnect
from .session_admin import replace_room_session
from .socket_transport import (
    emit_server_connected,
    handle_client_unloading,
    handle_disconnect,
    handle_protocol_socket_event,
    register_client_or_play,
)
from .http_api import (
    apply_cors_headers,
    handle_protocol_http,
    handle_scanner_input_http,
    health_response,
)

__all__ = [
    'env_csv',
    'resolve_init_finalize_timeout_seconds',
    'build_finalized_bridge_from_init_submissions',
    'enqueue_init_state_for_connected_clients',
    'init_state_body_for_slot',
    'other_slot',
    'remove_pending_packets_by_type',
    'validate_init_setup_submission',
    'expected_slot_for_router_session',
    'recover_reconnect_token_for_expected_slot',
    'short_session_id',
    'mark_room_finished_once',
    'notify_router_room_finished',
    'schedule_both_disconnected_termination_if_needed',
    'schedule_process_termination',
    'environment_body_for_client',
    'enqueue_environment_for_connected_clients',
    'extract_bridge_commands',
    'bridge_requests_force_environment_sync',
    'blocked_pending_command_for_slot',
    'effective_protocol_slot',
    'augment_protocol_response_with_pending_peer_ack',
    'protocol_packets_emit_payload_for_slot',
    'issue_environment_resync_packet_for_source',
    'emit_pending_packets_to_connected_clients',
    'enqueue_bridge_commands',
    'emit_ready_commands_to_connected_clients',
    'emit_pending_peer_ack_status_to_connected_clients',
    'handle_bridge_runtime_error',
    'force_environment_sync_for_connected_clients',
    'process_protocol_packet',
    'handle_transport_sid_disconnect',
    'replace_room_session',
    'emit_server_connected',
    'register_client_or_play',
    'handle_protocol_socket_event',
    'handle_client_unloading',
    'handle_disconnect',
    'apply_cors_headers',
    'health_response',
    'handle_protocol_http',
    'handle_scanner_input_http',
]
