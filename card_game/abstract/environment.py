from __future__ import annotations
from . import player, cardholder, card
from ..engine.engine import Engine, Data
from ..engine.event import Event
from ..engine.event_listener import AbstractEventListener
class Environment():
    def __init__(self):
        #you should override these values!
        self.players : dict[str, 'player.Player'] = {}
        self._engine : Engine = Engine()
    def transfer_card(self, card : card.Card, 
                      cardholder_from : cardholder.Cardholder, 
                      cardholder_to : cardholder.Cardholder):
        #transfers a card from one cardholder to another. 
        cardholder_from.remove_card_by_id(card.unique_id)
        cardholder_to.add_card(card)
    def propose(self, e : Event, priority : int = 0):
        #opens engine in limited manner to cards and players
        self._engine._propose(e, priority=priority)
    def add_external_listener(self, el : AbstractEventListener):
        el.internal = False
        #opens engine in limited manner to cards and players
        self._engine.add_external_listener(el)
    def add_player(self, player : player.Player):
        player.attach_to_env(self)
        self.players[player.unique_id] = player
    def forward(self, args : Data | None = None):
        return self._engine.forward(args)