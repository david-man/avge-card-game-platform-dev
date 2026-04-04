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
    def __init__(self, 
                 unique_id : str,
                 hp : int,
                 card_type : CardType,
                 retreat_cost : int,
                 mv_1_cost : int = 0,
                 mv_2_cost : int = 0):
        from .AVGECardholder import AVGEToolCardholder
        super().__init__(unique_id)
        self.tools_attached : AVGEToolCardholder = AVGEToolCardholder(self)
        self.statuses_attached : dict[StatusEffect, list[Card]] = {effect: [] for effect in StatusEffect}
        self.player : AVGEPlayer = self.player
        self.env : AVGEEnvironment = self.env


        #up to you to redefine all of the following!
        self.hp : int = hp
        self.max_hp : int = hp
        self.card_type : CardType = card_type
        self.energy : list[EnergyToken] = []
        
        #all the following should be considered CONST
        self.default_max_hp : int = hp
        self.default_type : CardType = card_type
        self.retreat_cost : int = retreat_cost#default cost
        self.has_atk_1 : bool = False
        self.atk_1_cost : int = mv_1_cost#default cost. doesn't matter if no atk_2
        self.has_atk_2 : bool = False
        self.atk_2_cost : int = mv_2_cost#default cost. doesn't matter if no atk_2
        self.has_passive : bool = False#any ability that activates when the card gets put in play
        self.has_active : bool = False#any ability that can be activated whenever

    @staticmethod
    def atk_1(caller_card : 'AVGECharacterCard', parent_event : AVGEEvent) -> Response:
        raise NotImplementedError()
    @staticmethod
    def atk_2(caller_card : 'AVGECharacterCard', parent_event : AVGEEvent) -> Response:
        raise NotImplementedError()
    @staticmethod
    def can_play_active(caller_card : 'AVGECharacterCard') -> bool:
        raise NotImplementedError()
    @staticmethod
    def active(caller_card : 'AVGECharacterCard', parent_event : AVGEEvent) -> Response:
        raise NotImplementedError()
    @staticmethod
    def passive(caller_card : 'AVGECharacterCard', parent_event : AVGEEvent) -> Response:
        raise NotImplementedError()
    
    def play_card(self, parent_event : AVGEEvent, card_for : AVGECharacterCard, args : Data = {}) -> Response:
        #Character cards can only have their abilities appropriated by other character cards, since abilities like "heal" make no sense for non-character cards. This may be tweaked later.

        if(args['type'] == ActionTypes.ATK_1):
            return self.atk_1(card_for, parent_event)
        elif(args['type'] == ActionTypes.ATK_2):
            return self.atk_2(card_for, parent_event)
        elif(args['type'] == ActionTypes.ACTIVATE_ABILITY):
            return self.active(card_for, parent_event)
        elif(args['type'] == ActionTypes.PASSIVE):
            return self.passive(card_for, parent_event)
    
    def attach_to_cardholder(self, cardholder : AVGECardholder):
        super().attach_to_cardholder(cardholder)
        self.tools_attached.env = self.env
        self.tools_attached.player = self.player


class AVGESupporterCard(AVGECard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
    @staticmethod
    def play_card(card_for : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard, parent_event : AVGEEvent) -> Response:
        raise NotImplementedError()

class AVGEItemCard(AVGECard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
    @staticmethod
    def play_card(card_for : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard, parent_event : AVGEEvent, ) -> Response:
        raise NotImplementedError()


class AVGEToolCard(AVGECard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        self.card_attached : AVGECharacterCard = None#the character card this AVGE tool card is attached to. None if not attached
    def play_card(self, parent_event : AVGEEvent) -> Response:
        #tools cannot have their abilities appropriated, since they're only meant to be played on attachment
        raise NotImplementedError()
    
class AVGEStadiumCard(AVGECard):
    def __init__(self ,unique_id):
        super().__init__(unique_id)
        self.original_owner : AVGEPlayer = None#original owner of the card before it became the stadium.
    def attach_to_cardholder(self, cardholder):
        if(cardholder.player is not None):
            self.original_owner = cardholder.player
    def play_card(self, parent_event : AVGEEvent) -> Response:
        #stadiums cannot have their abilities appropriated, since they're only meant to be played on attachment
        raise NotImplementedError()
    def _is_active_stadium(self):
        return (
            self.env is not None
            and len(self.env.stadium_cardholder) > 0
            and self.env.stadium_cardholder.peek() == self
        )