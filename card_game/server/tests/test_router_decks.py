from __future__ import annotations

from pathlib import Path

import card_game.server.game_runner as game_runner
import card_game.server.router_server as router_server


def _login(client, username: str) -> str:
    response = client.post('/api/v1/auth/login', json={'username': username})
    assert response.status_code == 200
    body = response.get_json()
    assert isinstance(body, dict)
    session_id = body.get('session_id')
    assert isinstance(session_id, str)
    return session_id


def _valid_deck_cards_alpha() -> list[str]:
    return [
        'KeiWatanabe',
        'MatthewWang',
        'DavidMan',
        'RobertoGonzales',
        'FionaLi',
        'JennieWang',
        'LukeXu',
        'DanielYang',
        'RyanLi',
        'SophiaSWang',
        'AliceWang',
        'EmilyWang',
        'AnnaBrown',
        'FelixChen',
        'Angel',
        'Emma',
        'MainHall',
        'FriedmanHall',
        'ConcertTicket',
        'ConcertTicket',
    ]


def _valid_deck_cards_beta() -> list[str]:
    return [
        'MeyaGao',
        'BenCherekIII',
        'ChristmasKim',
        'GraceZhao',
        'BokaiBi',
        'CavinXue',
        'PascalKim',
        'CathyRong',
        'HenryWang',
        'KatieXiang',
        'GabrielChen',
        'JuliaCeccarelli',
        'BettySolomon',
        'LucaChen',
        'Richard',
        'Victoria',
        'SteinertPracticeRoom',
        'RileyHall',
        'AVGETShirt',
        'AVGETShirt',
    ]


def _valid_non_character_deck_cards() -> list[str]:
    cards: list[str] = []
    for symbol_name, symbol in sorted(router_server.__dict__.items()):
        if not isinstance(symbol, type):
            continue
        if not issubclass(symbol, router_server.AVGECard):
            continue
        if not str(getattr(symbol, '__module__', '')).startswith('card_game.catalog'):
            continue
        if issubclass(symbol, router_server.AVGECharacterCard):
            continue

        max_copies = (
            router_server.DECK_MAX_ITEM_OR_TOOL_COPIES
            if issubclass(symbol, router_server.AVGEItemCard) or issubclass(symbol, router_server.AVGEToolCard)
            else router_server.DECK_MAX_OTHER_COPIES
        )

        remaining = router_server.DECK_REQUIRED_CARD_COUNT - len(cards)
        copies_to_add = min(max_copies, remaining)
        cards.extend([symbol_name] * copies_to_add)
        if len(cards) == router_server.DECK_REQUIRED_CARD_COUNT:
            break

    assert len(cards) == router_server.DECK_REQUIRED_CARD_COUNT
    return cards


def test_deck_crud_and_selection_roundtrip(tmp_path: Path) -> None:
    router_server.router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))
    client = router_server.app.test_client()

    session_id = _login(client, 'alice')

    create_response = client.post(
        '/api/v1/decks',
        json={
            'session_id': session_id,
            'name': 'Alpha',
            'cards': _valid_deck_cards_alpha(),
        },
    )
    assert create_response.status_code == 201
    create_body = create_response.get_json()
    assert isinstance(create_body, dict)
    deck = create_body.get('deck')
    assert isinstance(deck, dict)
    deck_id = deck['deck_id']

    list_response = client.get('/api/v1/decks', query_string={'session_id': session_id})
    assert list_response.status_code == 200
    list_body = list_response.get_json()
    assert isinstance(list_body, dict)
    assert isinstance(list_body.get('decks'), list)
    assert len(list_body['decks']) == 1

    update_response = client.put(
        f'/api/v1/decks/{deck_id}',
        json={
            'session_id': session_id,
            'name': 'Alpha+',
            'cards': _valid_deck_cards_beta(),
        },
    )
    assert update_response.status_code == 200

    select_response = client.post(
        f'/api/v1/decks/{deck_id}/select',
        json={'session_id': session_id},
    )
    assert select_response.status_code == 200
    select_body = select_response.get_json()
    assert isinstance(select_body, dict)
    assert select_body.get('selected_deck_id') == deck_id

    delete_response = client.delete(
        f'/api/v1/decks/{deck_id}',
        json={'session_id': session_id},
    )
    assert delete_response.status_code == 200

    list_after_delete = client.get('/api/v1/decks', query_string={'session_id': session_id})
    assert list_after_delete.status_code == 200
    list_after_delete_body = list_after_delete.get_json()
    assert isinstance(list_after_delete_body, dict)
    assert list_after_delete_body.get('decks') == []


def test_deck_ownership_enforced(tmp_path: Path) -> None:
    router_server.router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))
    client = router_server.app.test_client()

    alice_session = _login(client, 'alice')
    bob_session = _login(client, 'bob')

    create_response = client.post(
        '/api/v1/decks',
        json={
            'session_id': alice_session,
            'name': 'Alice Deck',
            'cards': _valid_deck_cards_alpha(),
        },
    )
    assert create_response.status_code == 201
    create_body = create_response.get_json()
    assert isinstance(create_body, dict)
    deck = create_body.get('deck')
    assert isinstance(deck, dict)
    deck_id = deck['deck_id']

    # Bob cannot select Alice's deck.
    select_response = client.post(
        f'/api/v1/decks/{deck_id}/select',
        json={'session_id': bob_session},
    )
    assert select_response.status_code == 404

    # Bob cannot update Alice's deck.
    update_response = client.put(
        f'/api/v1/decks/{deck_id}',
        json={
            'session_id': bob_session,
            'name': 'Hacked',
            'cards': ['x'],
        },
    )
    assert update_response.status_code == 404

    # Bob cannot delete Alice's deck.
    delete_response = client.delete(
        f'/api/v1/decks/{deck_id}',
        json={'session_id': bob_session},
    )
    assert delete_response.status_code == 404


def test_decks_get_accepts_query_session_without_cookie(tmp_path: Path) -> None:
    router_server.router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))
    login_client = router_server.app.test_client()

    session_id = _login(login_client, 'alice')

    create_response = login_client.post(
        '/api/v1/decks',
        json={
            'session_id': session_id,
            'name': 'Alpha',
            'cards': _valid_deck_cards_alpha(),
        },
    )
    assert create_response.status_code == 201

    # New client intentionally has no auth cookie. Query session_id should be enough.
    query_only_client = router_server.app.test_client()
    list_response = query_only_client.get('/api/v1/decks', query_string={'session_id': session_id})
    assert list_response.status_code == 200
    body = list_response.get_json()
    assert isinstance(body, dict)
    decks = body.get('decks')
    assert isinstance(decks, list)
    assert len(decks) == 1


def test_room_assignment_passes_selected_deck_cards_to_worker(tmp_path: Path) -> None:
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
            on_finished,
        ) -> None:
            captured_workers.append(
                {
                    'room_id': room_id,
                    'player_session_ids': player_session_ids,
                    'host': host,
                    'port': port,
                    'p1_username': p1_username,
                    'p2_username': p2_username,
                    'p1_selected_cards': p1_selected_cards,
                    'p2_selected_cards': p2_selected_cards,
                    'on_finished': on_finished,
                }
            )

        def start(self) -> None:
            return

        def stop(self, reason: str = 'stopped') -> None:
            return

    previous_worker_cls = router_server.RoomWorker
    try:
        router_server.RoomWorker = FakeRoomWorker  # type: ignore[assignment]
        router_server.router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))
        client = router_server.app.test_client()

        session_a = _login(client, 'alice')
        session_b = _login(client, 'bob')

        create_a = client.post(
            '/api/v1/decks',
            json={
                'session_id': session_a,
                'name': 'Alpha',
                'cards': _valid_deck_cards_alpha(),
            },
        )
        assert create_a.status_code == 201
        deck_a = create_a.get_json()
        assert isinstance(deck_a, dict)
        deck_a_id = deck_a['deck']['deck_id']

        create_b = client.post(
            '/api/v1/decks',
            json={
                'session_id': session_b,
                'name': 'Beta',
                'cards': _valid_deck_cards_beta(),
            },
        )
        assert create_b.status_code == 201
        deck_b = create_b.get_json()
        assert isinstance(deck_b, dict)
        deck_b_id = deck_b['deck']['deck_id']

        select_a = client.post(f'/api/v1/decks/{deck_a_id}/select', json={'session_id': session_a})
        assert select_a.status_code == 200

        select_b = client.post(f'/api/v1/decks/{deck_b_id}/select', json={'session_id': session_b})
        assert select_b.status_code == 200

        join_a = client.post('/matchmaking/queue', json={'action': 'join', 'session_id': session_a})
        assert join_a.status_code == 200

        join_b = client.post('/matchmaking/queue', json={'action': 'join', 'session_id': session_b})
        assert join_b.status_code == 200

        assert len(captured_workers) == 1
        worker_args = captured_workers[0]
        observed = {
            tuple(worker_args['p1_selected_cards'] or []),
            tuple(worker_args['p2_selected_cards'] or []),
        }
        expected = {
            tuple(_valid_deck_cards_alpha()),
            tuple(_valid_deck_cards_beta()),
        }
        assert observed == expected
    finally:
        router_server.RoomWorker = previous_worker_cls


def test_game_runner_setup_payload_uses_usernames() -> None:
    env = game_runner.build_environment_from_default_setups()
    payload = game_runner.environment_to_setup_payload(env)

    players = payload.get('players')
    assert isinstance(players, dict)
    p1 = players.get('p1')
    p2 = players.get('p2')
    assert isinstance(p1, dict)
    assert isinstance(p2, dict)
    assert p1.get('username') == game_runner.p1_username
    assert p2.get('username') == game_runner.p2_username


def test_enqueue_rejects_invalid_selected_deck(tmp_path: Path) -> None:
    router_server.router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))
    client = router_server.app.test_client()

    session_id = _login(client, 'alice')

    create_response = client.post(
        '/api/v1/decks',
        json={
            'session_id': session_id,
            'name': 'Alpha',
            'cards': _valid_deck_cards_alpha(),
        },
    )
    assert create_response.status_code == 201
    create_body = create_response.get_json()
    assert isinstance(create_body, dict)
    deck = create_body.get('deck')
    assert isinstance(deck, dict)
    deck_id = deck['deck_id']

    select_response = client.post(
        f'/api/v1/decks/{deck_id}/select',
        json={'session_id': session_id},
    )
    assert select_response.status_code == 200

    session = router_server.router.session(session_id)
    assert session is not None

    # Simulate a stale/corrupted selected deck that bypassed API validation.
    storage_update_ok = router_server.router._storage.update_deck(
        deck_id,
        session.user_id,
        'Alpha',
        '{"cards":["KeiWatanabe"]}'
    )
    assert storage_update_ok is True

    enqueue_response = client.post(
        '/matchmaking/queue',
        json={'action': 'join', 'session_id': session_id},
    )
    assert enqueue_response.status_code == 400
    enqueue_body = enqueue_response.get_json()
    assert isinstance(enqueue_body, dict)
    assert enqueue_body.get('ok') is False
    assert isinstance(enqueue_body.get('error'), str)
    assert 'invalid selected deck' in str(enqueue_body.get('error')).lower()

    status_response = client.get('/matchmaking/status', query_string={'session_id': session_id})
    assert status_response.status_code == 200
    status_body = status_response.get_json()
    assert isinstance(status_body, dict)
    assert status_body.get('status') == 'idle'


def test_deck_create_allows_incomplete_but_rejects_invalid_copies(tmp_path: Path) -> None:
    router_server.router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))
    client = router_server.app.test_client()

    session_id = _login(client, 'alice')

    incomplete_but_valid = client.post(
        '/api/v1/decks',
        json={
            'session_id': session_id,
            'name': 'Incomplete Draft',
            'cards': _valid_deck_cards_alpha()[:10],
        },
    )
    assert incomplete_but_valid.status_code == 201

    item_over_limit = client.post(
        '/api/v1/decks',
        json={
            'session_id': session_id,
            'name': 'Too Many Item Copies',
            'cards': ['ConcertTicket', 'ConcertTicket', 'ConcertTicket'] + _valid_deck_cards_alpha()[3:],
        },
    )
    assert item_over_limit.status_code == 400

    character_over_limit = client.post(
        '/api/v1/decks',
        json={
            'session_id': session_id,
            'name': 'Too Many Character Copies',
            'cards': ['KeiWatanabe', 'KeiWatanabe'] + _valid_deck_cards_alpha()[2:],
        },
    )
    assert character_over_limit.status_code == 400


def test_enqueue_rejects_incomplete_active_deck(tmp_path: Path) -> None:
    router_server.router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))
    client = router_server.app.test_client()

    session_id = _login(client, 'alice')

    create_response = client.post(
        '/api/v1/decks',
        json={
            'session_id': session_id,
            'name': 'Draft',
            'cards': _valid_deck_cards_alpha()[:10],
        },
    )
    assert create_response.status_code == 201
    create_body = create_response.get_json()
    assert isinstance(create_body, dict)
    deck = create_body.get('deck')
    assert isinstance(deck, dict)
    deck_id = deck['deck_id']

    select_response = client.post(
        f'/api/v1/decks/{deck_id}/select',
        json={'session_id': session_id},
    )
    assert select_response.status_code == 200

    enqueue_response = client.post(
        '/matchmaking/queue',
        json={'action': 'join', 'session_id': session_id},
    )
    assert enqueue_response.status_code == 400
    enqueue_body = enqueue_response.get_json()
    assert isinstance(enqueue_body, dict)
    assert enqueue_body.get('ok') is False
    assert isinstance(enqueue_body.get('error'), str)
    assert 'invalid selected deck' in str(enqueue_body.get('error')).lower()
    assert 'exactly 20 cards' in str(enqueue_body.get('error')).lower()


def test_enqueue_rejects_active_deck_without_character_card(tmp_path: Path) -> None:
    router_server.router = router_server.MatchmakingRouter(db_path=str(tmp_path / 'router.sqlite3'))
    client = router_server.app.test_client()

    session_id = _login(client, 'alice')

    create_response = client.post(
        '/api/v1/decks',
        json={
            'session_id': session_id,
            'name': 'No Character Deck',
            'cards': _valid_non_character_deck_cards(),
        },
    )
    assert create_response.status_code == 201
    create_body = create_response.get_json()
    assert isinstance(create_body, dict)
    deck = create_body.get('deck')
    assert isinstance(deck, dict)
    deck_id = deck['deck_id']

    select_response = client.post(
        f'/api/v1/decks/{deck_id}/select',
        json={'session_id': session_id},
    )
    assert select_response.status_code == 200

    enqueue_response = client.post(
        '/matchmaking/queue',
        json={'action': 'join', 'session_id': session_id},
    )
    assert enqueue_response.status_code == 400
    enqueue_body = enqueue_response.get_json()
    assert isinstance(enqueue_body, dict)
    assert enqueue_body.get('ok') is False
    assert isinstance(enqueue_body.get('error'), str)
    assert 'invalid selected deck' in str(enqueue_body.get('error')).lower()
    assert 'at least 1 character' in str(enqueue_body.get('error')).lower()
