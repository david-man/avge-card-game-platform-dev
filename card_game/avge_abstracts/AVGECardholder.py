from __future__ import annotations
from typing import Type, TYPE_CHECKING, Generic, TypeVar, Tuple
from ..constants import Pile
if TYPE_CHECKING:
    from .AVGEPlayer import AVGEPlayer
    from .AVGEEnvironment import AVGEEnvironment
    from .AVGECards import AVGECharacterCard, AVGECard
    from .AVGEEvent import AVGEEvent


T = TypeVar(name="T")
class OrderedDict(Generic[T]):
    def __init__(self):
        self._dict : dict[str, T] = {}
        self._order : list[str] = []
    def reorder(self, new_loc : int, k : str):
        if(k not in self._dict):
            raise KeyError(f"{k} not found")
        self._order.remove(k)
        self._order.insert(new_loc, k)
    def insert(self, loc : int, k : str, v : T):
        if(k in self._dict):
            self.reorder(loc, k)
        else:
            self._order.insert(loc, k)
            self._dict[k] = v
    def append(self, k : str, v : T):
        if(k in self._dict):
            self._order.remove(k)
        self._order.append(k)
        self._dict[k] = v
    def push(self, k : str, v : T):
        self.insert(0, k, v)
    def keys(self) -> list[str]:
        return list(self._order)
    def values(self) -> list[T]:
        return [self._dict[k] for k in self._order]
    def items(self) -> list[Tuple[str, T]]:
        l = []
        for k in self._order:
            l.append((k, self._dict[k]))
        return l
    def pop(self, idx = -1) -> Tuple[str, T]:
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

class AVGECardholder():
    def __init__(self,
                 pile_type : Pile,
                 expected_classes : list[Type[AVGECard]] | None = None):
        self.pile_type = pile_type
        self.cards_by_id : OrderedDict[AVGECard] = OrderedDict()
        self.player : AVGEPlayer = None#type: ignore
        self.env : AVGEEnvironment = None#type: ignore
        if(expected_classes is None):
            expected_classes=[]
        self.expected_classes = expected_classes

    def add_card(self, card : AVGECard):
        if(self.expected_classes != []):
            for c in self.expected_classes:
                if(isinstance(card, c)):
                    self.cards_by_id.append(card.unique_id, card)
                    card.attach_to_cardholder(self)
                    return
            raise Exception("Not the right type of card!")
        else:
            self.cards_by_id.append(card.unique_id, card)
            card.attach_to_cardholder(self)
    def __add__(self, other : AVGECardholder) -> list:
        to_ret = []
        for card in self:
            to_ret.append(card)
        for card in other:
            to_ret.append(card)
        return to_ret
    def __len__ (self):
        return len(self.cards_by_id)
    def __eq__(self, other : object):
        if not isinstance(other, AVGECardholder):
            return False
        pile_same = (self.pile_type == other.pile_type)
        player_same = (self.player is None and other.player is None) or (self.player is not None and other.player is not None and self.player.unique_id == other.player.unique_id)
        return (pile_same and player_same) 
    def attach_to_player(self, player : AVGEPlayer):
        self.player = player
        self.env = player.env
        for _, card in self.cards_by_id.items():
            card.attach_to_cardholder(self)
    def get_posn(self, card : AVGECard):
        return self.cards_by_id.get_posn(card.unique_id)
    def get_order(self):
        return self.cards_by_id._order
    def reorder(self, new_order : list[str]):
        if(len(new_order) == len(self)
           and len(set(new_order).intersection(set(self.cards_by_id._order))) == len(new_order)):
            self.cards_by_id._order = new_order
        else:
            raise Exception("Failed to reorder: new order is not the same as the old order!")
    def insert_card(self, idx, card : AVGECard):
        self.cards_by_id.insert(idx, card.unique_id, card)
        card.attach_to_cardholder(self)
    def pop_card(self, top : bool = True) -> AVGECard:
        #pops a card from either the top or the bottom of the deck
        if(top):
            return self.cards_by_id.pop(0)[1]
        return self.cards_by_id.pop()[1]
    def peek_n(self, n : int) -> list[AVGECard]:
        if(n <= len(self)):
            #gets the top n cards of the cardholder
            to_return = []
            items = self.cards_by_id.items()
            for i in range(n):
                to_return.append(items[i][1])
            return to_return
        else:
            raise IndexError()
    def peek(self) -> AVGECard:
        return self.peek_n(1)[0]
    def remove_card_by_id(self, card_id : str):
        del self.cards_by_id[card_id]
    def get_card(self, card_id : str) -> AVGECard:
        return self.cards_by_id[card_id]
    def __contains__(self, item : AVGECard):
        return isinstance(item, AVGECard) and item.unique_id in self.cards_by_id
    def __iter__(self):
        return (x for x in self.cards_by_id.values())
            
class AVGEToolCardholder(AVGECardholder):
    def __init__(self, parent_card : AVGECharacterCard):
        from .AVGECards import AVGEToolCard
        super().__init__(Pile.TOOL, [AVGEToolCard])
        self.parent_card : AVGECharacterCard = parent_card


class AVGEStadiumCardholder(AVGECardholder):
    def __init__(self):
        from .AVGECards import AVGEStadiumCard
        super().__init__(Pile.STADIUM, [AVGEStadiumCard])
        