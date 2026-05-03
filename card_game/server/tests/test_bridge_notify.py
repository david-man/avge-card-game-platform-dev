from __future__ import annotations

from types import SimpleNamespace

import pytest

from card_game.constants import (
    Animation,
    Data,
    Notify,
    ParticleExplosion,
    PlayerID,
    Response,
    ResponseType,
    RevealCards,
    RevealStr,
    SoundEffect,
)
from card_game.internal_events import AVGECardHPChange, PlayCharacterCard, PlayNonCharacterCard
from card_game.server.bridge.command_utils import command_token as bridge_command_token
from card_game.server.game_runner import FrontendGameBridge
from card_game.server.scanner.scanner_commands import normalize_scanner_command


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
    bridge._pending_packet_commands = []
    bridge._pending_packet_command_payloads = []
    bridge._outbound_command_queue = []
    bridge._outbound_command_payload_queue = []
    bridge._awaiting_frontend_ack = False
    bridge._awaiting_frontend_ack_command = None
    return bridge


def test_notify_payload_maps_players_and_timeout() -> None:
    bridge = _make_bridge()

    command_p1 = bridge._notify_from_notify(Notify('hello world', [PlayerID.P1], None))
    assert command_p1 == ['notify:;:player-1:;:hello world:;:-1']

    command_both = bridge._notify_from_notify(Notify('sync up', [PlayerID.P1, PlayerID.P2], 3))
    assert command_both == ['notify:;:both:;:sync up:;:3']


def test_command_token_preserves_spaces_by_default() -> None:
    assert bridge_command_token('listener name with spaces') == 'listener name with spaces'
    assert bridge_command_token('   ') == 'message'


def test_bridge_command_token_stays_space_delimited() -> None:
    bridge = _make_bridge()
    assert bridge._command_token('hello world') == 'hello_world'


def test_accept_notify_response_emits_timeout_aware_command() -> None:
    bridge = _make_bridge()
    response = Response(ResponseType.ACCEPT, Notify('ready check', [PlayerID.P2], 8))

    commands = bridge._commands_from_response(response)

    assert commands == ['notify:;:player-2:;:ready check:;:8']


def test_accept_plain_data_response_emits_no_command() -> None:
    bridge = _make_bridge()
    response = Response(ResponseType.ACCEPT, Data())

    commands = bridge._commands_from_response(response)

    assert commands == []


def test_response_accompanying_animation_serializes_for_first_command_payload() -> None:
    bridge = _make_bridge()
    response = Response(
        ResponseType.ACCEPT,
        Notify('ready check', [PlayerID.P1], 4),
        accompanying_animation=Animation(
            keyframes=[
                SoundEffect('reveal.mp3'),
                ParticleExplosion(SimpleNamespace(unique_id='card-7'), 'logo.png'),
            ],
            players=[PlayerID.P1],
        ),
    )

    commands = bridge._commands_from_response(response)
    payloads = bridge._response_payloads_for_commands(response, commands)

    assert commands == ['notify:;:player-1:;:ready check:;:4']
    assert payloads == [
        {
            'animation': {
                'target': 'player-1',
                'keyframes': [
                    {
                        'key': 'reveal.mp3',
                        'kind': 'sound',
                    },
                    {
                        'key': 'logo.png',
                        'kind': 'particles',
                        'card_id': 'card-7',
                    },
                ],
            },
        },
    ]


def test_core_play_non_character_reveal_cards_emits_single_reveal_with_message() -> None:
    bridge = _make_bridge()

    response = Response(
        ResponseType.CORE,
        RevealCards('item used', [PlayerID.P1], 5, [SimpleNamespace(unique_id='item-1')]),
    )
    response.source = PlayNonCharacterCard.__new__(PlayNonCharacterCard)

    commands = bridge._commands_from_response(response)

    assert commands == ['reveal:;:player-1:;:[item-1]:;:item used:;:5']


def test_core_play_non_character_reveal_cards_none_timeout_serializes_as_minus_one() -> None:
    bridge = _make_bridge()

    response = Response(
        ResponseType.CORE,
        RevealCards('item used', [PlayerID.P1], None, [SimpleNamespace(unique_id='item-1')]),
    )
    response.source = PlayNonCharacterCard.__new__(PlayNonCharacterCard)

    commands = bridge._commands_from_response(response)

    assert commands == ['reveal:;:player-1:;:[item-1]:;:item used:;:-1']


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

    assert commands == ['reveal:;:both:;:[item-1]:;:item used:;:5']


def test_core_play_character_notify_emits_notify_command() -> None:
    bridge = _make_bridge()

    response = Response(
        ResponseType.CORE,
        Notify('attacker used move', [PlayerID.P1, PlayerID.P2], 4),
    )
    response.source = PlayCharacterCard.__new__(PlayCharacterCard)

    commands = bridge._commands_from_response(response)

    assert commands == ['notify:;:both:;:attacker used move:;:4']


def test_reveal_cards_preserves_spaced_card_ids_and_message() -> None:
    bridge = _make_bridge()

    response = Response(
        ResponseType.CORE,
        RevealCards('played reveal card', [PlayerID.P1], 5, [SimpleNamespace(unique_id='BUO Stand')]),
    )
    response.source = PlayNonCharacterCard.__new__(PlayNonCharacterCard)

    commands = bridge._commands_from_response(response)

    assert commands == ['reveal:;:player-1:;:[BUO Stand]:;:played reveal card:;:5']


def test_reveal_str_preserves_spaces_in_message_and_items() -> None:
    bridge = _make_bridge()

    response = Response(
        ResponseType.CORE,
        RevealStr('used reveal str', [PlayerID.P1], 4, ['BUO Stand', 'Main Hall']),
    )
    response.source = PlayNonCharacterCard.__new__(PlayNonCharacterCard)

    commands = bridge._commands_from_response(response)

    assert commands == ['notify:;:player-1:;:used reveal str: BUO Stand, Main Hall:;:4']


def test_hp_change_notify_payload_is_emitted_before_hp_command() -> None:
    bridge = _make_bridge()

    source = AVGECardHPChange.__new__(AVGECardHPChange)
    source.target_card = SimpleNamespace(unique_id='char-1', hp=80, max_hp=100)

    response = Response(
        ResponseType.CORE,
        Notify('damage resolved', [PlayerID.P1], 3),
    )
    response.source = source

    commands = bridge._commands_from_response(response)

    assert commands == [
        'notify:;:player-1:;:damage resolved:;:3',
        'hp char-1 80 100',
    ]


def test_hp_change_reveal_payload_is_emitted_before_hp_command() -> None:
    bridge = _make_bridge()

    source = AVGECardHPChange.__new__(AVGECardHPChange)
    source.target_card = SimpleNamespace(unique_id='char-2', hp=70, max_hp=100)

    response = Response(
        ResponseType.CORE,
        RevealCards('revealed from hp event', [PlayerID.P1], 5, [SimpleNamespace(unique_id='BUO Stand')]),
    )
    response.source = source

    commands = bridge._commands_from_response(response)

    assert commands == [
        'reveal:;:player-1:;:[BUO Stand]:;:revealed from hp event:;:5',
        'hp char-2 70 100',
    ]


def test_hp_change_animation_payload_stays_on_hp_command_after_notify_first() -> None:
    bridge = _make_bridge()

    source = AVGECardHPChange.__new__(AVGECardHPChange)
    source.target_card = SimpleNamespace(unique_id='char-3', hp=60, max_hp=100)

    response = Response(
        ResponseType.CORE,
        Notify('damage resolved', [PlayerID.P1], 3),
        accompanying_animation=Animation(
            keyframes=[
                SoundEffect('punch.mp3'),
                ParticleExplosion(SimpleNamespace(unique_id='char-3'), 'crit.png'),
            ],
            players=[PlayerID.P1, PlayerID.P2],
        ),
    )
    response.source = source

    commands = bridge._commands_from_response(response)
    payloads = bridge._response_payloads_for_commands(response, commands)

    assert commands == [
        'notify:;:player-1:;:damage resolved:;:3',
        'hp char-3 60 100',
    ]
    assert payloads == [
        None,
        {
            'animation': {
                'target': 'both',
                'keyframes': [
                    {
                        'key': 'punch.mp3',
                        'kind': 'sound',
                    },
                    {
                        'key': 'crit.png',
                        'kind': 'particles',
                        'card_id': 'char-3',
                    },
                ],
            },
        },
    ]


def test_scanner_notify_parser_requires_timeout_and_rejects_legacy_variants() -> None:
    action_timeout, normalized_timeout = normalize_scanner_command('notify both hello_world -1')
    assert action_timeout == 'notify'
    assert normalized_timeout == 'notify both hello_world -1'

    with pytest.raises(ValueError, match='timeout'):
        normalize_scanner_command('notify player-1 hello_world')

    with pytest.raises(ValueError, match='player-1 or player-2'):
        normalize_scanner_command('notify all hello_world 3')
