from . import environment, cardholder
from ..constants import *
class Player():
    def __init__(self, unique_id : str):
        self.unique_id = unique_id
        self.cardholders : dict[Pile, 'cardholder.Cardholder'] = {}
        self.env : 'environment.Environment' = None
    def attach_to_env(self, env : 'environment.Environment'):
        self.env = env
        for _, cardholder in self.cardholders.items():
            cardholder.attach_to_player(self)
    def add_cardholder(self, cardholder : 'cardholder.Cardholder'):
        self.cardholders[cardholder.pile_type] = cardholder
        cardholder.attach_to_player(self)
    def __eq__(self, player2 : 'Player'):
        return self.unique_id == player2.unique_id
