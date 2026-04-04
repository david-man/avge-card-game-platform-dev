from __future__ import annotations
from typing import TYPE_CHECKING, Callable
from . import player, cardholder, card
from ..engine.engine import Engine, Data

if TYPE_CHECKING:
    from ..engine.event import Event
    from ..engine.event_listener import AbstractEventListener
    from ..engine.constrainer import Constraint

class Environment():
    def __init__(self):
        #you should override these values!
        self.players : dict[str, 'player.Player'] = {}
        self._engine : Engine = Engine()
    def transfer_card(self, card : card.Card, 
                      cardholder_from : cardholder.Cardholder, 
                      cardholder_to : cardholder.Cardholder,
                      new_idx = None):
        #transfers a card from one cardholder to another. 
        cardholder_from.remove_card_by_id(card.unique_id)
        if(new_idx is None):
            cardholder_to.add_card(card)
        else:
            cardholder_to.insert_card(new_idx, card)
    def propose(self, e : Event | list[Event] | Callable[[], Event | list[Event]], priority : int = 0):
        #opens engine in limited manner to cards and players
        self._engine._propose(e, priority=priority)
    def add_listener(self, el : AbstractEventListener):
        """
        If you're thinking of using this, you should have a VERY clear update_status invalidation constraint that you can guarantee will fire eventually. 
        """
        el.internal = False
        #opens engine in limited manner to cards and players
        self._engine.add_listener(el)
    def add_constrainer(self, constrainer : Constraint):
        #opens engine in limited manner to cards and players
        self._engine.add_constraint(constrainer)
    def add_player(self, player : player.Player):
        player.attach_to_env(self)
        self.players[player.unique_id] = player
    def forward(self, args : Data = {}):
        return self._engine.forward(args)