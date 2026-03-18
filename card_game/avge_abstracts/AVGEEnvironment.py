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
        self.stadium_cardholder : AVGEStadiumCardholder = AVGEStadiumCardholder()
        self.stadium_cardholder.env = self
        #adds players
        p1 = AVGEPlayer(PlayerID.P1)
        p2 = AVGEPlayer(PlayerID.P2)
        p1.opponent = p2
        p2.opponent = p1
        self.add_player(p1)
        self.add_player(p2)
        #pointer to whose turn it is
        self.player_turn : AVGEPlayer = None
        self.winner : AVGEPlayer = None

        self.game_phase : GamePhase = GamePhase.INIT 
    def get_active_card(self, player_id : PlayerID):
        return self.players[player_id].cardholders[Pile.ACTIVE].peek()
    