from __future__ import annotations

from types import SimpleNamespace

from card_game.catalog.characters.strings.AliceWang import _AliceHandEqualizerReactor
from card_game.constants import CardSelectionQuery, Interrupt, ResponseType
from card_game.internal_events import EmptyEvent, InputEvent


class _DummyCache:
    def get(self, _owner, _key, default=None, one_look=False):
        _ = one_look
        return default


def test_euclidean_interrupt_emits_progressing_notify_then_input_query() -> None:
    owner_hand = []
    opponent_hand = [SimpleNamespace(unique_id='card-a'), SimpleNamespace(unique_id='card-b')]
    opponent_discard = []

    env = SimpleNamespace(cache=_DummyCache())
    owner_player = SimpleNamespace(cardholders={'HAND': owner_hand})
    opponent_player = SimpleNamespace(cardholders={'HAND': opponent_hand, 'DISCARD': opponent_discard})
    owner_player.opponent = opponent_player

    owner_card = SimpleNamespace(env=env, player=owner_player)

    reactor = _AliceHandEqualizerReactor(owner_card)
    response = reactor.react()

    assert response.response_type == ResponseType.INTERRUPT
    assert isinstance(response.data, Interrupt)

    insertion = list(response.data.insertion)
    assert len(insertion) == 2

    assert isinstance(insertion[0], EmptyEvent)
    assert insertion[0].response_type == ResponseType.CORE

    assert isinstance(insertion[1], InputEvent)
    assert isinstance(insertion[1].query_data, CardSelectionQuery)