from __future__ import annotations

from pathlib import Path

import card_game.server.router_server as router_server


def test_auth_login_session_logout_flow(tmp_path: Path) -> None:
    router_server.router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))
    client = router_server.app.test_client()

    login_response = client.post('/api/v1/auth/login', json={'username': 'alice'})
    assert login_response.status_code == 200
    login_body = login_response.get_json()
    assert isinstance(login_body, dict)
    assert login_body.get('ok') is True
    assert login_body.get('session_id')

    session_response = client.get('/api/v1/auth/session', query_string={'session_id': login_body['session_id']})
    assert session_response.status_code == 200
    session_body = session_response.get_json()
    assert isinstance(session_body, dict)
    assert session_body.get('ok') is True
    assert session_body.get('username') == 'alice'

    logout_response = client.post('/api/v1/auth/logout', json={'session_id': login_body['session_id']})
    assert logout_response.status_code == 200

    session_after_logout = client.get('/api/v1/auth/session', query_string={'session_id': login_body['session_id']})
    assert session_after_logout.status_code == 401


def test_matchmaking_requires_authenticated_session(tmp_path: Path) -> None:
    router_server.router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))
    client = router_server.app.test_client()

    response = client.post('/matchmaking/queue', json={'action': 'join', 'session_id': 'missing'})
    assert response.status_code == 401
    body = response.get_json()
    assert isinstance(body, dict)
    assert body.get('ok') is False
    assert body.get('error_code') == 'unknown_session'


def test_matchmaking_with_authenticated_session(tmp_path: Path) -> None:
    router_server.router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))
    client = router_server.app.test_client()

    login_response = client.post('/api/v1/auth/login', json={'username': 'bob'})
    login_body = login_response.get_json()
    assert isinstance(login_body, dict)
    session_id = login_body['session_id']

    queue_response = client.post('/matchmaking/queue', json={'action': 'join', 'session_id': session_id})
    assert queue_response.status_code == 200
    queue_body = queue_response.get_json()
    assert isinstance(queue_body, dict)
    assert queue_body.get('ok') is True
    assert queue_body.get('status') in {'waiting', 'assigned'}


def test_login_supersedes_previous_session_for_same_username(tmp_path: Path) -> None:
    router_server.router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))
    client = router_server.app.test_client()

    first_login = client.post('/api/v1/auth/login', json={'username': 'alice'})
    assert first_login.status_code == 200
    first_body = first_login.get_json()
    assert isinstance(first_body, dict)
    first_session_id = first_body.get('session_id')
    assert isinstance(first_session_id, str) and first_session_id

    second_login = client.post('/api/v1/auth/login', json={'username': 'alice'})
    assert second_login.status_code == 200
    second_body = second_login.get_json()
    assert isinstance(second_body, dict)
    second_session_id = second_body.get('session_id')
    assert isinstance(second_session_id, str) and second_session_id
    assert second_session_id != first_session_id

    old_session_lookup = client.get('/api/v1/auth/session', query_string={'session_id': first_session_id})
    assert old_session_lookup.status_code == 401
    old_body = old_session_lookup.get_json()
    assert isinstance(old_body, dict)
    assert old_body.get('error_code') == 'session_superseded'

    new_session_lookup = client.get('/api/v1/auth/session', query_string={'session_id': second_session_id})
    assert new_session_lookup.status_code == 200
    new_body = new_session_lookup.get_json()
    assert isinstance(new_body, dict)
    assert new_body.get('ok') is True
    assert new_body.get('username') == 'alice'
