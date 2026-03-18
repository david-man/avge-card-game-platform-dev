from __future__ import annotations
from card_game.constants import *
from collections import OrderedDict
from . import environment, card, player
class Cardholder():
    def __init__(self, pile_type : Pile):
        self.pile_type = pile_type
        self.cards_by_id : OrderedDict[str, 'card.Card'] = {}
        self.player : 'player.Player' = None
        self.env : 'environment.Environment' = None
    def __len__ (self):
        return len(self.cards_by_id)
    def __eq__(self, other : Cardholder):
        pile_same = (self.pile_type == other.pile_type)
        player_same = (self.player is None and other.player is None) or (self.player is not None and other.player is not None and self.player.unique_id == other.player.unique_id)
        return (pile_same and player_same) 
    def attach_to_player(self, player : 'player.Player'):
        self.player = player
        self.env = player.env
        for _, card in self.cards_by_id.items():
            card.attach_to_cardholder(self)
    def add_card(self, card : 'card.Card'):
        self.cards_by_id[card.unique_id] = card
        card.attach_to_cardholder(self)
    def pop_card(self, top : bool = True) -> 'card.Card':
        #pops a card from either the top or the bottom of the deck
        return self.cards_by_id.popitem(last = (not top))[1]
    def peek_n(self, n : int) -> list['card.Card']:
        if(n <= len(self)):
            #gets the top n cards of the cardholder
            to_return = []
            iterator = iter(self.cards_by_id.items())
            for _ in range(n):
                to_return.append(next(iterator)[1])
            return to_return
        else:
            raise IndexError()
    def peek(self) -> 'card.Card':
        return self.peek_n(1)[0]
    def remove_card_by_id(self, card_id : str):
        del self.cards_by_id[card_id]
    def get_card(self, card_id : str) -> 'card.Card':
        return self.cards_by_id[card_id]
    def __contains__(self, item : 'card.Card'):
        return item.unique_id in self.cards_by_id