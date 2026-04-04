from __future__ import annotations
from ..abstract.cardholder import Cardholder, OrderedDict
from ..abstract.card import Card
from typing import Type, TYPE_CHECKING
from ..constants import Pile
if TYPE_CHECKING:
    from .AVGEPlayer import AVGEPlayer
    from .AVGEEnvironment import AVGEEnvironment
    from .AVGECards import AVGECharacterCard
class AVGECardholder(Cardholder):
    def __init__(self,
                 pile_type : Pile,
                 expected_classes : list[Type] = None,
                 max_size : int = None):
        super().__init__(pile_type)
        self.player : AVGEPlayer = None
        self.env : AVGEEnvironment = None
        
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
    def __iter__(self):
        return super().__iter__()
            
class AVGEToolCardholder(AVGECardholder):
    def __init__(self, parent_card : AVGECharacterCard):
        from .AVGECards import AVGEToolCard
        super().__init__(Pile.TOOL, [AVGEToolCard])
        self.parent_card : AVGECharacterCard = parent_card


class AVGEStadiumCardholder(AVGECardholder):
    def __init__(self):
        from .AVGECards import AVGEStadiumCard
        super().__init__(Pile.STADIUM, [AVGEStadiumCard])
        self.player = None
        