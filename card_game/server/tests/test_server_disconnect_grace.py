from __future__ import annotations

from threading import Condition
from threading import RLock
from typing import Callable

from card_game.server import server
from card_game.server.models.server_models import MultiplayerTransportState


class _FakeTimer:
    created: list['_FakeTimer'] = []

    def __init__(self, interval: float, callback: Callable[[], None]) -> None:
        self.interval = interval
        self.callback = callback
        self.cancelled = False
        self.started = False
        self.daemon = False
        _FakeTimer.created.append(self)

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True


class _FakeSocketIO:
    def __init__(self) -> None:
        self.emits: list[tuple[str, dict, str | None]] = []

    def emit(self, event: str, payload: dict, to: str | None = None) -> None:
        self.emits.append((event, payload, to))


def _prepare_disconnect_test_harness(monkeypatch):
    lock = RLock()
    state = MultiplayerTransportState(disconnect_grace_seconds=server.DISCONNECT_GRACE_SECONDS)

    monkeypatch.setattr(server, 'transport_lock', lock)
    monkeypatch.setattr(server, 'registration_condition', Condition(lock))
    monkeypatch.setattr(server, 'transport_state', state)
    monkeypatch.setattr(server, 'disconnect_forfeit_timer_by_slot', {'p1': None, 'p2': None})
    monkeypatch.setattr(server, 'first_player_join_seen', True)
    monkeypatch.setattr(server, 'termination_requested', False)
    monkeypatch.setattr(server, 'Timer', _FakeTimer)
    monkeypatch.setattr(server, 'p1_username', 'P1')
    monkeypatch.setattr(server, 'p2_username', 'P2')
    monkeypatch.setattr(server, 'pending_command_acks', [])
    monkeypatch.setattr(server, 'winner_announced', False)
    monkeypatch.setattr(server, 'winner_main_menu_ack_slots', set())
    monkeypatch.setattr(server, 'log_protocol_event', lambda *args, **kwargs: None)

    _FakeTimer.created.clear()
    return lock, state


def test_disconnect_forfeit_triggers_after_grace_timeout(monkeypatch) -> None:
    lock, state = _prepare_disconnect_test_harness(monkeypatch)
    recorded_commands: list[list[str]] = []
    monkeypatch.setattr(server, '_enqueue_bridge_commands', lambda commands, source_slot=None: recorded_commands.append(list(commands)))

    with lock:
        session_p1 = state.assign_slot('sid-p1', requested_slot='p1', reconnect_token=None)
        session_p2 = state.assign_slot('sid-p2', requested_slot='p2', reconnect_token=None)
        assert session_p1 is not None
        assert session_p2 is not None

        state.release_sid('sid-p2')
        server._schedule_disconnect_forfeit_timer_locked('p2')

    timer = _FakeTimer.created[-1]
    assert timer.interval == server.DISCONNECT_GRACE_SECONDS
    assert timer.started is True

    timer.callback()

    assert len(recorded_commands) == 1
    assert recorded_commands[0][0].startswith('winner player-1 ')


def test_disconnect_forfeit_is_cancelled_when_player_reconnects(monkeypatch) -> None:
    lock, state = _prepare_disconnect_test_harness(monkeypatch)
    recorded_commands: list[list[str]] = []
    monkeypatch.setattr(server, '_enqueue_bridge_commands', lambda commands, source_slot=None: recorded_commands.append(list(commands)))

    with lock:
        session_p1 = state.assign_slot('sid-p1', requested_slot='p1', reconnect_token=None)
        session_p2 = state.assign_slot('sid-p2', requested_slot='p2', reconnect_token=None)
        assert session_p1 is not None
        assert session_p2 is not None

        reconnect_token = session_p2.reconnect_token
        state.release_sid('sid-p2')
        server._schedule_disconnect_forfeit_timer_locked('p2')

        reconnected = state.assign_slot(
            'sid-p2-returned',
            requested_slot='p2',
            reconnect_token=reconnect_token,
        )
        assert reconnected is not None

    timer = _FakeTimer.created[-1]
    assert timer.interval == server.DISCONNECT_GRACE_SECONDS

    timer.callback()

    assert recorded_commands == []


def test_client_unloading_notifies_peer_immediately(monkeypatch) -> None:
    lock, state = _prepare_disconnect_test_harness(monkeypatch)
    fake_socketio = _FakeSocketIO()
    monkeypatch.setattr(server, 'socketio', fake_socketio)

    with lock:
        session_p1 = state.assign_slot('sid-p1', requested_slot='p1', reconnect_token=None)
        session_p2 = state.assign_slot('sid-p2', requested_slot='p2', reconnect_token=None)
        assert session_p1 is not None
        assert session_p2 is not None

    server._handle_transport_sid_disconnect('sid-p1', event_name='client_unloading')

    assert state.sid_by_slot['p1'] is None
    assert state.sid_by_slot['p2'] == 'sid-p2'
    assert len(_FakeTimer.created) >= 1
    assert _FakeTimer.created[-1].interval == server.DISCONNECT_GRACE_SECONDS
    assert ('opponent_disconnected', {'slot': 'p1', 'grace_seconds': server.DISCONNECT_GRACE_SECONDS}, 'sid-p2') in fake_socketio.emits
