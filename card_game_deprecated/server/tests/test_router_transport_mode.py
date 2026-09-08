from __future__ import annotations

from pathlib import Path

import card_game.server.router_server as router_server


def test_room_serialization_omits_endpoint_url(tmp_path: Path) -> None:
    router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))
    room = router_server.RoomRecord(
        room_id='room-test',
        player_session_ids=('session-a', 'session-b'),
        created_at=0.0,
        bind_host='127.0.0.1',
        port=9999,
        transport_mode='pipe',
    )

    serialized = router._serialize_room_locked(room)
    assert serialized.get('transport_mode') == 'pipe'
    assert 'endpoint_url' not in serialized


def test_queue_assignment_pipe_mode_launches_pipe_worker(tmp_path: Path) -> None:
    router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))

    captured_workers: list[dict[str, object]] = []

    class FakeRoomWorker:
        def __init__(
            self,
            room_id: str,
            player_session_ids: tuple[str, str],
            host: str,
            port: int,
            p1_username: str,
            p2_username: str,
            p1_selected_cards: list[str] | None,
            p2_selected_cards: list[str] | None,
            transport_mode: str,
            on_finished,
            on_event=None,
        ) -> None:
            captured_workers.append(
                {
                    'room_id': room_id,
                    'player_session_ids': player_session_ids,
                    'host': host,
                    'port': port,
                    'transport_mode': transport_mode,
                    'on_finished': on_finished,
                    'on_event': on_event,
                }
            )

        def start(self) -> None:
            return

        def stop(self, reason: str = 'stopped') -> None:
            return

        def snapshot(self):
            class _Snapshot:
                process_pid = None
                started_at = 0.0
                finished = False
                finish_reason = None
                log_path = '/tmp/fake-room.log'

            return _Snapshot()

    previous_worker_cls = router_server.RoomWorker
    router_server.RoomWorker = FakeRoomWorker  # type: ignore[assignment]

    try:
        session_a = router.login('alice', None)
        session_b = router.login('bob', None)

        first = router.enqueue(session_a.session_id)
        assert first.get('ok') is True

        second = router.enqueue(session_b.session_id)
        assert second.get('ok') is True
        assert second.get('status') == 'assigned'
    finally:
        router_server.RoomWorker = previous_worker_cls

    assert len(captured_workers) == 1
    worker_args = captured_workers[0]
    assert worker_args['transport_mode'] == 'pipe'
    assert callable(worker_args['on_event'])


def test_notify_room_session_takeover_pipe_mode_uses_worker_request(tmp_path: Path) -> None:
    router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))

    calls: list[dict[str, object]] = []

    class _FakeWorker:
        def request(self, method: str, params: dict[str, object], timeout_seconds: float = 2.0) -> dict[str, object]:
            calls.append({
                'method': method,
                'params': params,
                'timeout_seconds': timeout_seconds,
            })
            return {'ok': True}

        def snapshot(self):
            class _Snapshot:
                process_pid = None
                started_at = 0.0
                finished = False
                finish_reason = None
                log_path = '/tmp/fake-room.log'

            return _Snapshot()

    room = router_server.RoomRecord(
        room_id='room-x',
        player_session_ids=('session-a', 'session-b'),
        created_at=0.0,
        bind_host='127.0.0.1',
        port=9999,
        transport_mode='pipe',
        worker=_FakeWorker(),
    )

    router._notify_room_session_takeover(
        room,
        slot='p1',
        old_session_id='old-session',
        new_session_id='new-session',
    )

    assert len(calls) == 1
    call = calls[0]
    assert call['method'] == 'replace_room_session'
    params = call['params']
    assert isinstance(params, dict)
    payload = params.get('payload')
    assert isinstance(payload, dict)
    assert payload.get('old_session_id') == 'old-session'
    assert payload.get('new_session_id') == 'new-session'


def test_dispatch_pipe_command_for_session_no_active_room(tmp_path: Path) -> None:
    router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))

    session_a = router.login('alice', None)
    ok, body = router.dispatch_pipe_command_for_session(
        session_a.session_id,
        method='health',
        params={},
    )

    assert ok is False
    assert body.get('error_code') == 'no_active_room'


def test_protocol_proxy_register_client_pipe_mode(tmp_path: Path) -> None:
    previous_worker_cls = router_server.RoomWorker
    previous_router = router_server.router

    calls: list[dict[str, object]] = []

    class FakeRoomWorker:
        def __init__(
            self,
            room_id: str,
            player_session_ids: tuple[str, str],
            host: str,
            port: int,
            p1_username: str,
            p2_username: str,
            p1_selected_cards: list[str] | None,
            p2_selected_cards: list[str] | None,
            transport_mode: str,
            on_finished,
            on_event=None,
        ) -> None:
            self.transport_mode = transport_mode

        def start(self) -> None:
            return

        def stop(self, reason: str = 'stopped') -> None:
            return

        def request(self, method: str, params: dict[str, object], timeout_seconds: float = 2.0) -> dict[str, object]:
            calls.append({
                'method': method,
                'params': params,
                'timeout_seconds': timeout_seconds,
            })
            if method == 'protocol_http_packet':
                return {
                    'status': 200,
                    'body': {
                        'ok': True,
                        'packets': [],
                        'client_slot': 'p1',
                        'reconnect_token': 'token-1',
                    },
                }
            return {'ok': True}

        def snapshot(self):
            class _Snapshot:
                process_pid = None
                started_at = 0.0
                finished = False
                finish_reason = None
                log_path = '/tmp/fake-room.log'

            return _Snapshot()

    try:
        router_server.RoomWorker = FakeRoomWorker  # type: ignore[assignment]
        router_server.router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))

        client = router_server.app.test_client()

        login_a = client.post('/api/v1/auth/login', json={'username': 'alice'})
        login_b = client.post('/api/v1/auth/login', json={'username': 'bob'})
        assert login_a.status_code == 200
        assert login_b.status_code == 200

        body_a = login_a.get_json()
        body_b = login_b.get_json()
        assert isinstance(body_a, dict)
        assert isinstance(body_b, dict)
        session_a = body_a.get('session_id')
        session_b = body_b.get('session_id')
        assert isinstance(session_a, str)
        assert isinstance(session_b, str)

        join_a = client.post('/matchmaking/queue', json={'action': 'join', 'session_id': session_a})
        join_b = client.post('/matchmaking/queue', json={'action': 'join', 'session_id': session_b})
        assert join_a.status_code == 200
        assert join_b.status_code == 200

        protocol_response = client.post(
            '/protocol',
            json={
                'ACK': 0,
                'PacketType': 'register_client',
                'Body': {
                    'session_id': session_a,
                },
                'client_id': 'client-a',
            },
        )

        assert protocol_response.status_code == 200
        protocol_body = protocol_response.get_json()
        assert isinstance(protocol_body, dict)
        assert protocol_body.get('ok') is True
        assert router_server.router.game_session_for_client('client-a') == session_a
        assert len(calls) == 1
        assert calls[0]['method'] == 'protocol_http_packet'

        ready_response = client.post(
            '/protocol',
            json={
                'ACK': 1,
                'PacketType': 'ready',
                'Body': {},
                'client_id': 'client-a',
            },
        )

        assert ready_response.status_code == 200
        ready_body = ready_response.get_json()
        assert isinstance(ready_body, dict)
        assert ready_body.get('ok') is True
        assert len(calls) == 2
        assert calls[1]['method'] == 'protocol_http_packet'
        second_params = calls[1]['params']
        assert isinstance(second_params, dict)
        second_payload = second_params.get('payload')
        assert isinstance(second_payload, dict)
        assert second_payload.get('PacketType') == 'ready'
    finally:
        router_server.RoomWorker = previous_worker_cls
        router_server.router = previous_router
