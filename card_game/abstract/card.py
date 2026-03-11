from __future__ import annotations
from card_game.constants import *
from . import environment, cardholder, player
class Card():
    def __init__(self, unique_id : str):
        self.unique_id = unique_id
        self.player : 'player.Player' = None
        self.cardholder : 'cardholder.Cardholder' = None
        self.env : 'environment.Environment' = None
    def __eq__(self, other : Card):
        return self.unique_id == other.unique_id
    def attach_to_cardholder(self, cardholder : 'cardholder.Cardholder'):
        self.cardholder = cardholder
        self.player = cardholder.player
        self.env = cardholder.env
    def play_card(self, args : Data = {}) -> Response:
        raise NotImplementedError()
    