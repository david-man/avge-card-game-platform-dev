from __future__ import annotations

from threading import Condition, RLock

from card_game.server.protocol.protocol_command_queue import (
    acknowledge_head_command,
    build_command_packet,
    classify_command_response_category,
    classify_required_ack_slots,
)
from card_game.server.models.server_models import MultiplayerTransportState
from card_game.server.models.server_models import PendingCommandAck


def _normalize_client_slot(raw):
    if raw in {'p1', 'p2'}:
        return raw
    return None


def test_notify_both_with_timeout_targets_both_connected_slots() -> None:
    transport_state = MultiplayerTransportState()
    transport_state.sid_by_slot['p1'] = 'sid-p1'
    transport_state.sid_by_slot['p2'] = 'sid-p2'

    required = classify_required_ack_slots(
        'notify both hello_world -1',
        source_slot=None,
        transport_state=transport_state,
        normalize_client_slot=_normalize_client_slot,
    )

    assert required == {'p1', 'p2'}


def test_notify_single_player_with_timeout_targets_both_connected_slots() -> None:
    transport_state = MultiplayerTransportState()
    transport_state.sid_by_slot['p1'] = 'sid-p1'
    transport_state.sid_by_slot['p2'] = 'sid-p2'

    required = classify_required_ack_slots(
        'notify player-2 hello_world 4',
        source_slot=None,
        transport_state=transport_state,
        normalize_client_slot=_normalize_client_slot,
    )

    assert required == {'p1', 'p2'}


def test_reveal_both_targets_both_connected_slots() -> None:
    transport_state = MultiplayerTransportState()
    transport_state.sid_by_slot['p1'] = 'sid-p1'
    transport_state.sid_by_slot['p2'] = 'sid-p2'

    required = classify_required_ack_slots(
        'reveal both [card-1] revealed_card 5',
        source_slot=None,
        transport_state=transport_state,
        normalize_client_slot=_normalize_client_slot,
    )

    assert required == {'p1', 'p2'}


def test_reveal_single_player_still_targets_both_connected_slots() -> None:
    transport_state = MultiplayerTransportState()
    transport_state.sid_by_slot['p1'] = 'sid-p1'
    transport_state.sid_by_slot['p2'] = 'sid-p2'

    required = classify_required_ack_slots(
        'reveal player-1 [card-1] revealed_card 5',
        source_slot=None,
        transport_state=transport_state,
        normalize_client_slot=_normalize_client_slot,
    )

    assert required == {'p1', 'p2'}


def test_sound_single_player_targets_both_connected_slots() -> None:
    transport_state = MultiplayerTransportState()
    transport_state.sid_by_slot['p1'] = 'sid-p1'
    transport_state.sid_by_slot['p2'] = 'sid-p2'

    required = classify_required_ack_slots(
        'sound player-2 reveal',
        source_slot=None,
        transport_state=transport_state,
        normalize_client_slot=_normalize_client_slot,
    )

    assert required == {'p1', 'p2'}


def test_sound_both_targets_both_connected_slots() -> None:
    transport_state = MultiplayerTransportState()
    transport_state.sid_by_slot['p1'] = 'sid-p1'
    transport_state.sid_by_slot['p2'] = 'sid-p2'

    required = classify_required_ack_slots(
        'sound both reveal',
        source_slot=None,
        transport_state=transport_state,
        normalize_client_slot=_normalize_client_slot,
    )

    assert required == {'p1', 'p2'}


def test_classify_command_response_category_matches_frontend_contract() -> None:
    assert classify_command_response_category('input selection player-1 choose_one [A],[A],1 false false') == 'query_input'
    assert classify_command_response_category('notify both hello_world -1') == 'query_notify'
    assert classify_command_response_category('reveal player-1 [card-1] card_revealed 5') == 'query_notify'
    assert classify_command_response_category('sound player-2 reveal') == 'query_notify'
    assert classify_command_response_category('lock-input p2') == 'lock_state'
    assert classify_command_response_category('unlock_input p1') == 'lock_state'
    assert classify_command_response_category('winner player-1') == 'winner'
    assert classify_command_response_category('phase atk') == 'phase_update'
    assert classify_command_response_category('mv-energy 1 C123') == 'replay_command'


def test_classify_command_response_category_accepts_wire_delimiter() -> None:
    assert classify_command_response_category('notify:;:both:;:hello_world:;:-1') == 'query_notify'
    assert classify_command_response_category('input:;:selection:;:player-1:;:choose_one:;:[A],[A],1 false false') == 'query_input'


def test_build_command_packet_includes_response_category() -> None:
    pending = PendingCommandAck(
        command_id=9,
        command='notify both hello_world -1',
        required_slots={'p1', 'p2'},
    )

    def issue_backend_packet(packet_type: str, body: dict[str, object], is_response: bool) -> dict[str, object]:
        return {
            'PacketType': packet_type,
            'Body': body,
            'IsResponse': is_response,
        }

    def issue_backend_packet_for_session(_session, packet_type: str, body: dict[str, object], is_response: bool) -> dict[str, object]:
        return {
            'PacketType': packet_type,
            'Body': body,
            'IsResponse': is_response,
        }

    packet = build_command_packet(
        pending,
        is_response=True,
        session=None,
        issue_backend_packet=issue_backend_packet,
        issue_backend_packet_for_session=issue_backend_packet_for_session,
    )

    assert packet['PacketType'] == 'command'
    body = packet['Body']
    assert isinstance(body, dict)
    assert body.get('command') == 'notify both hello_world -1'
    assert body.get('command_id') == 9
    assert body.get('target_slots') == ['p1', 'p2']
    assert body.get('response_category') == 'query_notify'


def test_build_command_packet_includes_response_payload_when_present() -> None:
    pending = PendingCommandAck(
        command_id=11,
        command='hp card-1 40 50',
        required_slots={'p1', 'p2'},
        response_payload={
            'animation': {
                'target': 'both',
                'keyframes': [['reveal', 'sound']],
            },
        },
    )

    def issue_backend_packet(packet_type: str, body: dict[str, object], is_response: bool) -> dict[str, object]:
        return {
            'PacketType': packet_type,
            'Body': body,
            'IsResponse': is_response,
        }

    def issue_backend_packet_for_session(_session, packet_type: str, body: dict[str, object], is_response: bool) -> dict[str, object]:
        return {
            'PacketType': packet_type,
            'Body': body,
            'IsResponse': is_response,
        }

    packet = build_command_packet(
        pending,
        is_response=True,
        session=None,
        issue_backend_packet=issue_backend_packet,
        issue_backend_packet_for_session=issue_backend_packet_for_session,
    )

    body = packet['Body']
    assert isinstance(body, dict)
    assert body.get('response_payload') == {
        'animation': {
            'target': 'both',
            'keyframes': [['reveal', 'sound']],
        },
    }


def test_acknowledge_head_command_uses_command_id_when_provided() -> None:
    pending_command_acks = [
        PendingCommandAck(
            command_id=12,
            command='notify both hello_world -1',
            required_slots={'p1'},
        )
    ]

    transport_lock = RLock()
    registration_condition = Condition(transport_lock)

    acked, acked_command = acknowledge_head_command(
        command='notify both hello_world -1',
        source_slot='p1',
        pending_command_acks=pending_command_acks,
        normalize_client_slot=_normalize_client_slot,
        registration_condition=registration_condition,
        transport_lock=transport_lock,
        command_id=999,
    )

    assert acked is False
    assert acked_command is None
    assert len(pending_command_acks) == 1
    assert pending_command_acks[0].acked_slots == set()

    acked, acked_command = acknowledge_head_command(
        command='notify both hello_world -1',
        source_slot='p1',
        pending_command_acks=pending_command_acks,
        normalize_client_slot=_normalize_client_slot,
        registration_condition=registration_condition,
        transport_lock=transport_lock,
        command_id=12,
    )

    assert acked is True
    assert acked_command == 'notify both hello_world -1'
    assert pending_command_acks == []


def test_acknowledge_head_command_requires_command_id() -> None:
    pending_command_acks = [
        PendingCommandAck(
            command_id=13,
            command='phase no-input',
            required_slots={'p1'},
        )
    ]

    transport_lock = RLock()
    registration_condition = Condition(transport_lock)

    acked, acked_command = acknowledge_head_command(
        command='phase no-input',
        source_slot='p1',
        pending_command_acks=pending_command_acks,
        normalize_client_slot=_normalize_client_slot,
        registration_condition=registration_condition,
        transport_lock=transport_lock,
    )

    assert acked is False
    assert acked_command is None
    assert len(pending_command_acks) == 1
    assert pending_command_acks[0].acked_slots == set()
