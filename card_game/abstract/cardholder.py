from __future__ import annotations
from card_game.constants import *
from . import environment, card, player
from typing import Tuple, Generic, TypeVar

T = TypeVar('T')

class OrderedDict(Generic[T]):
    def __init__(self):
        self._dict : dict[str, T] = {}
        self._order : list[str] = []
    def reorder(self, new_loc : int, k : str):
        if(k not in self._dict):
            raise KeyError(f"{k} not found")
        self._order.remove(k)
        self._order.insert(new_loc, k)
    def insert(self, loc : int, k : str, v : 'card.Card'):
        if(k in self._dict):
            self.reorder(loc, k)
        else:
            self._order.insert(loc, k)
            self._dict[k] = v
    def append(self, k : str, v : 'card.Card'):
        if(k in self._dict):
            self._order.remove(k)
        self._order.append(k)
        self._dict[k] = v
    def push(self, k : str, v : 'card.Card'):
        self.insert(0, k, v)
    def keys(self) -> list[str]:
        return list(self._order)
    def values(self) -> list['card.Card']:
        return [self._dict[k] for k in self._order]
    def items(self) -> list[Tuple[str, 'card.Card']]:
        l = []
        for k in self._order:
            l.append((k, self._dict[k]))
        return l
    def pop(self, idx = -1) -> Tuple[str, 'card.Card']:
        key = self._order.pop(idx)
        val = self._dict[key]
        del self._dict[key]
        return key, val
    def get_posn(self, k) -> int:
        if(k not in self._dict.keys()):
            raise Exception("key not found")
        else:
            return self._order.index(k)
    def __getitem__(self, idx):
        return self._dict[idx]
    def __setitem__(self, k, v):
        if(k in self._dict):
            self._dict[k] = v
        else:
            self.append(k, v)
    def __len__(self):
        return len(self._order)
    def __contains__(self, item : str):
        return item in self._dict
    def __delitem__(self, k):
        self._order.remove(k)
        del self._dict[k]
class Cardholder():
    def __init__(self, pile_type : Pile):
        self.pile_type = pile_type
        self.cards_by_id : OrderedDict[Card] = OrderedDict()
        self.player : 'player.Player' = None
        self.env : 'environment.Environment' = None
    def __add__(self, other : Cardholder) -> list:
        to_ret = []
        for card in self:
            to_ret.append(card)
        for card in other:
            to_ret.append(card)
        return to_ret
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
    def get_posn(self, card : 'card.Card'):
        return self.cards_by_id.get_posn(card.unique_id)
    def get_order(self):
        return self.cards_by_id._order
    def reorder(self, new_order : list[str]):
        if(len(new_order) == len(self)
           and len(set(new_order).intersection(set(self.cards_by_id._order))) == len(new_order)):
            self.cards_by_id._order = new_order
        else:
            raise Exception("Failed to reorder: new order is not the same as the old order!")
    def add_card(self, card : 'card.Card'):
        self.cards_by_id.append(card.unique_id, card)
        card.attach_to_cardholder(self)
    def insert_card(self, idx, card : 'card.Card'):
        self.cards_by_id.insert(idx, card.unique_id, card)
        card.attach_to_cardholder(self)
    def pop_card(self, top : bool = True) -> 'card.Card':
        #pops a card from either the top or the bottom of the deck
        if(top):
            return self.cards_by_id.pop(0)[1]
        return self.cards_by_id.pop()[1]
    def peek_n(self, n : int) -> list['card.Card']:
        if(n <= len(self)):
            #gets the top n cards of the cardholder
            to_return = []
            items = self.cards_by_id.items()
            for i in range(n):
                to_return.append(items[i][1])
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
        return isinstance(item, card.Card) and item.unique_id in self.cards_by_id
    def __iter__(self):
        return (x for x in self.cards_by_id.values())