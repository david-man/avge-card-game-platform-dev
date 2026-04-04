from __future__ import annotations
from card_game.constants import *
from . import environment, cardholder, player
from ..engine import event_listener, constrainer
from typing import Tuple, Callable
class Card():
    def __init__(self, unique_id : str):
        self.unique_id = unique_id
        self.player : 'player.Player' = None
        self.cardholder : 'cardholder.Cardholder' = None
        self.env : 'environment.Environment' = None
        self.owned_listeners : list[event_listener.AbstractEventListener] = []
        self.owned_constraints : list[constrainer.Constraint] = []

    def __eq__(self, other : Card):
        return self.unique_id == other.unique_id
    def attach_to_cardholder(self, cardholder : 'cardholder.Cardholder'):
        self.cardholder = cardholder
        self.player = cardholder.player
        self.env = cardholder.env
    def add_listener(self, listener : event_listener.AbstractEventListener):
        """Interface for cards to add their own external listeners. Cards 
        must use this interface"""
        self.env.add_listener(listener)
        self.owned_listeners.append(listener)
    def add_constrainer(self, constrainer : constrainer.Constraint):
        """Interface for cards to add their own constrainers. Cards 
        must use this interface"""
        self.env.add_constrainer(constrainer)
        self.owned_constraints.append(constrainer)
    def play_card(self, parent_event : Event, args : Data = {}) -> Response:
        raise NotImplementedError()
    def deactivate_card(self):
        for listener in self.owned_listeners:
            listener.invalidate()#invalidate all owned listeners, since this card is no longer in play
        for constrainer in self.owned_constraints:
            constrainer.invalidate()#invalidates all owned constrainers, since this card has left play
    def reactivate_card(self):
        return#engine will revalidate all constrainers and listeners, so can do nothing. However, need to override if you override deactivate_card
    def generate_response(self, response_type : ResponseType = ResponseType.CORE, data = None, announce = False):
        #helper function to generate a response 
        return Response(self, response_type, data, announce = (announce or response_type == ResponseType.REQUIRES_QUERY))
    def generate_interrupt(self, events : list[Event]) -> Response:
        #Helper function to generate an INTERRUPT response easier
        return Response(self, ResponseType.INTERRUPT, {INTERRUPT_KEY: events}, True)
    def propose(self, e : Event | list[Event] | Callable[[], Event | list[Event]], priority : int = 0):
        self.env.propose(e, priority)