from __future__ import annotations
from card_game.constants import *
from . import environment, cardholder, player
from ..engine import event_listener
class Card():
    def __init__(self, unique_id : str):
        self.unique_id = unique_id
        self.player : 'player.Player' = None
        self.cardholder : 'cardholder.Cardholder' = None
        self.env : 'environment.Environment' = None
        self.owned_listeners : list[event_listener.AbstractEventListener] = []

        #data cache to store any extra variables you want to use
        #please limit keys and vals to basic objects and primitive variables, since this gets deepcopied
        self.data_cache = {}

    def __eq__(self, other : Card):
        return self.unique_id == other.unique_id
    def attach_to_cardholder(self, cardholder : 'cardholder.Cardholder'):
        self.cardholder = cardholder
        self.player = cardholder.player
        self.env = cardholder.env
    def add_external_listener(self, listener : event_listener.AbstractEventListener):
        """Interface for cards to add their own external listeners. Cards 
        must use this interface"""
        self.env.add_external_listener(listener)
        self.owned_listeners.append(listener)
    def play_card(self, args : Data = {}) -> Response:
        raise NotImplementedError()
    def deactivate_card(self):
        #deactivates the card and any lingering effects it may have
        raise NotImplementedError()
    