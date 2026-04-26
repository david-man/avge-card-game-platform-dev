from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from card_game.server import frontend_formatter as formatter


class _FakeCharacterCard:
    def __init__(self, owner_id: str, card_id: str) -> None:
        self.player = SimpleNamespace(unique_id=owner_id)
        self.unique_id = card_id


def test_attached_energy_token_maps_to_shared_energy_holder() -> None:
    env = SimpleNamespace(players={'p1': object(), 'p2': object()}, energy=[])
    token = SimpleNamespace(holder=_FakeCharacterCard('p2', 'C777'))

    with patch.object(formatter, 'AVGECharacterCard', _FakeCharacterCard):
        owner_id, holder_id, attached_to_card_id = formatter._energy_holder_and_attachment(env, token)

    assert owner_id == 'p2'
    assert holder_id == 'shared-energy'
    assert attached_to_card_id == 'C777'


def test_player_energy_reserve_maps_to_shared_energy_holder() -> None:
    env = SimpleNamespace(players={'p1': object(), 'p2': object()}, energy=[])
    token = SimpleNamespace(holder=SimpleNamespace(unique_id='p1'))

    owner_id, holder_id, attached_to_card_id = formatter._energy_holder_and_attachment(env, token)

    assert owner_id == 'p1'
    assert holder_id == 'shared-energy'
    assert attached_to_card_id is None


def test_environment_energy_pool_maps_to_energy_discard_holder() -> None:
    env = SimpleNamespace(players={'p1': object(), 'p2': object()}, energy=[])
    token = SimpleNamespace(holder=env)

    owner_id, holder_id, attached_to_card_id = formatter._energy_holder_and_attachment(env, token)

    assert owner_id == 'shared'
    assert holder_id == 'energy-discard'
    assert attached_to_card_id is None
