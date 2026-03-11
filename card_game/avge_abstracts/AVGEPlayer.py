from ..abstract.player import Player
from .AVGECards import AVGECharacterCard
from .AVGECardholder import AVGECardholder
from ..constants import *
class AVGEPlayer(Player):
    def __init__(self, unique_id : PlayerID):
        super().__init__(str(unique_id))
        deck = AVGECardholder(unique_id + "_" + Pile.DECK)
        discard = AVGECardholder(unique_id + "_" + Pile.DISCARD)
        hand = AVGECardholder(unique_id + "_" + Pile.HAND)
        bench = AVGECardholder(unique_id + "_" + Pile.BENCH, [AVGECharacterCard], max_bench_size)
        active = AVGECardholder(unique_id + "_" + Pile.ACTIVE, [AVGECharacterCard], 1)
        self.add_cardholder(deck)
        self.add_cardholder(discard)
        self.add_cardholder(hand)
        self.add_cardholder(bench)
        self.add_cardholder(active)

        self.attributes : dict[AVGEPlayerAttribute, int] = {
            AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN: 1,
            AVGEPlayerAttribute.HAS_LOST: 0,
            AVGEPlayerAttribute.KO_COUNT: 0,
            AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN: 1,
            AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN: 1,
            AVGEPlayerAttribute.TOTAL_ENERGY_TOKENS: initial_tokens
        }