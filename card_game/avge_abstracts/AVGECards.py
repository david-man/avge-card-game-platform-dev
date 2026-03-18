from __future__ import annotations
from ..abstract.card import Card
from ..engine.event_listener import AbstractEventListener
from ..constants import *

class AVGECharacterCard(Card):
    def __init__(self, unique_id : str):
        from .AVGECardholder import AVGEToolCardholder
        super().__init__(unique_id)
        self.tools_attached : AVGEToolCardholder = AVGEToolCardholder()
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

        self.owned_listeners : list[AbstractEventListener] = []
    def atk_1(owner_card : 'AVGECharacterCard', args : Data | None = None) -> bool:
        raise NotImplementedError()
    def atk_2(owner_card : 'AVGECharacterCard', args : Data | None = None) -> bool:
        raise NotImplementedError()
    def active(owner_card : 'AVGECharacterCard', args : Data | None = None) -> bool:
        raise NotImplementedError()
    def passive(owner_card : 'AVGECharacterCard', args : Data | None = None) -> bool:
        raise NotImplementedError()
    def play_card(self, args : Data | None = None) -> bool:
        if(args is None):
            args = {}
        if(args['type'] == ActionTypes.ATK_1):
            return self.atk_1(args)#automatically populates owner_card with self
        elif(args['type'] == ActionTypes.ATK_2):
            return self.atk_2(args)
        elif(args['type'] == ActionTypes.ACTIVATE_ABILITY):
            return self.active(args)
        elif(args['type'] == ActionTypes.PASSIVE):
            return self.passive(args)
    def deactivate_card(self):
        raise NotImplementedError()


class AVGESupporterCard(Card):
    def __init__(self, unique_id):
        super().__init__(unique_id)
    def play_card(self, args : Data | None = None) -> Response:
        raise NotImplementedError()
    def deactivate_card(self):
        raise NotImplementedError()

class AVGEItemCard(Card):
    def __init__(self, unique_id):
        super().__init__(unique_id)
    def play_card(self, args : Data | None = None) -> Response:
        raise NotImplementedError()
    def deactivate_card(self):
        raise NotImplementedError()

class AVGEToolCard(Card):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        self.card_attached : AVGECharacterCard = None#the character card this AVGE tool card is attached to. None if not attached
    def play_card(self, args : Data | None = None) -> Response:
        raise NotImplementedError()
    def deactivate_card(self):
        raise NotImplementedError()
    
class AVGEStadiumCard(Card):
    def __init__(self ,unique_id):
        from .AVGEPlayer import AVGEPlayer
        super().__init__(unique_id)
        self.is_active : bool = False#is this card the active stadium
        self.original_owner : AVGEPlayer = None#original owner of the card
    def attach_to_cardholder(self, cardholder):
        from .AVGECardholder import AVGEStadiumCardholder
        if(cardholder.player is not None):
            self.original_owner = cardholder.player
            self.is_active = False#can never be active when the cardholder is owned by a player
        if(isinstance(cardholder, AVGEStadiumCardholder)):
            self.is_active = True
        return super().attach_to_cardholder(cardholder)
    def play_card(self, args : Data | None = None) -> Response:
        raise NotImplementedError()
    def deactivate_card(self):
        raise NotImplementedError()