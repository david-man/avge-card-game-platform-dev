from __future__ import annotations
from ..abstract.cardholder import Cardholder
from ..abstract.card import Card
from typing import Type

class AVGECardholder(Cardholder):
    def __init__(self, unique_id : str,
                 expected_classes : list[Type] = None,
                 max_size : int = None):
        super().__init__(unique_id)
        self.max_size = max_size
        self.expected_classes = expected_classes
    def add_card(self, card : 'Card'):
        if(self.max_size is not None and len(self.cards_by_id) == self.max_size):
            raise Exception("Max size limit reached!")
        elif(self.expected_classes is not None):
            for c in self.expected_classes:
                if(isinstance(card, c)):
                    super().add_card(card)
                    return
            raise Exception("Not the right type of card!")
        else:
            super().add_card(card)
            
class AVGEToolCardholder(AVGECardholder):
    def __init__(self, unique_id : str):
        from .AVGECards import AVGEToolCard
        super().__init__(unique_id, [AVGEToolCard])
        self.attached_to_card : bool = False
        self.parent_card : Card = None

class AVGEStadiumCardholder(AVGECardholder):
    def __init__(self, unique_id : str):
        from .AVGECards import AVGEStadiumCard
        super().__init__(unique_id, [AVGEStadiumCard])
        self.attached_to_env : bool = False
        self.parent_env : Card = None
        