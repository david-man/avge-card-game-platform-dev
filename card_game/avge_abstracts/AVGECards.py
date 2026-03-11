from ..abstract.card import Card
from ..constants import *
class AVGECharacterCard(Card):
    def __init__(self, unique_id : str):
        from .AVGECardholder import AVGEToolCardholder
        super().__init__(unique_id)
        self.tools_attached : AVGEToolCardholder = AVGEToolCardholder(unique_id + "_" + "_" + Pile.TOOL)
        self.statuses_attached : list[StatusEffect] = []
        #up to you to redefine all of these!
        self.attributes : dict[AVGECardAttribute, Type | float] = {
            AVGECardAttribute.TYPE: None,
            AVGECardAttribute.HP: None,
            AVGECardAttribute.MV_1_COST: None,
            AVGECardAttribute.MV_2_COST: None,
            AVGECardAttribute.SWITCH_COST: None,
            AVGECardAttribute.ENERGY_ATTACHED: 0
        }
        self.has_atk_1 : bool = False
        self.has_atk_2 : bool = False
        self.has_passive : bool = False#any ability that activates when the card gets put in play
        self.has_active : bool = False#any ability that can be activated whenever
    def atk_1(self, args = {}) -> bool:
        raise NotImplementedError()
    def atk_2(self, args = {}) -> bool:
        raise NotImplementedError()
    def active(self, args = {}) -> bool:
        raise NotImplementedError()
    def passive(self, args = {}) -> bool:
        raise NotImplementedError()
    def play_card(self, args = {}) -> bool:
        if(args['type'] == ActionTypes.ATK_1):
            return self.atk_1(args)
        elif(args['type'] == ActionTypes.ATK_2):
            return self.atk_2(args)
        elif(args['type'] == ActionTypes.ACTIVATE_ABILITY):
            return self.active(args)

class AVGESupporterCard(Card):
    def __init__(self, unique_id):
        super().__init__(unique_id)

class AVGEItemCard(Card):
    def __init__(self, unique_id):
        super().__init__(unique_id)

class AVGEToolCard(Card):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        self.card_attached : AVGECharacterCard = None
    
class AVGEStadiumCard(Card):
    def __init__(self ,unique_id):
        super().__init__(unique_id)
        self.is_active : bool = False#is this card the active stadium