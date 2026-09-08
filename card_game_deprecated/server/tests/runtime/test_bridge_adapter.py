from __future__ import annotations

from card_game.server.runtime.bridge_adapter import extract_bridge_commands


def test_extract_bridge_commands_supports_canonical_command_objects() -> None:
    payload = {
        'animation': {
            'target': 'both',
            'keyframes': [{'key': 'sfx-key', 'kind': 'sound'}],
        }
    }
    bridge_result = {
        'commands': [
            {
                'command': ' notify both hello -1 ',
                'response_payload': payload,
            }
        ],
        # Legacy field should be ignored when canonical payload exists.
        'command_payloads': [{'legacy': True}],
        'setup_payload': {'phase': 'init'},
    }

    extracted, next_setup = extract_bridge_commands(bridge_result)

    assert extracted == [
        {
            'command': 'notify both hello -1',
            'response_payload': payload,
        }
    ]
    assert next_setup == {'phase': 'init'}


def test_extract_bridge_commands_rejects_legacy_parallel_payload_arrays() -> None:
    payload = {
        'animation': {
            'target': 'both',
            'keyframes': [{'key': 'sfx-key', 'kind': 'sound'}],
        }
    }
    bridge_result = {
        'commands': [' notify both hello -1 '],
        'command_payloads': [payload],
        'setup_payload': {'phase': 'init'},
    }

    extracted, next_setup = extract_bridge_commands(bridge_result)

    assert extracted == []
    assert next_setup == {'phase': 'init'}
