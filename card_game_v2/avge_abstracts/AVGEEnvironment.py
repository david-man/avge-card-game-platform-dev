from __future__ import annotations
from ..engine.engine import *
from ..engine.listener import EventListener, PacketReactor
from ..engine.constrainer import Constrainer
from ..engine.record import HistoricalStatus
from typing import TYPE_CHECKING, Any, Self
from dataclasses import dataclass
import random
from .AVGEPlayer import AVGEPlayer
from .AVGEDeck import AVGEDeck, DeckType
from ..constants import *
from ..engine.global_cache import Cache
from .AVGECard import AVGECharacterCard
if TYPE_CHECKING:
    from .AVGECard import AVGECard
    from ..core.AVGEIOManager import AVGEIO, IOType
    from .AVGEEventListener import *
    from ..engine.event import Event


@dataclass
class EnergyToken:
    token_id: str


class AVGEEnvironment:
    def __init__(self, io_manager: AVGEIO, decks: dict[User, list[type[AVGECard]]], core_listeners : list[type[AVGEEventListener]]):
        self.io_manager: AVGEIO = io_manager
        io_manager.register_to_environment(self)
        self.energy_tokens: list[EnergyToken] = [EnergyToken(
            f"token_{i}") for i in range(1, TOTAL_ENERGY_TOKENS + 1)]

        #actually instantiate cards, decks, players
        # players must be registered in self.players before their cards are constructed,
        # since card construction (AVGECharacterCard's tools_attached) looks up self.env.players[owner]
        start_num = 0
        self.players : dict[User, AVGEPlayer] = {}
        all_cards : list[AVGECard] = []
        for p in decks.keys():
            player = AVGEPlayer(p, {}, self)
            player.card_piles = {deck : AVGEDeck(player, deck, []) for deck in DeckType if deck != DeckType.STADIUM}
            self.players[p] = player
            initial_deck : list[AVGECard] = [card(f"card_{num}", self, p, DeckType.DECK) for num, card in enumerate(decks[p], start=start_num)]
            player.card_piles[DeckType.DECK].cards_holding = initial_deck
            start_num += len(initial_deck)
            all_cards += initial_deck

        # TurnEnd.act (core/EventCatalog.py) only re-seeds these per-turn allowances for whoever's
        # turn is starting NEXT - it never runs before the very first turn, so without this, the
        # player who goes first would play their entire first turn at AVGEPlayer.__init__'s zeroed
        # defaults (no attacks, no swaps, no supporter use, no energy adds). Seed both players, not
        # just whoever goes first (chosen below) - harmless for the other player, since TurnEnd
        # overwrites these again once it's actually their turn.
        for player in self.players.values():
            player.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = PER_TURN_ATKS
            player.attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN] = PER_TURN_SWAPS
            player.attributes[AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN] = PER_TURN_SUPPORTER_USE
            player.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] = PER_TURN_TOKEN_ADD

        owners : list[AVGECard | AVGEPlayer | Self] = all_cards + list(self.players.values()) + [self]
        self.cache = Cache(owners)
        self.engine: Engine = Engine(io_manager, self.cache)
        self.engine.listeners = [listener(self) for listener in core_listeners] # type: ignore
        self.stadium_cardholder : AVGEDeck = AVGEDeck(None, DeckType.STADIUM, []) #type: ignore

        #sets up turn
        self.turn : User = random.sample([User.PLAYER_1, User.PLAYER_2], 1)[0]
        self.round : int = 0

        #sets up a winner variable
        self.winner : User | None = None
        self.win_reason : WinReasons | None = None


    async def run(self):
        from ..core.EventCatalog import TurnEnd
        await self.engine.flush(lambda : self.search_history(TurnEnd)[0] is not None)

    # Cache API

    def cache_set(self, owner: AVGECard | AVGEPlayer | Self, key: str, new_value: Any):
        '''Sets a key-value in the owner's cache'''
        self.cache.set(owner, key, new_value)

    def cache_delete(self, owner: AVGECard | AVGEPlayer | Self, key: str):
        '''Deletes a key from the owner's associated cache key'''
        self.cache.remove(owner, key)
    
    # Engine API

    def add_listener(self, listener: EventListener):
        '''Adds an event listener to the engine'''
        self.engine.add_listener(listener)

    def add_packet_listener(self, listener: PacketReactor):
        '''Adds an event listener to the engine'''
        self.engine.add_packet_listener(listener)

    def add_constrainer(self, constrainer: Constrainer):
        '''Adds a constrainer to the engine'''
        self.engine.add_constrainer(constrainer)

    def add_io_listener(self, io_listener : IOListener):
        '''Adds an IO Listener to the engine'''
        self.engine.add_io_listener(io_listener)

    def push_packet(self, packet: Packet):
        '''Adds a packet to the front of the queue such that it runs right after the current one'''
        self.engine.push_packet(packet)

    def append_packet(self, packet: Packet):
        '''Adds a packet to the back of the queue such that it runs after all other packets currently in the queue'''
        self.engine.append_packet(packet)

    def search_history[EV: Event](self,
                                   event_type: type[EV],
                                   kwargs: dict[str, Any] | None = None,
                                   increment: int = 0,
                                   index_to_start: int = 0,
                                   specific_status: HistoricalStatus = HistoricalStatus.IMMUTABLE,
                                   attribute_search: bool = False) -> tuple[EV | None, int]:
        '''Searches history for the earliest matching event. See History.search for details.'''
        return self.engine.search_history(event_type, kwargs, increment, index_to_start, specific_status, attribute_search)

    # IOManager API

    async def report[T](self, io_type : IOType[T], io_id : AVGEEngineID) -> T:
        return await self.engine.report(io_type, io_id)

    async def broadcast(self, io_type : IOType[None]):
        return await self.engine.broadcast(io_type)

    # Utils
    def get_player_active(self, user : User | AVGEPlayer) -> AVGECharacterCard:
        if isinstance(user, User):
            user = self.players[user]
        card = user.card_piles[DeckType.ACTIVE_CARD][0]
        assert isinstance(card, AVGECharacterCard)
        return card

    def get_current_player(self) -> AVGEPlayer:
        return self.players[self.turn]

    def get_opponent(self, user : User | AVGEPlayer) -> AVGEPlayer:
        if isinstance(user, AVGEPlayer):
            user = user.id
        return self.players[user.next]
