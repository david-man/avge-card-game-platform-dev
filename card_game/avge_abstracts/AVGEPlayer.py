from ..abstract.player import Player
from .AVGECards import AVGECharacterCard
from .AVGECardholder import AVGECardholder
from ..constants import *
class AVGEPlayer(Player):
    def __init__(self, unique_id : PlayerID):
        super().__init__(str(unique_id))
        deck = AVGECardholder(unique_id + "_" + Pile.DECK, Pile.DECK)
        discard = AVGECardholder(unique_id + "_" + Pile.DISCARD, Pile.DISCARD)
        hand = AVGECardholder(unique_id + "_" + Pile.HAND, Pile.HAND)
        bench = AVGECardholder(unique_id + "_" + Pile.BENCH, Pile.BENCH, [AVGECharacterCard])
        active = AVGECardholder(unique_id + "_" + Pile.ACTIVE, Pile.ACTIVE, [AVGECharacterCard])
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

        self.opponent : AVGEPlayer = None
    def get_active_card(self):
        return self.cardholders[Pile.ACTIVE].peek_n(1)