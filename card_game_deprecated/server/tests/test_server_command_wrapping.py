from __future__ import annotations

from card_game.server import server
from card_game.server.protocol.command_codec import to_wire_command


def _stub_connected_command_queue(monkeypatch) -> None:
    monkeypatch.setattr(server, 'pending_command_acks', [])
    monkeypatch.setattr(server, 'next_command_id', 1)
    monkeypatch.setattr(server, 'winner_announced', False)
    monkeypatch.setattr(server, 'winner_main_menu_ack_slots', set())
    monkeypatch.setattr(server, '_emit_ready_commands_to_connected_clients', lambda: None)

    monkeypatch.setitem(server.transport_state.sid_by_slot, 'p1', 'sid-p1')
    monkeypatch.setitem(server.transport_state.sid_by_slot, 'p2', 'sid-p2')


def test_enqueue_reveal_single_target_is_not_wrapped(monkeypatch) -> None:
    _stub_connected_command_queue(monkeypatch)

    command = 'reveal player-1 [card-1] revealed_card 5'
    server._enqueue_bridge_commands([command], source_slot='p1')

    queued = [pending.command for pending in server.pending_command_acks]
    assert queued == [to_wire_command(command)]


def test_enqueue_single_target_input_is_not_wrapped(monkeypatch) -> None:
    _stub_connected_command_queue(monkeypatch)

    command = 'input coin player-1 force_flip 1'
    server._enqueue_bridge_commands([command], source_slot='p1')

    queued = [pending.command for pending in server.pending_command_acks]
    assert queued == [to_wire_command(command)]


def test_enqueue_single_target_query_does_not_wrap_when_other_client_disconnected(monkeypatch) -> None:
    _stub_connected_command_queue(monkeypatch)
    monkeypatch.setitem(server.transport_state.sid_by_slot, 'p2', None)

    command = 'input coin player-1 force_flip 1'
    server._enqueue_bridge_commands([command], source_slot='p1')

    queued = [pending.command for pending in server.pending_command_acks]
    assert queued == [to_wire_command(command)]


def test_enqueue_notify_both_is_not_wrapped(monkeypatch) -> None:
    _stub_connected_command_queue(monkeypatch)

    command = 'notify both everyone_ack_this -1'
    server._enqueue_bridge_commands([command], source_slot='p1')

    queued = [pending.command for pending in server.pending_command_acks]
    assert queued == [to_wire_command(command)]


def test_enqueue_command_object_preserves_response_payload(monkeypatch) -> None:
    _stub_connected_command_queue(monkeypatch)

    payload = {
        'animation': {
            'target': 'both',
            'keyframes': [
                {
                    'key': 'sfx-key',
                    'kind': 'sound',
                }
            ],
        }
    }
    command = {
        'command': 'notify both everyone_ack_this -1',
        'response_payload': payload,
    }

    server._enqueue_bridge_commands([command], source_slot='p1')

    assert len(server.pending_command_acks) == 1
    pending = server.pending_command_acks[0]
    assert pending.command == to_wire_command('notify both everyone_ack_this -1')
    assert pending.response_payload == payload
