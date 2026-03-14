from .avge_abstracts.AVGECardholder import *
from .avge_abstracts.AVGECards import *
from .avge_abstracts.AVGEEnvironment import *
from .avge_abstracts.AVGEEvent import *
from .avge_abstracts.AVGEPlayer import *
from .internal_events import *

class BasicCharacterCard(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        self.attributes : dict[AVGECardAttribute, Type | float] = {
            AVGECardAttribute.TYPE: Type.BRASS,
            AVGECardAttribute.HP: 100,
            AVGECardAttribute.MV_1_COST: 0,
            AVGECardAttribute.MV_2_COST: 1,
            AVGECardAttribute.SWITCH_COST: 1,
            AVGECardAttribute.ENERGY_ATTACHED: 0
        }
        self.has_atk_1 : bool = True
        self.has_atk_2 : bool = True
        self.has_passive : bool = False#any ability that activates when the card gets put in play
        self.has_active : bool = False#any ability that can be activated whenever
    def atk_1(self):
        return True
    def atk_2(self):
        return True
    
    