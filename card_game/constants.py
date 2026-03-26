from __future__ import annotations
from enum import Enum, StrEnum
from typing import Any, TYPE_CHECKING, Tuple
if TYPE_CHECKING:
    from card_game.engine.event import Event
    from card_game.engine.event_listener import AbstractEventListener
    from card_game.abstract.card import Card
type Data = dict[str, Any]

cards_per_deck = 30
initial_hand_size = 5
max_bench_size = 5
initial_tokens = 100
kos_to_win = 3

per_turn_token_add = 1
per_turn_supporter = 1
per_turn_swaps = 1
per_turn_atks = 1
class ResponseType(StrEnum):
    SKIP = "SKIP"
    ACCEPT = 'ACCEPT'
    REQUIRES_QUERY = "REQUIRES_QUERY"
    FINISHED = "FINISHED"
    FINISHED_PACKET = "FINISHED_PACKET"
    CORE = "CORE"

    NO_MORE_EVENTS = "NO_MORE_EVENTS"
    NEXT_EVENT = "NEXT_EVENT"
    NEXT_PACKET = 'NEXT_PACKET'
class Response():
    def __init__(self, 
                 source : Event | AbstractEventListener | Card | None,#None source reserved for very edge-case circumstances.
                 response_type : ResponseType = ResponseType.ACCEPT, 
                 data : Data | None = None,
                 announce : bool = False):
        self.response_type = response_type
        if(data is None):
            data = {}
        self.data = data
        self.source = source
        self.announce = announce

class AVGEAttributeModifier(StrEnum):
    ADDITIVE = 'additive'
    SET_STATE = 'setstate'
class AVGEPlayerAttribute(StrEnum):

    #turn specific
    
    SUPPORTER_USES_REMAINING_IN_TURN = "SUPPORTER_USES_REMAINING_IN_TURN"
    SWAP_REMAINING_IN_TURN = "SWAP_REMAINING_IN_TURN"
    ENERGY_ADD_REMAINING_IN_TURN = "ENERGY_ADD_REMAINING_IN_TURN"
    ATTACKS_LEFT = "ATTACKS_LEFT"

    #game specific
    KO_COUNT = "KO_COUNT"
    HAS_LOST = "HAS_LOST"
    TOTAL_ENERGY_TOKENS = "TOTAL_ENERGY_TOKENS"

class AVGECardAttribute(StrEnum):
    #character card attributes
    TYPE = "TYPE"
    HP = "HP"
    MAXHP = "MAXHP"
    SWITCH_COST = "SWITCH_COST"
    MV_1_COST = "MV_1_COST"
    MV_2_COST = "MV_2_COST"
    ENERGY_ATTACHED = "ENERGY_ATTACHED"
    STATUS_ATTACHED = "STATUS_ATTACHED"

class ChangeType(StrEnum):
    ADD = "ADD"
    REMOVE = "REMOVE"
class PlayerID(StrEnum):
    P1 = 'player1'
    P2 = 'player2'

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

    ENV = "ENV"
    PLAYER_CHOICE = "CHOICE"#exclusively for phase 2 and atk phase selection processes
class Type(StrEnum):
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

class RNGType(StrEnum):
    D6 = "D6"#response should be 1-6
    COIN = "COIN"#tails = 0, heads = 1. response can come in a list
type_weaknesses = {
    Type.STRING: Type.GUITAR,
    Type.GUITAR: Type.WOODWIND,
    Type.WOODWIND: Type.PERCUSSION,
    Type.PERCUSSION: Type.CHOIR,
    Type.CHOIR : Type.PIANO,
    Type.PIANO : Type.BRASS,
    Type.BRASS: Type.STRING
}
type_res = {
    Type.STRING: Type.PIANO,
    Type.PIANO: Type.PERCUSSION,
    Type.PERCUSSION: Type.GUITAR,
    Type.GUITAR: Type.BRASS,
    Type.BRASS: Type.CHOIR,
    Type.CHOIR: Type.WOODWIND,
    Type.WOODWIND: Type.STRING
}
