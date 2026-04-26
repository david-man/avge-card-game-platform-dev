from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from card_game.avge_abstracts.AVGEEnvironment import GamePhase
from card_game.constants import (
    AtkPhaseData,
    CardSelectionQuery,
    CoinflipData,
    Data,
    D6Data,
    IntegerInputData,
    OrderingQuery,
    Phase2Data,
    PlayerID,
    Response,
    ResponseType,
    ActionTypes,
)
from card_game.internal_events import InputEvent
from card_game.server.game_runner import FrontendGameBridge


class _FakeCard:
    def __init__(self, unique_id: str):
        self.unique_id = unique_id


class _FakeListener:
    def __init__(self, name: str):
        self._name = name

    def package(self) -> str:
        return self._name


def _make_bridge_with_cards(*cards: _FakeCard) -> FrontendGameBridge:
    bridge = FrontendGameBridge.__new__(FrontendGameBridge)
    bridge.env = SimpleNamespace(
        cards={card.unique_id: card for card in cards},
        _engine=SimpleNamespace(event_running=None),
        player_turn=SimpleNamespace(unique_id=PlayerID.P1),
        game_phase=None,
    )
    bridge._force_environment_sync_pending = False
    bridge._last_emitted_input_query_signature = None
    bridge._last_emitted_phase_token = None
    bridge._pending_ordering_listener_by_token = None
    bridge._last_emitted_ordering_query_signature = None
    return bridge


def test_build_input_command_for_card_selection_query() -> None:
    card_a = _FakeCard('card-a')
    card_b = _FakeCard('card-b')
    bridge = _make_bridge_with_cards(card_a, card_b)

    event = SimpleNamespace(
        player_for=SimpleNamespace(unique_id=PlayerID.P1),
        input_keys=['k1', 'k2'],
    )
    query = CardSelectionQuery(
        'Pick cards now',
        [card_a],
        [card_a, card_b],
        False,
        True,
    )

    command = bridge._build_input_command(event, query)

    assert command == 'input selection player-1 Pick_cards_now [card-a,card-b], [card-a], 2 true false'


def test_parse_frontend_input_result_for_card_selection_query() -> None:
    card_a = _FakeCard('card-a')
    card_b = _FakeCard('card-b')
    bridge = _make_bridge_with_cards(card_a, card_b)

    event = SimpleNamespace(
        query_data=CardSelectionQuery('Pick cards now', [card_a, card_b], [card_a, card_b], True, False),
        input_keys=['k1', 'k2'],
    )

    parsed = bridge._parse_frontend_input_result(event, {'ordered_selections': ['card-a', 'none']})

    assert isinstance(parsed, dict)
    assert parsed.get('input_result') == [card_a, None]


def test_parse_frontend_input_result_accepts_camel_case_ordered_selections_for_none() -> None:
    card_a = _FakeCard('card-a')
    bridge = _make_bridge_with_cards(card_a)

    event = SimpleNamespace(
        query_data=CardSelectionQuery('Pick cards now', [card_a], [card_a], True, False),
        input_keys=['k1'],
    )

    parsed = bridge._parse_frontend_input_result(event, {'orderedSelections': ['none']})

    assert isinstance(parsed, dict)
    assert parsed.get('input_result') == [None]


def test_parse_frontend_input_result_accepts_single_string_ordered_selections() -> None:
    card_a = _FakeCard('card-a')
    bridge = _make_bridge_with_cards(card_a)

    event = SimpleNamespace(
        query_data=CardSelectionQuery('Pick cards now', [card_a], [card_a], True, False),
        input_keys=['k1'],
    )

    parsed = bridge._parse_frontend_input_result(event, {'orderedSelections': 'none'})

    assert isinstance(parsed, dict)
    assert parsed.get('input_result') == [None]


def test_build_input_command_for_integer_query() -> None:
    bridge = _make_bridge_with_cards()
    event = SimpleNamespace(
        player_for=SimpleNamespace(unique_id=PlayerID.P2),
        input_keys=['k1'],
    )

    command = bridge._build_input_command(event, IntegerInputData('Pick a number', 0, 10))

    assert command == 'input numerical-entry player-2 Pick_a_number'


def test_build_input_command_for_coin_and_d6_queries() -> None:
    bridge = _make_bridge_with_cards()
    event = SimpleNamespace(
        player_for=SimpleNamespace(unique_id=PlayerID.P1),
        input_keys=['k1'],
    )

    with patch('card_game.server.game_runner.randint', side_effect=[1, 6]):
        coin_command = bridge._build_input_command(event, CoinflipData('Flip now'))
        d6_command = bridge._build_input_command(event, D6Data('Roll now'))

    assert coin_command == 'input coin player-1 Flip_now 1'
    assert d6_command == 'input d6 player-1 Roll_now 6'


def test_requires_query_ordering_query_emits_and_parses_round_trip() -> None:
    bridge = _make_bridge_with_cards()
    listener_a = _FakeListener('alpha')
    listener_b = _FakeListener('beta')

    response = Response(ResponseType.REQUIRES_QUERY, OrderingQuery([listener_a, listener_b]))
    commands = bridge._commands_from_response(response)

    assert commands == [
        'input selection player-1 order_listeners [l0_alpha,l1_beta], [l0_alpha,l1_beta], 2 false false'
    ]

    assert isinstance(bridge._pending_ordering_listener_by_token, dict)
    token_order = list(bridge._pending_ordering_listener_by_token.keys())

    command_side_effects, parsed_args = bridge._apply_frontend_event(
        'input_result',
        {'ordered_selections': [token_order[1], token_order[0]]},
    )

    assert command_side_effects == []
    assert isinstance(parsed_args, dict)
    assert parsed_args.get('group_ordering') == [listener_b, listener_a]


def test_requires_query_ordering_query_accepts_camel_case_payload_key() -> None:
    bridge = _make_bridge_with_cards()
    listener_a = _FakeListener('alpha')
    listener_b = _FakeListener('beta')

    response = Response(ResponseType.REQUIRES_QUERY, OrderingQuery([listener_a, listener_b]))
    _ = bridge._commands_from_response(response)

    assert isinstance(bridge._pending_ordering_listener_by_token, dict)
    token_order = list(bridge._pending_ordering_listener_by_token.keys())

    command_side_effects, parsed_args = bridge._apply_frontend_event(
        'input_result',
        {'orderedSelections': [token_order[1], token_order[0]]},
    )

    assert command_side_effects == []
    assert isinstance(parsed_args, dict)
    assert parsed_args.get('group_ordering') == [listener_b, listener_a]


def test_requires_query_phase_payloads_map_to_phase_commands_without_unhandled_notify() -> None:
    bridge = _make_bridge_with_cards()

    bridge.env.game_phase = GamePhase.PHASE_2
    bridge._last_emitted_phase_token = 'phase2'
    phase2_commands = bridge._commands_from_response(
        Response(ResponseType.REQUIRES_QUERY, Phase2Data(PlayerID.P1))
    )
    assert phase2_commands == []

    bridge.env.game_phase = GamePhase.ATK_PHASE
    bridge._last_emitted_phase_token = 'phase2'
    atk_commands = bridge._commands_from_response(
        Response(ResponseType.REQUIRES_QUERY, AtkPhaseData(PlayerID.P2))
    )
    assert atk_commands == ['phase atk']


def test_requires_query_legacy_non_data_query_payload_emits_unhandled_notify() -> None:
    bridge = _make_bridge_with_cards()
    legacy_source = InputEvent(
        player_for=SimpleNamespace(unique_id=PlayerID.P1),
        input_keys=['k1'],
        input_validation=lambda _result: True,
        catalyst_action=ActionTypes.NONCHAR,
        caller=SimpleNamespace(),
        query_data={'legacy': 'payload'},  # type: ignore[arg-type]
    )
    bridge.env._engine.event_running = legacy_source

    commands = bridge._commands_from_response(Response(ResponseType.REQUIRES_QUERY, Data()))

    assert commands == ['notify both UNHANDLED_QUERY_DATA -1']
