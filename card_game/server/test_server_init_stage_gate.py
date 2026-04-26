from __future__ import annotations

from typing import Any

from card_game.server import server
from card_game.server.server_models import PendingCommandAck


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
