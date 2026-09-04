from __future__ import annotations
from enum import Enum, StrEnum


# CONSTANTS
TOTAL_ENERGY_TOKENS = 100
CARDS_PER_DECK = 20
INITIAL_HAND_SIZE = 5
MAX_BENCH_SIZE = 5
KOS_TO_WIN = 3

PER_TURN_TOKEN_ADD = 1
PER_TURN_SUPPORTER_USE = 1
PER_TURN_SWAPS = 1
PER_TURN_ATKS = 1

default_timeout = 5


# CLASS DEFINITIONS

class EngineGroup(Enum):
    EXTERNAL_MODIFIERS_1 = 0  # used if you want something to come before internal prechecks
    INTERNAL_1 = 1  # all internal prechecks & the weaknesses are calculated in here
    EXTERNAL_PRECHECK_1 = 2
    EXTERNAL_MODIFIERS_2 = 3  # debuffs all go here
    EXTERNAL_MODIFIERS_3 = 4  # any
    EXTERNAL_PRECHECK_2 = 5
    INTERNAL_2 = 6  # i honestly don't think anything goes in here tbh
    CORE = 7
    INTERNAL_3 = 8
    EXTERNAL_REACTORS = 9
    INTERNAL_4 = 10

    def succ(self):
        v = self.value + 1
        return EngineGroup(v)


class ResponseStatus(Enum):
    SUCCESS = 0
    REGULATE_PASS = 1
    REGULATE_FAIL = 2
    REGULATE_IGNORE = 3
    REACTOR_SKIP = 4


class User(Enum):
    PLAYER_1 = 1
    PLAYER_2 = 2

    @property
    def next(self):
        members = list(self.__class__)
        index = members.index(self) + 1
        return members[index % len(members)]
    


class ID:
    pass


class ActionTypes(StrEnum):
    ATK_1 = 'ATK_1'
    ACTIVATE_ABILITY = 'ACTIVATE_ABILITY'
    ATK_2 = "ATK_2"
    PASSIVE = "PASSIVE"  # an action type exclusively used for stuff like follow-up atks
    SKIP = "SKIP"  # an action type used when someone fucks up and has no energy for any attack going into the attack phase

    NONCHAR = 'NONCHAR'

    ENV = "ENV"
    PLAYER_CHOICE = "CHOICE"  # exclusively for phase 2 and atk phase selection processes


class StatusEffect(StrEnum):
    ARRANGER = 'ARR'
    MAID = 'MAID'
    GOON = 'GOON'

class AVGEStatusModifier(StrEnum):
    ADD = 'add'
    REMOVE = 'remove'


class AVGEAttributeModifier(StrEnum):
    ADDITIVE = 'additive'
    SET_STATE = 'setstate'
    SUBSTRACTIVE = 'substractive'


class AVGEPlayerAttribute(StrEnum):

    # turn specific

    SUPPORTER_USES_REMAINING_IN_TURN = "SUPPORTER_USES_REMAINING_IN_TURN"
    SWAP_REMAINING_IN_TURN = "SWAP_REMAINING_IN_TURN"
    ENERGY_ADD_REMAINING_IN_TURN = "ENERGY_ADD_REMAINING_IN_TURN"
    ATTACKS_LEFT = "ATTACKS_LEFT"

    # game specific
    KO_COUNT = "KO_COUNT"
    TOTAL_ENERGY_TOKENS = "TOTAL_ENERGY_TOKENS"

class WinReasons(StrEnum):
    ALL_KOS = "ALL_KOS"
    KO_NO_DECK = "KO_NO_DECK"
