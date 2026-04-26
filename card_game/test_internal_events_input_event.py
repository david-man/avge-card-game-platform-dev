from __future__ import annotations

from card_game.constants import ActionTypes, Data, ResponseType
from card_game.internal_events import InputEvent


class DummyCache:
    def __init__(self) -> None:
        self.set_calls: list[tuple[object, str, object]] = []
        self.delete_calls: list[tuple[object, str]] = []

    def set(self, key: object, input_key: str, value: object) -> None:
        self.set_calls.append((key, input_key, value))

    def delete(self, key: object, input_key: str) -> None:
        self.delete_calls.append((key, input_key))


class DummyEnv:
    def __init__(self) -> None:
        self.cache = DummyCache()


class DummyPlayer:
    def __init__(self, env: DummyEnv) -> None:
        self.env = env


def test_input_event_core_accepts_valid_input() -> None:
    env = DummyEnv()
    player = DummyPlayer(env)
    caller = object()

    event = InputEvent(
        player_for=player,
        input_keys=['choice'],
        input_validation=lambda values: True,
        catalyst_action=ActionTypes.ENV,
        caller=caller,
        query_data=Data(),
    )

    response = event.core({'input_result': ['none']})

    assert response.response_type == ResponseType.CORE
    assert env.cache.set_calls == [(caller, 'choice', 'none')]


def test_input_event_invert_core_deletes_cached_keys() -> None:
    env = DummyEnv()
    player = DummyPlayer(env)
    caller = object()

    event = InputEvent(
        player_for=player,
        input_keys=['choice'],
        input_validation=lambda values: True,
        catalyst_action=ActionTypes.ENV,
        caller=caller,
        query_data=Data(),
    )

    event.invert_core()

    assert env.cache.delete_calls == [(caller, 'choice')]
