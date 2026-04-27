from __future__ import annotations

from typing import Any

from card_game.server import server
from card_game.server.server_models import PendingCommandAck
from card_game.server.server_models import MultiplayerTransportState


class _FakeBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def handle_frontend_event(
        self,
        event_type: str,
        response_data: dict[str, Any] | None,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self.calls.append((event_type, response_data or {}, context or {}))
        return {
            'commands': [],
            'setup_payload': {},
            'force_environment_sync': False,
        }


def _stub_server_for_packet_test(monkeypatch, fake_bridge: _FakeBridge, stage: str = 'init') -> None:
    monkeypatch.setattr(server, 'frontend_game_bridge', fake_bridge)
    monkeypatch.setattr(server, 'room_stage', stage)
    monkeypatch.setattr(server, 'protocol_seq', 0)
    monkeypatch.setattr(server, 'pending_command_acks', [])

    monkeypatch.setattr(server, '_commands_ready_for_slot', lambda source_slot, is_response, session=None: [])
    monkeypatch.setattr(server, '_emit_ready_commands_to_connected_clients', lambda: None)
    monkeypatch.setattr(server, '_acknowledge_head_command', lambda command, source_slot: (False, None))
    monkeypatch.setattr(server, '_extract_bridge_commands', lambda result: [])
    monkeypatch.setattr(server, '_enqueue_bridge_commands', lambda commands, source_slot=None: None)
    monkeypatch.setattr(server, '_bridge_requests_force_environment_sync', lambda result: False)
    monkeypatch.setattr(server, '_force_environment_sync_for_connected_clients', lambda: None)


def test_update_frontend_input_response_not_ignored_during_init(monkeypatch) -> None:
    fake_bridge = _FakeBridge()
    _stub_server_for_packet_test(monkeypatch, fake_bridge, stage='init')

    payload = {
        'ACK': 0,
        'PacketType': 'update_frontend',
        'Body': {
            'command': 'input selection player-1 msg [A], [A], 1 false true',
            'input_response': {
                'orderedSelections': ['none'],
            },
        },
    }

    response, status = server._process_protocol_packet(payload, client_slot='p1')

    assert status == 200
    assert response.get('ok') is True
    assert len(fake_bridge.calls) >= 1
    assert fake_bridge.calls[0][0] == 'input_result'


def test_frontend_event_non_winner_still_ignored_during_init(monkeypatch) -> None:
    fake_bridge = _FakeBridge()
    _stub_server_for_packet_test(monkeypatch, fake_bridge, stage='init')

    payload = {
        'ACK': 0,
        'PacketType': 'frontend_event',
        'Body': {
            'event_type': 'card_moved',
            'response_data': {'card_id': 'CARD-1'},
            'context': {},
        },
    }

    response, status = server._process_protocol_packet(payload, client_slot='p1')

    assert status == 200
    assert response.get('ok') is True
    assert fake_bridge.calls == []


def test_frontend_event_rejected_when_waiting_for_other_client_response(monkeypatch) -> None:
    fake_bridge = _FakeBridge()
    _stub_server_for_packet_test(monkeypatch, fake_bridge, stage='live')
    monkeypatch.setattr(server, 'entity_setup_payload', {'cards': [], 'energy': []})
    monkeypatch.setattr(
        server,
        'pending_command_acks',
        [
            PendingCommandAck(
                command_id=1,
                command='input coin player-2 force_flip 1',
                required_slots={'p2'},
            )
        ],
    )

    payload = {
        'ACK': 0,
        'PacketType': 'frontend_event',
        'Body': {
            'event_type': 'energy_moved',
            'response_data': {'energy_id': '1', 'to_zone_id': 'shared-energy'},
            'context': {},
        },
    }

    response, status = server._process_protocol_packet(payload, client_slot='p1')

    assert status == 200
    assert response.get('ok') is True
    assert response.get('rejected') is True
    assert fake_bridge.calls == []
    packets = response.get('packets', [])
    assert isinstance(packets, list)
    assert len(packets) == 1
    packet = packets[0]
    assert packet.get('PacketType') == 'environment'
    body = packet.get('Body')
    assert isinstance(body, dict)
    assert body.get('playerView') == 'p1'


def test_frontend_event_allowed_for_required_slot_when_pending(monkeypatch) -> None:
    fake_bridge = _FakeBridge()
    _stub_server_for_packet_test(monkeypatch, fake_bridge, stage='live')
    monkeypatch.setattr(
        server,
        'pending_command_acks',
        [
            PendingCommandAck(
                command_id=1,
                command='input coin player-1 force_flip 1',
                required_slots={'p1'},
            )
        ],
    )

    payload = {
        'ACK': 0,
        'PacketType': 'frontend_event',
        'Body': {
            'event_type': 'card_moved',
            'response_data': {'card_id': 'CARD-1'},
            'context': {},
        },
    }

    response, status = server._process_protocol_packet(payload, client_slot='p1')

    assert status == 200
    assert response.get('ok') is True
    assert response.get('rejected') is not True
    assert len(fake_bridge.calls) == 1
    assert fake_bridge.calls[0][0] == 'card_moved'


def test_frontend_event_rejected_for_acked_slot_while_other_slot_still_pending(monkeypatch) -> None:
    fake_bridge = _FakeBridge()
    _stub_server_for_packet_test(monkeypatch, fake_bridge, stage='live')
    monkeypatch.setattr(server, 'entity_setup_payload', {'cards': [], 'energy': []})
    monkeypatch.setattr(
        server,
        'pending_command_acks',
        [
            PendingCommandAck(
                command_id=1,
                command='notify both resolve_notify -1',
                required_slots={'p1', 'p2'},
                acked_slots={'p1'},
            )
        ],
    )

    payload = {
        'ACK': 0,
        'PacketType': 'frontend_event',
        'Body': {
            'event_type': 'phase2_attack_button_clicked',
            'response_data': {},
            'context': {},
        },
    }

    response, status = server._process_protocol_packet(payload, client_slot='p1')

    assert status == 200
    assert response.get('ok') is True
    assert response.get('rejected') is True
    assert fake_bridge.calls == []


def test_validate_init_setup_submission_raises_when_bench_over_cap(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        'entity_setup_payload',
        {
            'cards': [
                {'id': 'card-a', 'ownerId': 'p1', 'holderId': 'p1-hand', 'cardType': 'character'},
                {'id': 'card-b', 'ownerId': 'p1', 'holderId': 'p1-hand', 'cardType': 'character'},
                {'id': 'card-c', 'ownerId': 'p1', 'holderId': 'p1-hand', 'cardType': 'character'},
                {'id': 'card-d', 'ownerId': 'p1', 'holderId': 'p1-hand', 'cardType': 'character'},
                {'id': 'card-e', 'ownerId': 'p1', 'holderId': 'p1-hand', 'cardType': 'character'},
            ],
        },
    )

    try:
        server._validate_init_setup_submission(
            'p1',
            {
                'active_card_id': 'card-a',
                'bench_card_ids': ['card-b', 'card-c', 'card-d', 'card-e'],
            },
        )
    except ValueError as exc:
        assert 'bench_card_ids cannot exceed' in str(exc)
    else:
        raise AssertionError('Expected ValueError for over-cap bench setup payload.')


def test_handle_bridge_runtime_error_enqueues_game_error_and_terminates(monkeypatch) -> None:
    recorded_commands: list[list[str]] = []
    recorded_finish_reasons: list[str] = []
    recorded_termination_reasons: list[str] = []

    monkeypatch.setattr(
        server,
        '_enqueue_bridge_commands',
        lambda commands, source_slot=None: recorded_commands.append(list(commands)),
    )
    monkeypatch.setattr(
        server,
        '_commands_ready_for_slot',
        lambda source_slot, is_response, session=None: [
            {
                'ACK': 1,
                'PacketType': 'command',
                'Body': {
                    'command': 'notify both Game_error -1',
                    'command_id': 1,
                },
            }
        ],
    )
    monkeypatch.setattr(server, '_mark_room_finished_once', lambda reason: recorded_finish_reasons.append(reason))
    monkeypatch.setattr(server, '_schedule_process_termination', lambda reason: recorded_termination_reasons.append(reason))

    response, status = server._handle_bridge_runtime_error(Exception('boom'), 'p1', None)

    assert status == 200
    assert response.get('ok') is True
    assert response.get('fatal_error') is True
    assert recorded_commands == [['notify both Game_error -1']]
    assert recorded_finish_reasons == ['game_runner_error']
    assert recorded_termination_reasons == ['game runner error']


def test_recover_reconnect_token_for_expected_slot_uses_active_session(monkeypatch) -> None:
    transport_state = MultiplayerTransportState()
    active_session = transport_state.assign_slot('sid-p2', requested_slot='p2', reconnect_token=None)
    assert active_session is not None

    monkeypatch.setattr(server, 'transport_state', transport_state)

    recovered = server._recover_reconnect_token_for_expected_slot('p2', None)

    assert recovered == active_session.reconnect_token
