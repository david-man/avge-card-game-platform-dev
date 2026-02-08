#just some constants
from enum import Enum

cards_per_deck = 20
initial_hand_size = 5
max_hand_size = 5
initial_tokens = 100
kos_to_win = 2



class PlayerID(Enum):
    P1 = 0
    P2 = 1
class Pile(Enum):
    DECK = 0
    HAND = 1 
    ACTIVE = 2
    DISCARD = 3
    BENCH = 4

class QueryTypes(Enum):
    MAKE_ACTIVE = 0
    PHASE_2 = 1
    ITEM = 2
    TOOL = 3
    SUPPORTER = 4
    STADIUM = 5
    SWITCH = 6
    ADD_NRG = 7
    ATTACH_NRG = 8
    TO_BENCH = 9
    ATK = 10

class ActionTypes(Enum):
    ATK_1 = 0
    ACTIVATE_ABILITY = 1
    ATK_2 = 2
    PASSIVE = 3

class Trainer(Enum):
    ITEM = 0
    SUPPORTER = 1
    STADIUM = 2
    TOOL = 3

class Type(Enum):
    WOODWIND = 0
    PERCUSSION = 1
    PIANO = 2
    STRING = 3
    GUITAR = 4
    CHOIR = 5
    BRASS = 6
    ALL = 7

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


class Flow(Enum):
    #Phase 1: picking a card
    PRE_PICK_CARD = 0
    PICK_CARD = 1
    POST_PICK_CARD = 2

    #Phase 2: main phase: you can do the following

    #a: play a character from your hand to your bench
    PRE_PLAY_BENCH = 3
    PLAY_BENCH = 4
    POST_PLAY_BENCH = 5
    #b: attach energy to a character card on your bench or on your active 
    PRE_ATTACH_NRG = 6
    ATTACH_NRG = 7
    POST_ATTACH_NRG = 8
    #c: switch active character w/ bench character
    PRE_SWITCH = 9
    SWITCH = 10
    POST_SWITCH = 11
    #d: play an item
    PRE_PLAY_ITEM = 12
    PLAY_ITEM = 13
    POST_PLAY_ITEM = 14
    #e: play a stadium
    PRE_PLAY_STADIUM = 15
    PLAY_STADIUM = 16
    POST_PLAY_STADIUM = 17
    #f: play a supporter
    PRE_PLAY_SUPPORTER = 18
    PLAY_SUPPORTER = 19
    POST_PLAY_SUPPORTER = 20
    #g: play a tool
    PRE_PLAY_TOOL = 21
    PLAY_TOOL = 22
    POST_PLAY_TOOL = 23
    #h: add an energy token
    PRE_ADD_NRG_TOKEN = 24
    ADD_NRG_TOKEN = 25
    POST_ADD_NRG_TOKEN = 26

    #Phase 3: Attack
    PRE_ATTACK = 27
    ATTACK = 28
    POST_ATTACK = 29

    #Extra "phases" that I've added 
    PRE_TURN = 30#in this phase, you MUST do a KO check and immediately swap to SWITCH
    POST_TURN = 31#in this turn, you MUST do a KO check and immediately swap to SWITCH
    
    PRE_PHASE_TWO = 32
    PHASE_TWO = 33
    POST_PHASE_TWO = 34
    GENERIC_ATTACH = 35#a generic hook to hook onto if you want your ability to insta activate

class DamageFlow(Enum):
    #injection hooks specifically for damage buffing/nerfing
    PRE_DMG = 0
    POST_DMG = 1