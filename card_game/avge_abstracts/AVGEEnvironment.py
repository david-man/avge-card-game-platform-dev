from ..abstract.environment import Environment
from .AVGECardholder import AVGEStadiumCardholder, AVGECardholder
from .AVGEPlayer import AVGEPlayer
from ..abstract.card import Card
from ..constants import *
from enum import StrEnum

class GamePhase(StrEnum):
    INIT = 'init'
    TURN_BEGIN = 'begin'
    PICK_CARD = 'pick'
    PHASE_2 = 'phase_2'
    ATK_PHASE = 'phase_atk'
    TURN_END = 'end'
class AVGEEnvironment(Environment):
    def __init__(self):
        super().__init__()
        self.stadium_cardholder : AVGEStadiumCardholder = AVGEStadiumCardholder(Pile.STADIUM)
        self.cardholders[Pile.STADIUM] = self.stadium_cardholder
        #adds players
        self.players[PlayerID.P1] = AVGEPlayer(PlayerID.P1)
        self.players[PlayerID.P2] = AVGEPlayer(PlayerID.P2)
        #registers all cardholders
        for _, cardholder in self.players[PlayerID.P1].cardholders.items():
            self.cardholders[cardholder.unique_id] = cardholder
        for _, cardholder in self.players[PlayerID.P2].cardholders.items():
            self.cardholders[cardholder.unique_id] = cardholder

        #pointer to whose turn it is
        self.player_turn : AVGEPlayer = None
        self.winner : AVGEPlayer = None

        self.game_phase : GamePhase = GamePhase.INIT 

    def register_card(self, card : Card, pile : AVGECardholder):
        #registers a new card
        if(pile.unique_id in self.cardholders.keys()):
            self.cardholders[pile.unique_id].add_card(card)
            self.cards[card.unique_id] = card
        raise IndexError()
    def get_active_card(self, player_id : PlayerID):
        return self.players[player_id].cardholders[Pile.ACTIVE].peek_n()
    