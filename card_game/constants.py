from __future__ import annotations
from enum import Enum, StrEnum
from typing import Any
from .engine.engine_constants import Flag
Data = dict[str, Any]

cards_per_deck = 30
initial_hand_size = 5
max_bench_size = 5
initial_tokens = 100
kos_to_win = 3

per_turn_token_add = 1
per_turn_supporter = 1
per_turn_swaps = 1
class ResponseType(StrEnum):
    SKIP = "SKIP"
    ACCEPT = 'ACCEPT'
    REQUIRES_QUERY = "REQUIRES_QUERY"
    FINISHED = "FINISHED"
    CORE = "CORE"

    NO_MORE_EVENTS = "NO_MORE_EVENTS"
    NEXT_EVENT = "NEXT_EVENT"
    NEXT_PACKET = 'NEXT_PACKET'
class Response():
    import card_game.engine.event
    import card_game.engine.event_listener
    def __init__(self, 
                 source : card_game.engine.event.Event | card_game.engine.event_listener.AbstractEventListener | None,#None source reserved for very edge-case circumstances.
                 response_type : ResponseType = ResponseType.ACCEPT, 
                 data : Data = {},
                 announce : bool = False):
        self.response_type = response_type
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

    #game specific
    KO_COUNT = "KO_COUNT"
    HAS_LOST = "HAS_LOST"
    TOTAL_ENERGY_TOKENS = "TOTAL_ENERGY_TOKENS"

class AVGECardAttribute(StrEnum):
    #character card attributes
    TYPE = "TYPE"
    HP = "HP"
    SWITCH_COST = "SWITCH_COST"
    MV_1_COST = "MV_1_COST"
    MV_2_COST = "MV_2_COST"
    ENERGY_ATTACHED = "ENERGY_ATTACHED"
    STATUS_ATTACHED = "STATUS_ATTACHED"

class AVGEFlag(Flag):
    #a list of AVGE-specific event flags

    #the 3 phases
    PHASE_PICK_CARD = "PICK"#when you pick one card from the deck
    PHASE_2 = "P2"#when the player enters phase 2
    PHASE_ATK = "ATK"#when the player is given options to attack

    #flags for actions that actively do something(i.e, call a card to act)
    CARD_TRANSITION = "TRANSITION"#when a card transitions from A -> B
    CARD_ATTR_CHANGE = "CARD_ATTR"
    PLAYER_ATTR_CHANGE = "PLAYER_ATTR"
    PLAY_NONCHAR_CARD = "PLAY_NONCHAR"
    PLAY_CHAR_CARD = "PLAY_CHAR"

    TURN_BEGIN = "BEGIN"#when a player's turn begins
    TURN_END = "END"#when a player's turn ends 
    GAME_INIT = "INIT"#the first part of the game where players just pick up cards

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

class StatusEffect(Enum):
    #a status effect is just an effect that event listeners care about
    #only with an event listener do they actually do anything meaningful
    NONE = 0

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
