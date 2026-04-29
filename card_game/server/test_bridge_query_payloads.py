from __future__ import annotations

from threading import RLock
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
    Notify,
    OrderingQuery,
    StrSelectionQuery,
    Pile,
    Phase2Data,
    PlayerID,
    Response,
    ResponseType,
    ActionTypes,
)
from card_game.internal_events import InputEvent, TransferCard
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
    bridge._lock = RLock()
    bridge.env = SimpleNamespace(
        cards={card.unique_id: card for card in cards},
        _engine=SimpleNamespace(event_running=None),
        player_turn=SimpleNamespace(unique_id=PlayerID.P1),
        game_phase=None,
        stadium_cardholder=object(),
    )
    bridge._force_environment_sync_pending = False
    bridge._pending_input_query_event = None
    bridge._pending_input_query_command = None
    bridge._last_emitted_phase_token = None
    bridge._outbound_command_queue = []
    bridge._outbound_command_payload_queue = []
    bridge._awaiting_frontend_ack = False
    bridge._awaiting_frontend_ack_command = None
    bridge._pending_frontend_events = []
    bridge._pending_ordering_listener_by_token = None
    bridge._last_emitted_ordering_query_signature = None
    bridge._pending_packet_commands = []
    bridge._pending_packet_command_payloads = []
    bridge._pending_engine_input_args = None
    bridge._max_forward_steps = 5000
    return bridge


def _make_drain_bridge_with_forward_responses(*responses: Response) -> FrontendGameBridge:
    bridge = _make_bridge_with_cards(_FakeCard('card-a'))
    pending = list(responses)

    def _forward(_input_args=None):
        if pending:
            return pending.pop(0)
        return Response(ResponseType.NO_MORE_EVENTS, Data())

    bridge.env.forward = _forward
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


def test_parse_frontend_input_result_pads_missing_allows_none_card_selections() -> None:
    card_a = _FakeCard('card-a')
    card_b = _FakeCard('card-b')
    bridge = _make_bridge_with_cards(card_a, card_b)

    event = SimpleNamespace(
        query_data=CardSelectionQuery('Pick cards now', [card_a, card_b], [card_a, card_b], True, False),
        input_keys=['k1', 'k2'],
    )

    parsed = bridge._parse_frontend_input_result(event, {'orderedSelections': ['card-a']})

    assert isinstance(parsed, dict)
    assert parsed.get('input_result') == [card_a, None]


def test_parse_frontend_input_result_pads_missing_allows_none_string_selections() -> None:
    bridge = _make_bridge_with_cards()

    event = SimpleNamespace(
        query_data=StrSelectionQuery('Pick strings now', ['A', 'B'], ['A', 'B'], True, False),
        input_keys=['k1', 'k2'],
    )

    parsed = bridge._parse_frontend_input_result(event, {'ordered_selections': ['A']})

    assert isinstance(parsed, dict)
    assert parsed.get('input_result') == ['A', None]


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


def test_build_input_command_for_multi_coin_and_d6_queries() -> None:
    bridge = _make_bridge_with_cards()
    coin_event = SimpleNamespace(
        player_for=SimpleNamespace(unique_id=PlayerID.P1),
        input_keys=['k1', 'k2', 'k3'],
    )
    d6_event = SimpleNamespace(
        player_for=SimpleNamespace(unique_id=PlayerID.P1),
        input_keys=['k1', 'k2'],
    )

    with patch('card_game.server.game_runner.randint', side_effect=[1, 0, 1, 4, 2]):
        coin_command = bridge._build_input_command(coin_event, CoinflipData('Flip now'))
        d6_command = bridge._build_input_command(d6_event, D6Data('Roll now'))

    assert coin_command == 'input coin player-1 Flip_now [1,0,1]'
    assert d6_command == 'input d6 player-1 Roll_now [4,2]'


def test_commands_from_response_transfer_same_deck_emits_single_card_shuffle_animation() -> None:
    card_a = _FakeCard('card-a')
    bridge = _make_bridge_with_cards(card_a)
    bridge.env.stadium_cardholder = object()

    owner = SimpleNamespace(unique_id=PlayerID.P1)
    deck_holder = SimpleNamespace(player=owner, pile_type=Pile.DECK)
    transfer = TransferCard(
        card=card_a,
        pile_from=deck_holder,
        pile_to=deck_holder,
        catalyst_action=ActionTypes.NONCHAR,
        caller=SimpleNamespace(),
        core_notif=None,
    )

    response = Response(ResponseType.CORE, Data())
    response.source = transfer

    commands = bridge._commands_from_response(response)

    assert commands == ['shuffle-single-card card-a p1-deck']


def test_parse_frontend_input_result_for_multi_coinflip_values() -> None:
    bridge = _make_bridge_with_cards()
    event = SimpleNamespace(
        query_data=CoinflipData('Flip now'),
        input_keys=['k1', 'k2', 'k3'],
    )

    parsed = bridge._parse_frontend_input_result(event, {'result_values': [1, 0, 'heads']})

    assert isinstance(parsed, dict)
    assert parsed.get('input_result') == [1, 0, 1]


def test_parse_frontend_input_result_for_multi_d6_values() -> None:
    bridge = _make_bridge_with_cards()
    event = SimpleNamespace(
        query_data=D6Data('Roll now'),
        input_keys=['k1', 'k2'],
    )

    parsed = bridge._parse_frontend_input_result(event, {'resultValues': '[6,2]'})

    assert isinstance(parsed, dict)
    assert parsed.get('input_result') == [6, 2]


def test_parse_frontend_input_result_expands_single_coinflip_with_randomized_extra_values() -> None:
    bridge = _make_bridge_with_cards()
    event = SimpleNamespace(
        query_data=CoinflipData('Flip now'),
        input_keys=['k1', 'k2'],
    )

    with patch('card_game.server.game_runner.randint', return_value=0):
        parsed = bridge._parse_frontend_input_result(event, {'result_value': 1})

    assert isinstance(parsed, dict)
    assert parsed.get('input_result') == [1, 0]


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


def test_drain_engine_keeps_requires_query_command_when_flushing_pending_packet_commands() -> None:
    card_a = _FakeCard('card-a')
    query_event = InputEvent(
        player_for=SimpleNamespace(unique_id=PlayerID.P2),
        input_keys=['k1'],
        input_validation=lambda _result: True,
        catalyst_action=ActionTypes.ATK_1,
        caller=SimpleNamespace(),
        query_data=CardSelectionQuery('Pick cards now', [card_a], [card_a], False, False),
    )

    notify_response = Response(ResponseType.CORE, Notify('first packet command', [PlayerID.P1], 3))
    query_response = Response(ResponseType.REQUIRES_QUERY, Data())
    query_response.source = query_event

    bridge = _make_drain_bridge_with_forward_responses(notify_response, query_response)

    drained = bridge._drain_engine(input_args=None, stop_after_command_batch=True)

    assert drained == [
        'notify player-1 first_packet_command 3',
        'input selection player-2 Pick_cards_now [card-a], [card-a], 1 false false',
    ]


def test_drain_engine_emits_transfer_move_before_reactor_query() -> None:
    card_a = _FakeCard('card-a')
    owner = SimpleNamespace(unique_id=PlayerID.P1)
    deck_holder = SimpleNamespace(player=owner, pile_type=Pile.DECK)
    hand_holder = SimpleNamespace(player=owner, pile_type=Pile.HAND)
    transfer = TransferCard(
        card=card_a,
        pile_from=deck_holder,
        pile_to=hand_holder,
        catalyst_action=ActionTypes.NONCHAR,
        caller=SimpleNamespace(),
        core_notif=None,
    )

    query_event = InputEvent(
        player_for=SimpleNamespace(unique_id=PlayerID.P2),
        input_keys=['k1'],
        input_validation=lambda _result: True,
        catalyst_action=ActionTypes.PASSIVE,
        caller=SimpleNamespace(),
        query_data=CardSelectionQuery('Pick cards now', [card_a], [card_a], False, False),
    )

    transfer_response = Response(ResponseType.CORE, Data())
    transfer_response.source = transfer
    query_response = Response(ResponseType.REQUIRES_QUERY, Data())
    query_response.source = query_event

    bridge = _make_drain_bridge_with_forward_responses(transfer_response, query_response)

    first_batch = bridge._drain_engine(input_args=None, stop_after_command_batch=True)
    second_batch = bridge._drain_engine(input_args=None, stop_after_command_batch=True)

    assert first_batch == ['mv card-a p1-hand']
    assert second_batch == ['input selection player-2 Pick_cards_now [card-a], [card-a], 1 false false']


def test_requires_query_input_event_is_latched_and_not_reemitted() -> None:
    card_a = _FakeCard('card-a')
    bridge = _make_bridge_with_cards(card_a)
    query_event = InputEvent(
        player_for=SimpleNamespace(unique_id=PlayerID.P2),
        input_keys=['k1'],
        input_validation=lambda _result: True,
        catalyst_action=ActionTypes.ATK_1,
        caller=SimpleNamespace(),
        query_data=CardSelectionQuery('Pick cards now', [card_a], [card_a], False, False),
    )
    bridge.env._engine.event_running = query_event

    response = Response(ResponseType.REQUIRES_QUERY, Data())
    response.source = query_event

    first_commands = bridge._commands_from_response(response)
    second_commands = bridge._commands_from_response(response)

    assert first_commands == ['input selection player-2 Pick_cards_now [card-a], [card-a], 1 false false']
    assert second_commands == []
    assert bridge._pending_input_query_event is query_event
    assert bridge._pending_input_query_command == first_commands[0]


def test_pump_outbound_waits_for_pending_input_query_latch() -> None:
    card_a = _FakeCard('card-a')
    bridge = _make_bridge_with_cards(card_a)
    query_event = InputEvent(
        player_for=SimpleNamespace(unique_id=PlayerID.P1),
        input_keys=['k1'],
        input_validation=lambda _result: True,
        catalyst_action=ActionTypes.ATK_1,
        caller=SimpleNamespace(),
        query_data=CardSelectionQuery('Pick cards now', [card_a], [card_a], False, False),
    )
    bridge.env._engine.event_running = query_event
    bridge._pending_input_query_event = query_event
    bridge._pending_input_query_command = 'input selection player-1 Pick_cards_now [card-a], [card-a], 1 false false'

    forward_calls = 0

    def _forward(_input_args=None):
        nonlocal forward_calls
        forward_calls += 1
        return Response(ResponseType.NO_MORE_EVENTS, Data())

    bridge.env.forward = _forward

    bridge._pump_outbound_until_next_command()

    assert forward_calls == 0
    assert bridge._outbound_command_queue == []


def test_setup_loaded_resends_latched_input_query_command() -> None:
    card_a = _FakeCard('card-a')
    bridge = _make_bridge_with_cards(card_a)
    query_event = InputEvent(
        player_for=SimpleNamespace(unique_id=PlayerID.P1),
        input_keys=['k1'],
        input_validation=lambda _result: True,
        catalyst_action=ActionTypes.ATK_1,
        caller=SimpleNamespace(),
        query_data=CardSelectionQuery('Pick cards now', [card_a], [card_a], False, False),
    )
    bridge.env._engine.event_running = query_event
    bridge._pending_input_query_event = query_event
    bridge._pending_input_query_command = 'input selection player-1 Pick_cards_now [card-a], [card-a], 1 false false'

    with patch('card_game.server.game_runner.environment_to_setup_payload', return_value={}):
        response = bridge.handle_frontend_event('setup_loaded', {}, None)

    assert response['commands'] == ['input selection player-1 Pick_cards_now [card-a], [card-a], 1 false false']
    assert bridge._awaiting_frontend_ack is True
    assert bridge._awaiting_frontend_ack_command == 'input selection player-1 Pick_cards_now [card-a], [card-a], 1 false false'


def test_input_result_accept_clears_pending_input_query_latch() -> None:
    card_a = _FakeCard('card-a')
    bridge = _make_bridge_with_cards(card_a)
    query_event = InputEvent(
        player_for=SimpleNamespace(unique_id=PlayerID.P1),
        input_keys=['k1'],
        input_validation=lambda _result: True,
        catalyst_action=ActionTypes.ATK_1,
        caller=SimpleNamespace(),
        query_data=CardSelectionQuery('Pick cards now', [card_a], [card_a], False, False),
    )
    bridge.env._engine.event_running = query_event
    bridge._pending_input_query_event = query_event
    bridge._pending_input_query_command = 'input selection player-1 Pick_cards_now [card-a], [card-a], 1 false false'

    command_side_effects, parsed_args = bridge._apply_frontend_event(
        'input_result',
        {'ordered_selections': ['card-a']},
    )

    assert command_side_effects == []
    assert isinstance(parsed_args, dict)
    assert parsed_args.get('input_result') == [card_a]
    assert bridge._pending_input_query_event is None
    assert bridge._pending_input_query_command is None
