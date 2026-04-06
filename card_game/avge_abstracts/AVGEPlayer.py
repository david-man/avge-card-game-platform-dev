from __future__ import annotations

from .AVGECards import AVGECharacterCard
from .AVGECardholder import AVGECardholder
from ..constants import *
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .AVGECardholder import AVGECardholder
    from .AVGEEnvironment import AVGEEnvironment
class AVGEPlayer():
    def __init__(self, unique_id : PlayerID):
        self.unique_id = unique_id
        self.cardholders : dict[Pile, AVGECardholder] = {}
        self.env : AVGEEnvironment = None#type: ignore
        deck = AVGECardholder(Pile.DECK)
        discard = AVGECardholder(Pile.DISCARD)
        hand = AVGECardholder(Pile.HAND)
        bench = AVGECardholder(Pile.BENCH, [AVGECharacterCard])
        active = AVGECardholder(Pile.ACTIVE, [AVGECharacterCard])
        self.add_cardholder(deck)
        self.add_cardholder(discard)
        self.add_cardholder(hand)
        self.add_cardholder(bench)
        self.add_cardholder(active)
        self.attributes : dict[AVGEPlayerAttribute, int] = {
            AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN: 1,
            AVGEPlayerAttribute.KO_COUNT: 0,
            AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN: 1,
            AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN: 1,
            AVGEPlayerAttribute.ATTACKS_LEFT: 1,
        }

        self.opponent : AVGEPlayer = self
        self.energy : list[EnergyToken] = []
        energy = [EnergyToken(f"{unique_id}_energy_token_{i}") for i in range(initial_tokens)]
        for token in energy:
            token.attach(self)
    def get_active_card(self) -> AVGECharacterCard:
        assert isinstance(self.cardholders[Pile.ACTIVE].peek(), AVGECharacterCard)
        return cast(AVGECharacterCard, self.cardholders[Pile.ACTIVE].peek())
    def get_cards_in_play(self) -> list[AVGECharacterCard]:
        return cast(list[AVGECharacterCard], self.cardholders[Pile.BENCH]) + [self.get_active_card()]
    def get_next_turn(self) -> int:
        """Gets the round number for this player's next turn"""
        assert self.env is not None
        if(self.env.player_turn == self):
            return self.env.round_id + 2
        else:
            return self.env.round_id + 1
    def get_last_turn(self) -> int:
        """Gets the round number for this player's last turn"""
        assert self.env is not None
        if(self.env.player_turn == self):
            return self.env.round_id - 2
        else:
            return self.env.round_id - 1
    def attach_to_env(self, env : AVGEEnvironment):
        self.env = env
        for _, cardholder in self.cardholders.items():
            cardholder.attach_to_player(self)
    def add_cardholder(self, cardholder : AVGECardholder):
        self.cardholders[cardholder.pile_type] = cardholder
        cardholder.attach_to_player(self)
    def __eq__(self, player2 : object):
        return isinstance(player2, AVGEPlayer) and self.unique_id == player2.unique_id