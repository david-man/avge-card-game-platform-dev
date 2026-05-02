from __future__ import annotations

import sys
from typing import Any

import card_game.server.workers.room_worker as room_worker


def _noop_on_finished(_room_id: str, _reason: str) -> None:
    return


def test_room_worker_pipe_mode_does_not_set_server_bind_env(monkeypatch) -> None:
    popen_calls: list[dict[str, Any]] = []

    class _DummyPopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            popen_calls.append({'args': args, 'kwargs': kwargs})
            self.pid = 4242
            self.stdin = kwargs.get('stdin')
            self.stdout = kwargs.get('stdout')

        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            return

        def wait(self, timeout: float | None = None) -> int:
            _ = timeout
            return 0

        def kill(self) -> None:
            return

    monkeypatch.setattr(room_worker.subprocess, 'Popen', _DummyPopen)
    monkeypatch.setattr(room_worker.Thread, 'start', lambda self: None)

    worker = room_worker.RoomWorker(
        room_id='room-test',
        player_session_ids=('session-a', 'session-b'),
        host='127.0.0.1',
        port=5600,
        p1_username='alice',
        p2_username='bob',
        p1_selected_cards=None,
        p2_selected_cards=None,
        transport_mode='pipe',
        on_finished=_noop_on_finished,
    )

    worker.start()

    assert len(popen_calls) == 1
    args = popen_calls[0]['args']
    kwargs = popen_calls[0]['kwargs']
    assert isinstance(args, tuple)
    assert len(args) >= 1
    assert args[0] == [sys.executable, '-m', 'card_game.server.workers.room_pipe_runtime']

    env = kwargs.get('env')
    assert isinstance(env, dict)
    assert env.get('ROOM_TRANSPORT_MODE') == 'pipe'
    assert 'SERVER_HOST' not in env
    assert 'SERVER_PORT' not in env

    worker.stop('test_shutdown')


def test_room_worker_rejects_non_pipe_mode() -> None:
    try:
        room_worker.RoomWorker(
            room_id='room-test-port',
            player_session_ids=('session-a', 'session-b'),
            host='0.0.0.0',
            port=5799,
            p1_username='alice',
            p2_username='bob',
            p1_selected_cards=None,
            p2_selected_cards=None,
            transport_mode='port',  # type: ignore[arg-type]
            on_finished=_noop_on_finished,
        )
        assert False, 'Expected ValueError for non-pipe transport_mode.'
    except ValueError as exc:
        assert 'pipe transport_mode' in str(exc)
