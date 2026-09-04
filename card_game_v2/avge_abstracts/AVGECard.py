from __future__ import annotations
from typing import TYPE_CHECKING, Any
from enum import StrEnum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from .AVGEDeck import AVGEDeck, DeckType, AVGEToolHolder
from ..constants import *
if TYPE_CHECKING:
    from .AVGEEnvironment import AVGEEnvironment, EnergyToken
    from .AVGEID import CardID
    from .AVGEPlayer import AVGEPlayer
    from .AVGEEventListener import *
    from .AVGEConstrainer import *
    from ..core.EventCatalog import TransferCard


class AVGECard(ABC):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in : DeckType):
        self.cardID = cardID
        self.owner = owner
        self.deck_type = deck_in
        self.env: AVGEEnvironment = env

    @abstractmethod
    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event : TransferCard):
        '''A function that helps manage how listeners, constrainers, and packet listeners are created and destroyed. All cards must at least acknowledge this function'''
        pass

    def cache_set(self, key: str, new_value: Any):
        '''Sets a new value in the global cache'''
        self.env.cache_set(self, key, new_value)

    def cache_delete(self, key: str):
        '''Cleans up a value in the global cache'''
        self.env.cache_delete(self, key)

    def add_listener(self, listener: AVGEEventListener):
        '''Adds an event listener to the engine'''
        self.env.add_listener(listener)

    def remove_listener(self, listener: AVGEEventListener):
        '''Removes an event listener from the engine'''
        self.env.remove_listener(listener)

    def add_packet_listener(self, listener: AVGEPacketReactor):
        '''Adds an event listener to the engine'''
        self.env.add_packet_listener(listener)

    def remove_packet_listener(self, listener: AVGEPacketReactor):
        '''Removes an event listener from the engine'''
        self.env.remove_packet_listener(listener)

    def add_constrainer(self, constrainer: AVGEConstrainer):
        '''Adds a constrainer to the engine'''
        self.env.add_constrainer(constrainer)

    def remove_constrainer(self, constrainer: AVGEConstrainer):
        '''Removes a constrainer from the engine'''
        self.env.remove_constrainer(constrainer)


class CardType(StrEnum):
    ALL = "ALL"  # treat this as a sort of "true" element that has no resistance and can be used for all energy
    WOODWIND = "WW"
    PERCUSSION = "PERC"
    PIANO = "PIANO"
    STRING = "STRING"
    GUITAR = 'GUITAR'
    CHOIR = "CHOIR"
    BRASS = "BRASS"

type_weaknesses = {
    CardType.STRING: CardType.GUITAR,
    CardType.GUITAR: CardType.WOODWIND,
    CardType.WOODWIND: CardType.PERCUSSION,
    CardType.PERCUSSION: CardType.CHOIR,
    CardType.CHOIR : CardType.PIANO,
    CardType.PIANO : CardType.BRASS,
    CardType.BRASS: CardType.STRING
}

@dataclass
class Attack(ABC):
    name : str
    description : str
    atk_type : ActionTypes
    cost : int

    @abstractmethod
    async def __call__(self, card : AVGECharacterCard, caller_action: ActionTypes):
        pass

@dataclass
class Ability(ABC):
    name : str
    description : str
    ability_type : ActionTypes

    @abstractmethod
    async def __call__(self, card : AVGECharacterCard):
        pass

    @abstractmethod
    def can_play(self, card : AVGECharacterCard):
        pass


class AVGECharacterCard(AVGECard, ABC):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in : DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self.statuses_attached: dict[StatusEffect, set[AVGECard | AVGEPlayer | AVGEEnvironment]] = {
            effect: set([]) for effect in StatusEffect}
        self.tools_attached: AVGEToolHolder = AVGEToolHolder(self.env.players[owner], DeckType.OFFHAND, [], self)
        self.energy_tokens: list[EnergyToken] = []
        self.hp = self.base_hp()
        self.max_hp = self.base_max_hp()
        self.card_type = self.base_card_type()
        self.retreat_cost = self.base_retreat_cost()

        self.attacks = self.base_attacks()
        self.abilities = self.base_abilities()

    @abstractmethod
    def base_hp(self) -> int:
        pass

    @abstractmethod
    def base_max_hp(self) -> int:
        pass

    @abstractmethod
    def base_card_type(self) -> CardType:
        pass

    @abstractmethod
    def base_retreat_cost(self) -> int:
        pass

    @abstractmethod
    def base_attacks(self) -> dict[ActionTypes, Attack]:
        pass

    @abstractmethod
    def base_abilities(self) -> dict[ActionTypes, Ability]:
        pass


class AVGESupporterCard(AVGECard):
    @abstractmethod
    async def play_card(self, card: 'AVGECard', caller_action: ActionTypes) -> None:
        pass


class AVGEItemCard(AVGECard):
    @abstractmethod
    async def play_card(self, card: 'AVGECard', caller_action: ActionTypes) -> None:
        pass


class AVGEStadiumCard(AVGECard):
    @abstractmethod
    async def play_card(self) -> None:
        pass


class AVGEToolCard(AVGECard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in : DeckType):
        self.parent_card: AVGECharacterCard | None = None
        super().__init__(cardID, env, owner, deck_in)
    @abstractmethod
    async def play_card(self) -> None:
        pass
