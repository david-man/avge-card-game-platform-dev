from __future__ import annotations
from typing import TYPE_CHECKING, Any, cast
from enum import StrEnum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from .AVGEDeck import AVGEDeck, DeckType, AVGEToolHolder
from .labels import label_for
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
        self.actions: dict[ActionTypes, Ability] = {}

    @abstractmethod
    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event : TransferCard):
        '''A function that helps manage how a card's extensions (listeners, for example) evolve as the card moves around the board. This is called right before the card is actually moved on the board. All cards must at least acknowledge this function.'''
        pass

    def cache_set(self, key: str, new_value: Any):
        '''Sets a new value in the global cache'''
        self.env.cache_set(self, key, new_value)

    def cache_get(self, key: str, default: Any = None) -> Any:
        '''Reads a value from the global cache without journaling a change.'''
        return self.env.cache_get(self, key, default)

    def cache_delete(self, key: str):
        '''Cleans up a value in the global cache'''
        self.env.cache_delete(self, key)

    def add_listener(self, listener: AVGEEventListener):
        '''Adds an event listener to the engine'''
        self.env.add_listener(listener)

    def add_packet_listener(self, listener: AVGEPacketReactor):
        '''Adds an event listener to the engine'''
        self.env.add_packet_listener(listener)

    def add_constrainer(self, constrainer: AVGEConstrainer):
        '''Adds a constrainer to the engine'''
        self.env.add_constrainer(constrainer)

    def add_io_listener(self, listener : AVGEIOListener):
        '''Adds an io listener to the engine'''
        self.env.add_io_listener(listener)

    def additional_wire_state(self) -> dict[str, Any]:
        '''Explicit per-card state that may supplement the standard wire representation.'''
        return {}

    def __str__(self) -> str:
        '''A human-readable display name for this card, for use in any player-facing text
        (notifications, broadcasts) - "HappyRuthJara" -> "Happy Ruth Jara". Without this, an
        f-string like f"{card}" falls back to object.__repr__, leaking a raw Python object repr
        (e.g. "<...KathySun object at 0x...>") into what the player sees.'''
        return label_for(type(self).__name__)

    def _set_actions(self, actions: object, allowed: set[ActionTypes]) -> None:
        if not isinstance(actions, dict):
            raise TypeError(f"{type(self).__name__}.base_actions() must return a dict")
        raw_actions = cast(dict[object, object], actions)
        validated: dict[ActionTypes, Ability] = {}
        for key, action in raw_actions.items():
            if not isinstance(key, ActionTypes) or key not in allowed:
                raise ValueError(
                    f"{type(self).__name__} has unsupported action key: {key!r}"
                )
            if not isinstance(action, Ability):
                raise TypeError(
                    f"{type(self).__name__}.actions[{key.name}] must be an Ability"
                )
            # Treat this as untrusted runtime data even though Ability's annotation is
            # ActionTypes: subclasses and fixtures can still supply a malformed value.
            declared_type = vars(action).get("action_type")
            if not isinstance(declared_type, ActionTypes):
                raise ValueError(
                    f"{type(self).__name__}.actions[{key.name}] declares an invalid "
                    f"action type: {declared_type!r}"
                )
            if key != declared_type:
                raise ValueError(
                    f"{type(self).__name__}.actions[{key.name}] contains an action "
                    f"declaring {declared_type.name}"
                )
            validated[key] = action
        self.actions = validated

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
class Ability(ABC):
    name : str
    description : str
    action_type : ActionTypes

    @abstractmethod
    async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
        pass

    def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
        '''Whether this action is intrinsically legal. This must be side-effect-free.'''
        return True


@dataclass
class Attack(Ability):
    cost: int


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

        self._set_actions(
            self.base_actions(),
            {
                ActionTypes.ATK_1,
                ActionTypes.ATK_2,
                ActionTypes.ACTIVATE_ABILITY,
                ActionTypes.PASSIVE,
            },
        )

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
    def base_actions(self) -> dict[ActionTypes, Ability]:
        pass


class AVGENonCharacterCard(AVGECard, ABC):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._set_actions(self.base_actions(), {ActionTypes.NONCHAR})

    @abstractmethod
    def base_actions(self) -> dict[ActionTypes, Ability]:
        pass


class AVGESupporterCard(AVGENonCharacterCard):
    pass


class AVGEItemCard(AVGENonCharacterCard):
    pass


class AVGEStadiumCard(AVGENonCharacterCard):
    pass


class AVGEToolCard(AVGENonCharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in : DeckType):
        self.parent_card: AVGECharacterCard | None = None
        super().__init__(cardID, env, owner, deck_in)
