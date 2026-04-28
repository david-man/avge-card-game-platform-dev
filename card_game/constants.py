from __future__ import annotations
from enum import Enum, StrEnum
from typing import Any, TYPE_CHECKING, Callable, TypeVar, Sequence
from dataclasses import dataclass
if TYPE_CHECKING:
    from card_game.engine.event import Event
    from card_game.engine.event_listener import AbstractEventListener
    from card_game.avge_abstracts.AVGECards import AVGECard, AVGECharacterCard
    from card_game.avge_abstracts.AVGEPlayer import AVGEPlayer
    from card_game.avge_abstracts.AVGEEnvironment import AVGEEnvironment

cards_per_deck = 30
initial_hand_size = 15
max_bench_size = 3
initial_tokens = 100
kos_to_win = 3

per_turn_token_add = 100
per_turn_supporter = 1
per_turn_swaps = 1
per_turn_atks = 1

default_timeout = 5

ACTIVE_FLAG = 'active_flag'

@dataclass
class Data():
    pass
@dataclass
class Notify(Data):
    message : str
    players : list[PlayerID]
    timeout : int | None #None if message should not automatically be accepted after some num of seconds.
@dataclass
class EndOfTurn(Notify):
    pass
@dataclass
class RevealCards(Notify):
    cards : list[AVGECard]
@dataclass
class RevealStr(Notify):
    items : list[str]
@dataclass
class Interrupt[EV](Data):
    type Gen = Callable[[], list[EV] | list[Gen] | list[EV | Gen]]
    insertion : list[EV] | list[Gen] | list[EV | Gen]
@dataclass
class CardSelectionQuery(Data):
    header_msg : str
    targets : Sequence[AVGECard]
    display : Sequence[AVGECard]
    allows_none : bool
    allows_repeat : bool
@dataclass
class StrSelectionQuery(Data):
    header_msg : str
    targets : list[str]
    display : list[str]
    allows_none : bool
    allows_repeat : bool
@dataclass
class OrderingQuery(Data):
    unordered_listeners : list[AbstractEventListener]
@dataclass
class GameEnd(Data):
    winner : PlayerID
    reason : str
@dataclass
class Phase2Data(Data):
    player : PlayerID
@dataclass
class AtkPhaseData(Data):
    player : PlayerID
@dataclass
class IntegerInputData(Data):
    header_msg : str
    min_num : int#inclusive
    max_num : int#inclusive
@dataclass
class CoinflipData(Data):
    header_msg : str
@dataclass
class D6Data(Data):
    header_msg : str
class ResponseType(StrEnum):
    SKIP = "SKIP"#something in the list went awry/was rejected, undo the whole packet
    ACCEPT = 'ACCEPT'#accept and move to the next step
    REQUIRES_QUERY = "REQUIRES_QUERY"#requires query, try again
    INTERRUPT = "INTERRUPT"#packet interrupted: events at INTERRUPT_KEY need to be finished first before this packet can continue
    FAST_FORWARD = "FF"#fast forward the event to its closing. if used right after an INTERRUPT, you can "override" an event completely.
    FINISHED = "FINISHED"#event has finished naturally
    FINISHED_PACKET = "FINISHED_PACKET"#packet has finished naturally
    GAME_END = "GAME_END"#game has ended because of a reason that isn't "no more events"
    CORE = "CORE"#core was run successfully

    NO_MORE_EVENTS = "NO_MORE_EVENTS"
    NEXT_EVENT = "NEXT_EVENT"
    NEXT_PACKET = 'NEXT_PACKET'

EV = TypeVar('EV', bound='Event')
class Response():
    def __init__(self, 
                 response_type : ResponseType, 
                 data : Data):
        self.response_type = response_type
        self.data = data

@dataclass
class AVGEEngineID():
    caller : AVGECard | AVGEPlayer | AVGEEnvironment
    action_type : ActionTypes
    header_class : type[AVGECard] | None



class AVGEAttributeModifier(StrEnum):
    ADDITIVE = 'additive'
    SET_STATE = 'setstate'
    SUBSTRACTIVE = 'substractive'
class AVGEPlayerAttribute(StrEnum):

    #turn specific
    
    SUPPORTER_USES_REMAINING_IN_TURN = "SUPPORTER_USES_REMAINING_IN_TURN"
    SWAP_REMAINING_IN_TURN = "SWAP_REMAINING_IN_TURN"
    ENERGY_ADD_REMAINING_IN_TURN = "ENERGY_ADD_REMAINING_IN_TURN"
    ATTACKS_LEFT = "ATTACKS_LEFT"

    #game specific
    KO_COUNT = "KO_COUNT"
    TOTAL_ENERGY_TOKENS = "TOTAL_ENERGY_TOKENS"

@dataclass
class EnergyToken():
    unique_id : str#energy tokens are instantiated in the beginning w/ unique_id's. they cannot be generated, but they can end up voided (by sending it to the Environment)
    holder : AVGEPlayer | AVGECharacterCard | AVGEEnvironment | None = None
    def attach(self, new_holder : AVGEPlayer | AVGECharacterCard | AVGEEnvironment):
        self.holder = new_holder
        self.holder.energy.append(self)
    def detach(self):
        old_holder = self.holder
        self.holder = None
        if(old_holder is not None):
            old_holder.energy.remove(self)
    def __eq__(self, other : object):
        return isinstance(other, EnergyToken) and self.unique_id == other.unique_id

class StatusChangeType(StrEnum):
    ADD = "ADD"#adds 1 status thing
    ERASE = "ERASE"#removes 1 status thing
    REMOVE = "REMOVE"#completely wipes the status

class PlayerID(StrEnum):
    P1 = 'p1'
    P2 = 'p2'
all_players : list[PlayerID] = [PlayerID.P1, PlayerID.P2]
class Pile(StrEnum):
    DECK = 'deck'
    HAND = 'hand'
    ACTIVE = 'active'
    DISCARD = 'discard'
    BENCH = 'bench'
    TOOL = 'tool'
    STADIUM = 'stadium'

class ActionTypes(StrEnum):
    ATK_1 = 'ATK_1'
    ACTIVATE_ABILITY = 'ACTIVATE_ABILITY'
    ATK_2 = "ATK_2"
    PASSIVE = "PASSIVE"#an action type exclusively used for stuff like follow-up atks
    SKIP = "SKIP"#an action type used when someone fucks up and has no energy for any attack going into the attack phase

    NONCHAR = 'NONCHAR'

    ENV = "ENV"
    PLAYER_CHOICE = "CHOICE"#exclusively for phase 2 and atk phase selection processes
class CardType(StrEnum):
    ALL = "ALL"#treat this as a sort of "true" element that has no resistance and can be used for all energy
    WOODWIND = "WW"
    PERCUSSION = "PERC"
    PIANO = "PIANO"
    STRING = "STRING"
    GUITAR = 'GUITAR'
    CHOIR = "CHOIR"
    BRASS = "BRASS"

class StatusEffect(StrEnum):
    ARRANGER = 'ARR'
    MAID = 'MAID'
    GOON = 'GOON'

class InputType(StrEnum):
    D6 = "D6"#response should be 1-6
    COIN = "COIN"#tails = 0, heads = 1. response can come in a list
    BINARY = "BINARY"#yes/no question
    SELECTION = "SELECTION"#selection btwn TARGETS_FLAG array.
    #should be structured like {QUERY_LABEL:___, 'allow_repeats': True(default False), 'allow_none': True(default False), TARGETS_FLAG: either a list of targets for all keys or each individual key gets a list}
    DETERMINISTIC = "DETERMINISTIC"#one-off character-specific deterministic/non-rng player choices. validation function should take in all results AT ONCE(list of results, with one slot per key)
type_weaknesses = {
    CardType.STRING: CardType.GUITAR,
    CardType.GUITAR: CardType.WOODWIND,
    CardType.WOODWIND: CardType.PERCUSSION,
    CardType.PERCUSSION: CardType.CHOIR,
    CardType.CHOIR : CardType.PIANO,
    CardType.PIANO : CardType.BRASS,
    CardType.BRASS: CardType.STRING
}
