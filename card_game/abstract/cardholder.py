from __future__ import annotations
from card_game.constants import *
from collections import OrderedDict
from . import environment, card, player
class Cardholder():
    def __init__(self, unique_id : str):
        self.unique_id = unique_id
        self.cards_by_id : OrderedDict[str, 'card.Card'] = {}
        self.player : 'player.Player' = None
        self.env : 'environment.Environment' = None
    def __eq__(self, other : Cardholder):
        return self.unique_id == other.unique_id
    def attach_to_player(self, player : 'player.Player'):
        self.player = player
        self.env = player.env
        for _, card in self.cards_by_id.items():
            card.attach_to_cardholder(self)
    def add_card(self, card : 'card.Card'):
        self.cards_by_id[card.unique_id] = card
    def pop_card(self, top : bool = True) -> 'card.Card':
        #pops a card from either the top or the bottom of the deck
        return self.cards_by_id.popitem(last = (not top))[1]
    def peek_n(self, n : int = 1) -> 'card.Card':
        #gets the top n cards of the cardholder
        to_return = []
        iterator = iter(self.cards_by_id.items())
        for _ in range(n):
            to_return.append(next(iterator))
        return to_return
    def remove_card_by_id(self, card_id : str):
        del self.cards_by_id[card_id]
    def get_card(self, card_id : str) -> 'card.Card':
        return self.cards_by_id[card_id]
    def num_cards(self) -> int:
        return len(self.cards_by_id)
    def __contains__(self, item : 'card.Card'):
        return item.unique_id in self.cards_by_id