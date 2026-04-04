from ..abstract.player import Player
from .AVGECards import AVGECharacterCard
from .AVGECardholder import AVGECardholder
from ..constants import *
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .AVGECardholder import AVGECardholder
    from .AVGEEnvironment import AVGEEnvironment
class AVGEPlayer(Player):
    def __init__(self, unique_id : PlayerID):
        super().__init__(str(unique_id))
        self.cardholders : dict[Pile, AVGECardholder] = {}
        self.env : AVGEEnvironment = None
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

        self.opponent : AVGEPlayer = None
        self.energy : list[EnergyToken] = []
        energy = [EnergyToken(f"{unique_id}_energy_token_{i}") for i in range(initial_tokens)]
        for token in energy:
            token.attach(self)
        print("HERE")
    def get_active_card(self) -> AVGECharacterCard:
        return self.cardholders[Pile.ACTIVE].peek()
    def get_cards_in_play(self) -> list[AVGECharacterCard]:
        return list(self.cardholders[Pile.BENCH]) + [self.get_active_card()]
    def get_next_turn(self) -> int:
        """Gets the round number for this player's next turn"""
        if(self.env.player_turn == self):
            return self.env.round_id + 2
        else:
            return self.env.round_id + 1
    def get_last_turn(self) -> int:
        """Gets the round number for this player's last turn"""
        if(self.env.player_turn == self):
            return self.env.round_id - 2
        else:
            return self.env.round_id - 1