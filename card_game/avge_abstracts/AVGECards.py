from __future__ import annotations
from ..constants import *
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:  
    from .AVGEPlayer import AVGEPlayer
    from .AVGEEvent import AVGEEvent, AVGEPacket, DeferredAVGEPacket
    from .AVGEEnvironment import AVGEEnvironment
    from .AVGECardholder import AVGECardholder
    from .AVGEEventListeners import AVGEAbstractEventListener
    from .AVGEConstrainer import AVGEConstraint

class AVGECard():
    def __init__(self, unique_id : str):
        self.unique_id = unique_id
        self.player : AVGEPlayer = None#type: ignore
        self.cardholder : AVGECardholder = None#type: ignore
        self.env : AVGEEnvironment = None#type: ignore
        self.owned_listeners : list[AVGEAbstractEventListener] = []
        self.owned_constraints : list[AVGEConstraint] = []
    
    def __eq__(self, other : object):
        return isinstance(other, AVGECard) and self.unique_id == other.unique_id
    def __str__(self):
        return type(self).__name__
    def attach_to_cardholder(self, cardholder : AVGECardholder):
        self.cardholder = cardholder
        self.player = cardholder.player
        self.env = cardholder.env
    def add_listener(self, listener : AVGEAbstractEventListener):
        """Interface for cards to add their own external listeners. Cards 
        must use this interface"""
        assert self.env is not None
        self.env.add_listener(listener)
        self.owned_listeners.append(listener)
    def add_constrainer(self, constrainer : AVGEConstraint):
        """Interface for cards to add their own constrainers. Cards 
        must use this interface"""
        assert self.env is not None
        self.env.add_constrainer(constrainer)
        self.owned_constraints.append(constrainer)
    def play_card(self, parent_event : AVGEEvent, args : Data = {}) -> Response:
        raise NotImplementedError()
    def deactivate_card(self):
        for listener in self.owned_listeners:
            listener.invalidate()#invalidate all owned listeners, since this card is no longer in play
        for constrainer in self.owned_constraints:
            constrainer.invalidate()#invalidates all owned constrainers, since this card has left play
    def reactivate_card(self):
        return#engine will revalidate all constrainers and listeners, so can do nothing. However, need to override if you override deactivate_card
    def generate_response(self, response_type : ResponseType = ResponseType.CORE, data = None):
        #helper function to generate a response 
        return Response(self, response_type, data)
    def generate_interrupt(self, events : list[AVGEEvent]) -> Response:
        #Helper function to generate an INTERRUPT response easier
        return Response(self, ResponseType.INTERRUPT, {INTERRUPT_KEY: events})
    def propose(self, packet : AVGEPacket, priority : int = 0):
        assert self.env is not None
        self.env.propose(packet, priority)
    def extend(self, packet : list[AVGEEvent | DeferredAVGEPacket]):
        assert self.env is not None
        self.env.extend(packet)
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
        self.statuses_attached : dict[StatusEffect, list[AVGECard | None]] = {effect: [] for effect in StatusEffect}
        self.statuses_responsible : dict[StatusEffect, list[AVGECard]] = {effect: [] for effect in StatusEffect}
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
    def atk_1(card : 'AVGECharacterCard') -> Response:
        raise NotImplementedError()
    @staticmethod
    def atk_2(card : 'AVGECharacterCard') -> Response:
        raise NotImplementedError()
    @staticmethod
    def can_play_active(card : 'AVGECharacterCard') -> bool:
        raise NotImplementedError()
    @staticmethod
    def active(card : 'AVGECharacterCard') -> Response:
        raise NotImplementedError()
    @staticmethod
    def passive(card : 'AVGECharacterCard') -> Response:
        raise NotImplementedError()
    
    def play_card(self, card : AVGECharacterCard, args : Data = {}) -> Response:#type: ignore
        #Character cards can only have their abilities appropriated by other character cards, since abilities like "heal" make no sense for non-character cards. This may be tweaked later.

        if(args['type'] == ActionTypes.ATK_1):
            return self.atk_1(card)
        elif(args['type'] == ActionTypes.ATK_2):
            return self.atk_2(card)
        elif(args['type'] == ActionTypes.ACTIVATE_ABILITY):
            return self.active(card)
        elif(args['type'] == ActionTypes.PASSIVE):
            return self.passive(card)
    
    def attach_to_cardholder(self, cardholder : AVGECardholder):
        super().attach_to_cardholder(cardholder)
        self.tools_attached.env = self.env
        self.tools_attached.player = self.player


class AVGESupporterCard(AVGECard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
    @staticmethod
    def play_card(card : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:#type: ignore
        raise NotImplementedError()

class AVGEItemCard(AVGECard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
    @staticmethod
    def play_card(card : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:#type: ignore
        raise NotImplementedError()


class AVGEToolCard(AVGECard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        self.card_attached : AVGECharacterCard | None = None#the character card this AVGE tool card is attached to. None if not attached
    def attach_to_cardholder(self, cardholder):
        from .AVGECardholder import AVGEToolCardholder
        super().attach_to_cardholder(cardholder)
        self.card_attached = self.cardholder.parent_card if isinstance(self.cardholder, AVGEToolCardholder) else None
    def play_card(self) -> Response:#type: ignore
        #tools cannot have their abilities appropriated, since they're only meant to be played on attachment
        raise NotImplementedError()
    
class AVGEStadiumCard(AVGECard):
    def __init__(self ,unique_id):
        super().__init__(unique_id)
    def attach_to_cardholder(self, cardholder):
        temp = None
        if(cardholder.player is None):
            temp = self.player
        super().attach_to_cardholder(cardholder)
        if(temp is not None):
            self.player = temp
    def play_card(self) -> Response:#type: ignore
        #stadiums cannot have their abilities appropriated, since they're only meant to be played on attachment
        raise NotImplementedError()
    def _is_active_stadium(self):
        return (
            self.env is not None
            and len(self.env.stadium_cardholder) > 0
            and self.env.stadium_cardholder.peek() == self
        )