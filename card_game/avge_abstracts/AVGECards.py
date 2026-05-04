from __future__ import annotations
from ..constants import *
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:  
    from .AVGEPlayer import AVGEPlayer
    from .AVGEEvent import AVGEEvent, AVGEPacket, DeferredAVGEPacket, PacketType
    from .AVGEEnvironment import AVGEEnvironment
    from .AVGECardholder import AVGECardholder
    from .AVGEEventListeners import AVGEAbstractEventListener, AVGEPacketListener
    from .AVGEConstrainer import AVGEConstraint

class AVGECard():
    def __init__(self, unique_id : str):
        self.unique_id = unique_id
        self.player : AVGEPlayer = None#type: ignore
        self.cardholder : AVGECardholder = None#type: ignore
        self.env : AVGEEnvironment = None#type: ignore
        self.owned_listeners : list[AVGEAbstractEventListener] = []
        self.owned_constraints : list[AVGEConstraint] = []
        self.owned_packet_listeners : list[AVGEPacketListener] = []
    def __hash__(self):
        return hash(self.unique_id)
    def __eq__(self, other : object):
        return isinstance(other, AVGECard) and self.unique_id == other.unique_id
    def __str__(self):
        text = type(self).__name__
        return "".join([" " + char if char.isupper() and i > 0 else char for i, char in enumerate(text)])
    def attach_to_cardholder(self, cardholder : AVGECardholder):
        self.cardholder = cardholder
        self.player = cardholder.player
        self.env = cardholder.env
    def add_listener(self, listener : AVGEAbstractEventListener):
        """Interface for cards to add their own external listeners. Cards that stick around
        should use this interface"""
        assert self.env is not None
        self.env.add_listener(listener)
        self.owned_listeners.append(listener)
    def add_constrainer(self, constrainer : AVGEConstraint):
        """Interface for cards to add their own constrainers. Cards 
        must use this interface"""
        assert self.env is not None
        self.env.add_constrainer(constrainer)
        self.owned_constraints.append(constrainer)
    def add_packet_listener(self, listener : AVGEPacketListener):
        """Interface for cards to add their own external listeners. Cards that stick around
        should use this interface"""
        assert self.env is not None
        self.env.add_packet_listener(listener)
        self.owned_packet_listeners.append(listener)
    def play_card(self, parent_event : AVGEEvent, args : dict | None = None) -> Response:
        raise NotImplementedError()
    def deactivate_card(self) -> PacketType | None:
        for listener in self.owned_listeners:
            listener.invalidate()#invalidate all owned listeners, since this card is no longer in play
        for constrainer in self.owned_constraints:
            constrainer.invalidate()#invalidates all owned constrainers, since this card has left play
        for listener in self.owned_packet_listeners:
            listener.invalidate()#invalidates all owned packet listeners, since this card has left play
    def reactivate_card(self):
        return#engine will revalidate all constrainers and listeners, so can do nothing. However, need to override if you override deactivate_card
    def propose(self, packet : AVGEPacket, priority : int = 0):
        assert self.env is not None
        self.env.propose(packet, priority)
    def extend(self, packet : list[AVGEEvent | DeferredAVGEPacket]):
        assert self.env is not None
        self.env.extend(packet)
    def extend_event(self, packet : list[AVGEEvent | DeferredAVGEPacket]):
        assert self.env is not None
        self.env.extend_event(packet)
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
        self.statuses_attached : dict[StatusEffect, list[AVGECard | AVGEPlayer | AVGEEnvironment]] = {effect: [] for effect in StatusEffect}
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
        self.atk_1_name : str | None = None
        self.atk_1_cost : int = mv_1_cost#default cost. doesn't matter if no atk_2
        self.atk_2_name : str | None = None
        self.atk_2_cost : int = mv_2_cost#default cost. doesn't matter if no atk_2
        self.has_passive : bool = False#any ability that activates when the card gets put in play
        self.active_name : str | None = None#any ability that can be activated whenever

    def atk_1(self, card : 'AVGECharacterCard', caller_action : ActionTypes) -> Response:
        raise NotImplementedError()
    def atk_2(self, card : 'AVGECharacterCard', caller_action : ActionTypes) -> Response:
        raise NotImplementedError()
    def can_play_active(self) -> bool:
        raise NotImplementedError()
    def active(self) -> Response:
        raise NotImplementedError()
    def passive(self) -> Response:
        raise NotImplementedError()
    
    def play_card(self, card : AVGECharacterCard, args : dict | None = None) -> Response:#type: ignore
        #Character cards can only have their abilities appropriated by other character cards, since abilities like "heal" make no sense for non-character cards. This may be tweaked later.
        if(args is None):
            args = {}
        if(args['type'] == ActionTypes.ATK_1):
            assert isinstance(args['caller_type'], ActionTypes)
            return self.atk_1(card, args['caller_type'])
        elif(args['type'] == ActionTypes.ATK_2):
            assert isinstance(args['caller_type'], ActionTypes)
            return self.atk_2(card, args['caller_type'])
        elif(args['type'] == ActionTypes.ACTIVATE_ABILITY):
            if(card != self):
                raise Exception("Tried to steal an ability. This is currently not supported.")
            return self.active()
        elif(args['type'] == ActionTypes.PASSIVE):
            if(card != self):
                raise Exception("Tried to steal an ability. This is currently not supported.")
            return self.passive()
    
    def attach_to_cardholder(self, cardholder : AVGECardholder):
        super().attach_to_cardholder(cardholder)
        self.tools_attached.env = self.env
        self.tools_attached.player = self.player

    def generic_response(self, caller : AVGECharacterCard, action_type : ActionTypes) -> Response:
        if(action_type == ActionTypes.ATK_1):
            return Response(ResponseType.CORE, Notify(f"{str(caller)} used {self.atk_1_name}!", all_players, default_timeout))
        if(action_type == ActionTypes.ACTIVATE_ABILITY):
            return Response(ResponseType.CORE, Notify(f"{str(caller)} used {self.active_name}!", all_players, default_timeout))
        if(action_type == ActionTypes.ATK_2):
            return Response(ResponseType.CORE, Notify(f"{str(caller)} used {self.atk_2_name}!", all_players, default_timeout))
        return Response(ResponseType.CORE, Data())


class AVGESupporterCard(AVGECard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
    def play_card(self, card : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:#type: ignore
        raise NotImplementedError()
    def generic_response(self, caller : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
        if(caller == self):
            return Response(ResponseType.CORE, RevealCards(
                f"{str(self)} was used!", all_players, default_timeout, [self]
            ))
        else:
            return Response(ResponseType.CORE, RevealCards(
                f"{str(caller)} used {str(self)}!", all_players, default_timeout, [self]
            ))

class AVGEItemCard(AVGECard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
    def play_card(self, card : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:#type: ignore
        raise NotImplementedError()
    def generic_response(self, caller : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
        if(caller == self):
            return Response(ResponseType.CORE, RevealCards(
                f"{self.player.username} used {str(self)}!", all_players, default_timeout, [self]
            ))
        else:
            return Response(ResponseType.CORE, RevealCards(
                f"{str(caller)} used {str(self)}!", all_players, default_timeout, [self]
            ))


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