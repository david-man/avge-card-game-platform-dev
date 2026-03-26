from __future__ import annotations
from ..abstract.card import Card
from ..engine.event_listener import AbstractEventListener
from ..constants import *
from typing import TYPE_CHECKING, Tuple, Callable

if TYPE_CHECKING:
    
    from .AVGEPlayer import AVGEPlayer
    from .AVGEEvent import AVGEEvent
    from .AVGEEnvironment import AVGEEnvironment
    from .AVGECardholder import AVGECardholder
    from .AVGEEventListeners import AVGEAbstractEventListener
    from .AVGEConstrainer import AVGEConstraint

class AVGECard(Card):
    def __init__(self, unique_id : str):
        super().__init__(unique_id)
        self.player : AVGEPlayer = None
        self.cardholder : AVGECardholder = None
        self.env : AVGEEnvironment = None
        self.owned_listeners : list[AVGEAbstractEventListener] = []
        self.owned_constraints : list[AVGEConstraint] = []
class AVGECharacterCard(AVGECard):
    def __init__(self, unique_id : str):
        from .AVGECardholder import AVGEToolCardholder
        super().__init__(unique_id)
        self.tools_attached : AVGEToolCardholder = AVGEToolCardholder()
        self.statuses_attached : dict[StatusEffect, int] = {}
        #up to you to redefine all of these!
        self.attributes : dict[AVGECardAttribute, CardType | float] = {
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

        self.player : AVGEPlayer = self.player
        self.env : AVGEEnvironment = self.env
    @staticmethod
    def atk_1(owner_card : 'AVGECharacterCard', parent_event : AVGEEvent, args : Data = {}) -> Response:
        raise NotImplementedError()
    @staticmethod
    def atk_2(owner_card : 'AVGECharacterCard', parent_event : AVGEEvent, args : Data = {}) -> Response:
        raise NotImplementedError()
    
    def can_play_active(self) -> bool:
        raise NotImplementedError()
    @staticmethod
    def active(owner_card : 'AVGECharacterCard', parent_event : AVGEEvent, args : Data = {}) -> Response:
        raise NotImplementedError()
    
    def passive(self, parent_event : AVGEEvent, args : Data = {}) -> Response:
        raise NotImplementedError()
    def play_card(self, parent_event : AVGEEvent, card_for : AVGECharacterCard, args : Data = {}) -> Response:
        if(parent_event is None):
            raise ValueError("parent_event is required")
        if(args['type'] == ActionTypes.ATK_1):
            return self.atk_1(card_for, parent_event, args)
        elif(args['type'] == ActionTypes.ATK_2):
            return self.atk_2(card_for, parent_event, args)
        elif(args['type'] == ActionTypes.ACTIVATE_ABILITY):
            return self.active(card_for, parent_event, args)
        elif(args['type'] == ActionTypes.PASSIVE):
            return self.passive(parent_event, args)


class AVGESupporterCard(AVGECard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
    def play_card(self, parent_event : AVGEEvent, card_for : AVGECharacterCard = None, args : Data = {}) -> Response:
        raise NotImplementedError()

class AVGEItemCard(AVGECard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
    def play_card(self, parent_event : AVGEEvent, card_for : AVGECharacterCard = None, args : Data = {}) -> Response:
        raise NotImplementedError()


class AVGEToolCard(AVGECard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        self.card_attached : AVGECharacterCard = None#the character card this AVGE tool card is attached to. None if not attached
    def play_card(self, parent_event : AVGEEvent, card_for : AVGECharacterCard, args : Data = {}) -> Response:
        raise NotImplementedError()
    
class AVGEStadiumCard(AVGECard):
    def __init__(self ,unique_id):
        super().__init__(unique_id)
        self.original_owner : AVGEPlayer = None#original owner of the card before it became the stadium.
    def attach_to_cardholder(self, cardholder):
        if(cardholder.player is not None):
            self.original_owner = cardholder.player
    def play_card(self, parent_event : AVGEEvent, card_for : AVGECharacterCard = None, args : Data = {}) -> Response:
        raise NotImplementedError()
    def _is_active_stadium(self):
        return (
            self.env is not None
            and len(self.env.stadium_cardholder) > 0
            and self.env.stadium_cardholder.peek() == self
        )