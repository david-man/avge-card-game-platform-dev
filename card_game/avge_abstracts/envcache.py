from __future__ import annotations

from typing import TYPE_CHECKING
from dataclasses import dataclass
from .AVGECards import AVGECard
if TYPE_CHECKING:
    from typing import Any
    

@dataclass
class Change():
    card : AVGECard
@dataclass
class InsertKey(Change):
    key : str
    val : Any #immutable
@dataclass
class AlterKey(Change):
    key : str
    old_val : Any
    new_val : Any
@dataclass 
class DeleteKey(Change):
    key : str
    val : Any
class EnvironmentCache():
    
    def __init__(self, card_ids : list[str]):
        
        self._changelog : list[Change] = []
        self._capturing_changes = False
        self.empty_card = AVGECard("ENVIRONMENT_CARD_VARIABLE")
        self.cache = {k : {} for k in card_ids + ["ENVIRONMENT_CARD_VARIABLE"]}
    def set(self, card : AVGECard | None, key : str, value):
        if(card is None):
            card = self.empty_card
        if(self._capturing_changes):
            if(key not in self.cache[card.unique_id]):
                self._changelog.append(InsertKey(card, key, value))
            else:
                old_val = self.cache[card.unique_id][key]
                self._changelog.append(AlterKey(card, key, old_val, value))
        self.cache[card.unique_id][key] = value
    def get(self, card : AVGECard | None, key : str, default = None, one_look = False):
        """Gets value from data cache. If one look is on, this ALSO deletes the value"""
        if(card is None):
            card = self.empty_card
        val = self.cache[card.unique_id].get(key, default)
        if(one_look):
            self.delete(card, key)
        return val
    def delete(self, card : AVGECard | None, key : str):
        """Attempts to delete a key in data cache. If key does not exist, does nothing"""
        if(card is None):
            card = self.empty_card
        if(key not in self.cache[card.unique_id]):
            return
        if(self._capturing_changes):
            old_val = self.cache[card.unique_id][key]
            self._changelog.append(DeleteKey(card, key, old_val))
        del self.cache[card.unique_id][key]
    def rewind(self):
        self._capturing_changes = False
        while(len(self._changelog) > 0):
            change = self._changelog.pop(-1)#filo
            if(isinstance(change, DeleteKey)):
                self.cache[change.card.unique_id][change.key] = change.val
            elif(isinstance(change, AlterKey)):
                self.cache[change.card.unique_id][change.key] = change.old_val
            elif(isinstance(change, InsertKey)):
                del self.cache[change.card.unique_id][change.key]
        self._changelog = []
    def capture(self):
        self._capturing_changes = True
        self._changelog = []
    def release(self):
        self._capturing_changes = False
        self._changelog = []
    def wipe(self, card : AVGECard):
        if(card is None):
            card = self.empty_card
        for key in list(self.cache[card.unique_id]):
            self.delete(card, key)