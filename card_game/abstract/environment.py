from __future__ import annotations
from . import player, cardholder, card
from ..engine.engine import Engine
from ..engine.event import Event
from ..engine.event_listener import AbstractEventListener
class Environment():
    def __init__(self):
        #you should override these values!
        self.players : dict[str, 'player.Player'] = {}
        self.cardholders : dict[str, 'cardholder.Cardholder'] = {}
        self.cards : dict[str, 'card.Card'] = {}
        self._engine : Engine = Engine()
    def transfer_card(self, card : str | card.Card, 
                      cardholder_from : str | cardholder.Cardholder, 
                      cardholder_to : str | cardholder.Cardholder):
        #transfers a card from one cardholder to another
        if(isinstance(cardholder_from, str)):
            cardholder_from = self.cardholders[cardholder_from]
        if(isinstance(cardholder_to, str)):
            cardholder_to = self.cardholders[cardholder_to]
        if(isinstance(card, str)):
            card = self.cards[card]
        cardholder_from.remove_card_by_id(card.unique_id)
        cardholder_to.add_card(card)
    def propose_event(self, e : Event, priority : int = 0):
        #opens engine in limited manner to cards and players
        self._engine._propose_event(e, priority=priority)
    def add_external_listener(self, el : AbstractEventListener):
        #opens engine in limited manner to cards and players
        self._engine.add_external_listener(el)