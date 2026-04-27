from __future__ import annotations

from types import SimpleNamespace

import pytest

from card_game.constants import Data, Notify, PlayerID, Response, ResponseType, RevealCards
from card_game.internal_events import PlayCharacterCard, PlayNonCharacterCard
from card_game.server.game_runner import FrontendGameBridge
from card_game.server.scanner_commands import normalize_scanner_command


def _make_bridge() -> FrontendGameBridge:
    bridge = FrontendGameBridge.__new__(FrontendGameBridge)
    bridge.env = SimpleNamespace(
        _engine=SimpleNamespace(event_running=None),
        player_turn=SimpleNamespace(unique_id=PlayerID.P1),
        game_phase=None,
    )
    bridge._force_environment_sync_pending = False
    bridge._pending_input_query_event = None
    bridge._pending_input_query_command = None
    bridge._last_emitted_phase_token = None
    return bridge


def test_notify_payload_maps_players_and_timeout() -> None:
    bridge = _make_bridge()

    command_p1 = bridge._notify_from_notify(Notify('hello world', [PlayerID.P1], None))
    assert command_p1 == ['notify player-1 hello_world -1']

    command_both = bridge._notify_from_notify(Notify('sync up', [PlayerID.P1, PlayerID.P2], 3))
    assert command_both == ['notify both sync_up 3']


def test_accept_notify_response_emits_timeout_aware_command() -> None:
    bridge = _make_bridge()
    response = Response(ResponseType.ACCEPT, Notify('ready check', [PlayerID.P2], 8))

    commands = bridge._commands_from_response(response)

    assert commands == ['notify player-2 ready_check 8']


def test_accept_plain_data_response_emits_no_command() -> None:
    bridge = _make_bridge()
    response = Response(ResponseType.ACCEPT, Data())

    commands = bridge._commands_from_response(response)

    assert commands == []


def test_core_play_non_character_reveal_cards_emits_single_reveal_with_message() -> None:
    bridge = _make_bridge()

    response = Response(
        ResponseType.CORE,
        RevealCards('item used', [PlayerID.P1], 5, [SimpleNamespace(unique_id='item-1')]),
    )
    response.source = PlayNonCharacterCard.__new__(PlayNonCharacterCard)

    commands = bridge._commands_from_response(response)

    assert commands == ['reveal player-1 [item-1] item_used 5']


def test_core_play_non_character_reveal_cards_none_timeout_serializes_as_minus_one() -> None:
    bridge = _make_bridge()

    response = Response(
        ResponseType.CORE,
        RevealCards('item used', [PlayerID.P1], None, [SimpleNamespace(unique_id='item-1')]),
    )
    response.source = PlayNonCharacterCard.__new__(PlayNonCharacterCard)

    commands = bridge._commands_from_response(response)

    assert commands == ['reveal player-1 [item-1] item_used -1']


def test_core_play_non_character_reveal_cards_all_players_emits_single_reveal_both_command() -> None:
    bridge = _make_bridge()

    response = Response(
        ResponseType.CORE,
        RevealCards(
            'item used',
            [PlayerID.P1, PlayerID.P2],
            5,
            [SimpleNamespace(unique_id='item-1')],
        ),
    )
    response.source = PlayNonCharacterCard.__new__(PlayNonCharacterCard)

    commands = bridge._commands_from_response(response)

    assert commands == ['reveal both [item-1] item_used 5']


def test_core_play_character_notify_emits_notify_command() -> None:
    bridge = _make_bridge()

    response = Response(
        ResponseType.CORE,
        Notify('attacker used move', [PlayerID.P1, PlayerID.P2], 4),
    )
    response.source = PlayCharacterCard.__new__(PlayCharacterCard)

    commands = bridge._commands_from_response(response)

    assert commands == ['notify both attacker_used_move 4']


def test_scanner_notify_parser_requires_timeout_and_rejects_legacy_variants() -> None:
    action_timeout, normalized_timeout = normalize_scanner_command('notify both hello_world -1')
    assert action_timeout == 'notify'
    assert normalized_timeout == 'notify both hello_world -1'

    with pytest.raises(ValueError, match='timeout'):
        normalize_scanner_command('notify player-1 hello_world')

    with pytest.raises(ValueError, match='player-1 or player-2'):
        normalize_scanner_command('notify all hello_world 3')
