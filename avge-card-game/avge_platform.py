#this file details the foundation for the game
from __future__ import annotations
from typing import Callable
from generic_platform import *
from constants import *
import random


type FlowInjection = Callable[[AVGECharacterCard], None]
type DmgInjection = Callable[[AVGECharacterCard, Type, ActionTypes, int], int]
class AVGECharacterCard(GenericCard):
    #this is an abstract AVGE Character Card, so you need to override it!
    def __init__(self):
        super().__init__()
        self.energies_attached : dict[Type, int] = {}
        self.game_environment : 'AVGEEnvironment' = None
        self.cardholder : 'AVGECardholder' = None
        self.player : 'AVGEPlayer' = None
        self.cleanup_flag : bool = False#a flag that tells us if the card needs to be cleaned up or not
        #this dictionary maps each type of energy to how many of it the card is holding
        for type in Type:
            self.energies_attached[type] = 0

        #a damage injection is a special type of injection that injects itself
        #right before and right after a character card takes damage

        #it returns how much damage the card should take and if the card passive should be cleaned up after
        #it takes in the card itself, the attacking type, the type of attack, and the original damage number
        self.dmg_injections : dict[DamageFlow, dict[str, DmgInjection]] = {}
        for flow in DamageFlow:
            self.dmg_injections[flow] = {}
        #note that giving an attack_dmg to post_dmg WILL call damage twice

        #you need to override these when you make your card!
        self.type : Type = None
        self.max_hp : int= None 
        self.current_hp : int= None
        self.has_move_1 : bool= False
        self.has_move_2 : bool = False
        self.has_passive_ability : bool= False
        self.has_active_ability :bool = False
        self.switch_cost : int = None
        

   
    def __str__(self):
        return "AVGECard"

    def check(self):
        #basic check that things are initialized properly
        if(self.max_hp is None
           or self.current_hp is None
           or self.type is None):
            return False
        #each card should only get 2 things
        if(int(self.has_active_ability) + int(self.has_passive_ability)
           + int(self.has_move_1) + int(self.has_move_2) != 2):
            return False
        return True

    #The following functions are the ones that will have to be overwritten
    def can_swap(self) -> bool:
        #returns whether you have enough energy to swap off
        return False
    def consume_energy_and_swap(self) -> bool:
        #consumes energy on the swap. returns whether it succeeded
        #if we were still using energy types, we would have to query for this
        return False

    def move_one(self) -> bool:
        #plays move 1, returns success
        #DO NOT override if your card doesn't have this
        return False
    def can_play_move_1(self) -> bool:
        #returns whether you have enough energy to play move 1
        #DO NOT override if your card doesn't have this
        return False
    def move_two(self) -> bool:
        #plays move 2, returns success
        #DO NOT override if your card doesn't have this
        return False
    def can_play_move_2(self) -> bool:
        #returns whether you have enough energy to play move 2
        #DO NOT override if your card doesn't have this
        return False
    def active_ability(self) -> bool:
        #uses the active ability, returns success
        #DO NOT override if your card doesn't have this
        return False
    def passive(self) -> bool:
        #starts the passive, returns success
        #DO NOT override if your card doesn't have this
        return False
    def cleanup(self) -> bool:
        #cleans up
        #this function gets used before card is placed inside disposal pile
        return False
    
    #the following are helper functions, mostly called by the game environment

    #you probably don't need to touch these, but you can definitely use them!
    def damage(self, attacking_type : Type, attacking_dmg : int, action_type : ActionTypes) -> None:
        #applies damage to the card. PLEASE use this function to apply dmg(we have hooks!)
        for injection in self.dmg_injections[DamageFlow.PRE_DMG].values():
            #they can stack!
            attacking_dmg = injection(self, attacking_type, action_type, attacking_dmg)
        
        if(type_weaknesses[self.type] == attacking_type):
            attacking_dmg = attacking_dmg * 1.2
        elif(type_res[self.type] == attacking_type):
            attacking_dmg = attacking_dmg * 0.8
        self.current_hp -= int(attacking_dmg)
        for injection in self.dmg_injections[DamageFlow.POST_DMG].values():
            injection(self, attacking_type, action_type, attacking_dmg)
        return
        
    @override
    def play_card(self, args):
        action_type : ActionTypes = args[0]
        if(action_type == ActionTypes.ACTIVATE_ABILITY):
            if(not self.has_active_ability):
                raise Exception("Tried to activate an active ability that doesn't exist")
            return self.active_ability()
        if(action_type == ActionTypes.PASSIVE):
            if(not self.has_passive_ability):
                raise Exception("Tried to activate a passive that doesn't exist")
            print("ACTIVATING PASSIVE")
            return self.passive()
        if(action_type == ActionTypes.ATK_1):
            if(not self.has_move_1):
                raise Exception("Tried to use a move 1 that doesn't exist")
            return self.move_one()
        if(action_type == ActionTypes.ATK_2):
            if(not self.has_move_2):
                raise Exception("Tried to use a move 2 that doesn't exist")
            return self.move_two()
    def dmg_inject(self, card : AVGECharacterCard, phase : DamageFlow,
                   ability: DmgInjection) -> None:
        #injects an ability into a card's damage flow. only use this for abilities
        card.dmg_injections[phase][self.ingame_id] = ability
    def dmg_purify(self, card : AVGECharacterCard, phase : DamageFlow = None) -> None:
        #takes the ability out of the flow of a card's damage. 
        #specify phase if this card has injected in multiple areas
        if(phase is not None):
            if(self.ingame_id in card.dmg_injections[phase]):
                del card.dmg_injections[phase][self.ingame_id]
            else:
                raise Exception("Tried to purify an ability from a flow state, but card id was not found!")
        else:
            purified = False
            for _phase in Flow:
                if(self.ingame_id in card.dmg_injections[_phase]):
                    del card.dmg_injections[_phase][self.ingame_id]
                    purified = True
            if(not purified):
                raise Exception("Tried to purify an ability from a player's flow, but card id was not found!")
    
    def inject(self, player : 'AVGEPlayer', phase : Flow, 
               ability : FlowInjection) -> None:
        #injects an ability into the flow of a player's turn. only use this for abilities
        #this ability should be in the form of a lambda that takes in the player 
        #and does not return anything
        #note: a card should not place more than 1 injection in 1 flow state. 
        #i really would reconsider your card abilities if you think you need to do this

        player.flow_injections[phase][self.ingame_id] = ability

    def purify(self, player : 'AVGEPlayer', phase : Flow = None) -> None:
        #takes the ability out of the flow of a player's turn. 
        #specify phase if this card has injected in multiple areas
        if(phase is not None):
            if(self.ingame_id in player.flow_injections[phase]):
                del player.flow_injections[phase][self.ingame_id]
            else:
                raise Exception("Tried to purify an ability from a flow state, but ability uuid was not found!")
        else:
            purified = False
            for _phase in Flow:
                if(self.ingame_id in player.flow_injections[_phase]):
                    del player.flow_injections[_phase][self.ingame_id]
                    purified = True
            if(not purified):
                raise Exception("Tried to purify an ability from a player's flow, but ability uuid was not found!")
    
class AVGETrainerCard(GenericCard):
    def __init__(self, trainer_type : Trainer):
        super().__init__()
        self.trainer_type : Trainer = trainer_type
        self.game_environment : 'AVGEEnvironment' = None
        self.cardholder : 'AVGECardholder' = None
        self.player : 'AVGEPlayer' = None
    def check(self):
        return True

class AVGEEnergyCard(GenericCard):
    def __init__(self, energy_type : Type):
        super().__init__()
        self.energy_type : Type = energy_type
        self.game_environment : 'AVGEEnvironment' = None
        self.cardholder : 'AVGECardholder' = None
        self.player : 'AVGEPlayer' = None
    def check(self):
        return True

class AVGECardholder(GenericCardholder):#literally here just for typing hints
    def __init__(self):
        super().__init__()
        self.cards_holding : OrderedDict[Any, AVGECharacterCard | AVGEEnergyCard | AVGETrainerCard] = OrderedDict([])
        self.ingame_id : Any= None#id of the cardholder in the game environment
        self.player : 'AVGEPlayer' = None
        self.game_environment : 'AVGEEnvironment' = None

class AVGEPlayer(GenericPlayer):
    def __init__(self):
        super().__init__( False)
        self.game_environment : 'AVGEEnvironment' = None
        self.card_holders : dict[Pile, AVGECardholder] = {}
        self.flow_injections : dict[Flow, dict[str, FlowInjection]]= {}
        for flow in Flow:
            self.flow_injections[flow] = {}
        #this dictionary maps each phase of a player's turn to a list of injections
        #each injection is in a dictionary mapping the injector's uuid to the lambda

        self.turn_flow : list[Flow] = []
        #a stack representing what the next turns should be. 
        # ability cards can hijack it, but usually, it'll be single-element
        self.turn_flow.append(Flow.PRE_TURN)        

        #turn-specific attributes
        self.support_cards_remaining = 1#how many more support cards can this player use
        self.swaps_remaining = 1#how many more swaps can this player do
        self.energy_adds_remaining = 1#how many more energies can this player add in this turn
        
        #game-specific attributes
        self.has_lost = False#has the player lost (forcibly or via ff)
        self.energy_tokens_remaining = 0
        self.kos = 0


        self.active_ability_available = False#is the active ability ready for use?
        #note: because active abilities can be used at any time, the environment
        # not the player, will deal with calling it 
        #this is the same for forfeits


        #easy pointer to the opponent
        self.opponent : AVGEPlayer = None


        #card collections that the player has
        for col in [pile for pile in Pile]:
            self.register_cardholder(AVGECardholder(), col)
    def register_opponent(self, pointer : AVGEPlayer) -> None:
        #registers the opponent pointer
        self.opponent = pointer
        return
    def give_tokens(self, tokens : int):
        #gives energy tokens
        self.energy_tokens_remaining += tokens
    def turn_reset(self):
        #resets certain attributes after the turn is over
        self.turn_flow = []
        self.turn_flow.append(Flow.PRE_TURN)
        self.swaps_remaining = 1
        self.support_cards_remaining = 1
        self.energy_adds_remaining = 1

    @override
    def on_entry(self):
        #doesn't do anything because we need the entry to be injectible
        return super().on_entry()
    @override
    def on_exit(self):
        if(self.has_lost):
            self.game_environment.deactivate_player(self.ingame_id)

    def make_notif(self, string : str):
        self.game_environment.notify(self.ingame_id, [string])
    def make_query(self, query : QueryTypes):
        return self.game_environment.query(self.ingame_id, [query])
    @override
    def action(self, args) -> list:#returns a single element list detailing if the player's turn is over
        state_on : Flow= args[0]
        #first, validity checks of being in the state
        if(state_on == Flow.PRE_PLAY_SUPPORTER and self.support_cards_remaining <= 0):
            self.make_notif("Can't play more support cards!")
            self.turn_flow.append(Flow.PHASE_TWO)
            return [False]
        if(state_on == Flow.PRE_SWITCH and self.swaps_remaining <= 0):
            self.make_notif("Can't play more swaps!")
            self.turn_flow.append(Flow.PHASE_TWO)
            return [False]
        if(state_on == Flow.PRE_PLAY_BENCH and self.card_holders[Pile.BENCH].num_cards() == 3):
            self.make_notif("Already have 3 cards on bench!")
            return [False]
        if((state_on == Flow.PRE_ADD_NRG_TOKEN or state_on == Flow.PRE_ATTACH_NRG)
           and self.energy_adds_remaining <= 0):
            self.make_notif("Can't add more energy!")
            self.turn_flow.append(Flow.PHASE_TWO)
            return [False]
        
        #next, run all injections. injections should only be put in the PRE and POST turns
        for injection in self.flow_injections[state_on].values():
            injection(self)
        
        #now, deal with standard action events on each flow state
        match state_on:
            case Flow.POST_TURN:
                return [True]
            case Flow.GENERIC_ATTACH:
                if(len(self.turn_flow) == 0):
                    raise Exception("The generic attach flow state cannot be appended when there's no turns left!")
            case Flow.PRE_TURN:
                self.turn_flow.append(Flow.PRE_PICK_CARD)
            case Flow.PRE_PICK_CARD:
                self.turn_flow.append(Flow.PICK_CARD)
            case Flow.PICK_CARD:
                if(len(self.card_holders[Pile.DECK].cards_holding) == 0):
                    #if no cards in deck, insta lose
                    self.has_lost = True
                    self.turn_flow.append(Flow.POST_TURN)
                else:
                    #transfer card from deck to hand
                    top_card_id = self.card_holders[Pile.DECK].peek()[0]
                    transfer_card(top_card_id, self.card_holders[Pile.DECK], self.card_holders[Pile.HAND])
                    self.turn_flow.append(Flow.POST_PICK_CARD)

            case Flow.POST_PICK_CARD:
                self.turn_flow.append(Flow.PRE_PHASE_TWO)
            case Flow.PRE_PHASE_TWO:
                self.turn_flow.append(Flow.PHASE_TWO)
            case Flow.PHASE_TWO:
                #this state is basically just a multiplex
                q = self.make_query(QueryTypes.PHASE_2)
                if(q is None):
                    self.turn_flow.append(Flow.PHASE_TWO)
                    self.make_notif("Resetting due to quit")
                else:
                    next_action = q[0]#some query
                    match next_action:
                        case "item":
                            self.turn_flow.append(Flow.PRE_PLAY_ITEM)
                        case "switch":
                            self.turn_flow.append(Flow.PRE_SWITCH)
                        case "stadium":
                            self.turn_flow.append(Flow.PRE_PLAY_STADIUM)
                        case "supporter":
                            self.turn_flow.append(Flow.PRE_PLAY_SUPPORTER)
                        case "bench":
                            self.turn_flow.append(Flow.PRE_PLAY_BENCH)
                        case "tool":
                            self.turn_flow.append(Flow.PRE_PLAY_TOOL)
                        case "nrg_card":
                            self.turn_flow.append(Flow.PRE_ATTACH_NRG)
                        case "nrg_token":
                            self.turn_flow.append(Flow.PRE_ADD_NRG_TOKEN)#NOT IMPLEMENTED
                        case "atk":
                            self.turn_flow.append(Flow.PRE_ATTACK)
                        case _:
                            self.turn_flow.append(Flow.PHASE_TWO)
                            self.make_notif("Resetting due to invalid input")
            
            
            case Flow.PRE_PLAY_ITEM:
                self.turn_flow.append(Flow.PLAY_ITEM)
            case Flow.PRE_PLAY_TOOL:
                self.turn_flow.append(Flow.PLAY_TOOL)
            case Flow.PRE_PLAY_SUPPORTER:
                self.turn_flow.append(Flow.PLAY_SUPPORTER)
            case Flow.PRE_PLAY_STADIUM:
                self.turn_flow.append(Flow.PLAY_STADIUM)
            case Flow.PRE_SWITCH:
                self.turn_flow.append(Flow.SWITCH)
            case Flow.PRE_ATTACH_NRG:
                self.turn_flow.append(Flow.ATTACH_NRG)
            case Flow.PRE_ADD_NRG_TOKEN:
                self.turn_flow.append(Flow.ADD_NRG_TOKEN)
            case Flow.PRE_PLAY_BENCH:
                self.turn_flow.append(Flow.PLAY_BENCH)

            case Flow.POST_PLAY_ITEM | Flow.POST_PLAY_TOOL | Flow.POST_PLAY_STADIUM | Flow.POST_PLAY_BENCH:
                self.turn_flow.append(Flow.PHASE_TWO)
            case Flow.POST_ADD_NRG_TOKEN | Flow.POST_ATTACH_NRG:
                self.energy_adds_remaining -= 1
                self.turn_flow.append(Flow.PHASE_TWO)
            case Flow.POST_PLAY_SUPPORTER:
                self.swaps_remaining -= 1
                self.turn_flow.append(Flow.PHASE_TWO)
            case Flow.POST_SWITCH:
                self.swaps_remaining -= 1
                self.turn_flow.append(Flow.PHASE_TWO)

            case Flow.PLAY_ITEM:
                q = self.make_query(QueryTypes.ITEM)
                if(q is None):
                    self.turn_flow.append(Flow.PHASE_TWO)
                    self.make_notif("Resetting due to quit")
                else:
                    item_id : str = q[0]
                    if(not self.card_holders[Pile.HAND].has_card(item_id)):
                        self.make_notif("No such card id exists in player hand! Try again!")
                        self.turn_flow.append(Flow.PHASE_TWO)
                    else:
                        card : AVGETrainerCard = self.card_holders[Pile.HAND].get_card(item_id)
                        if(not isinstance(card, AVGETrainerCard) or card.trainer_type != Trainer.ITEM):
                            self.make_notif(f"Wrong type: wanted item!")
                            self.turn_flow.append(Flow.PHASE_TWO)
                        else:
                            #use item, discard it
                            card.play_card([])
                            transfer_card(card.ingame_id, self.card_holders[Pile.HAND], self.card_holders[Pile.DISCARD])
                            self.turn_flow.append(Flow.POST_PLAY_ITEM)
            case Flow.PLAY_TOOL:
                q = self.make_query(QueryTypes.TOOL)
                if(q is None):
                    self.turn_flow.append(Flow.PHASE_TWO)
                    self.make_notif("Resetting due to quit")
                else:
                    item_id : str = q[0]
                    if(not self.card_holders[Pile.HAND].has_card(item_id)):
                        self.make_notif("No such card id exists in player hand! Try again!")
                        self.turn_flow.append(Flow.PHASE_TWO)
                    else:
                        card : AVGETrainerCard = self.card_holders[Pile.HAND].get_card(item_id)
                        if(not isinstance(card, AVGETrainerCard) or card.trainer_type != Trainer.TOOL):
                            self.make_notif(f"Wrong type: wanted tool!")
                            self.turn_flow.append(Flow.PHASE_TWO)
                        else:
                            #use tool, discard it
                            card.play_card([])
                            self.turn_flow.append(Flow.POST_PLAY_TOOL)
            case Flow.PLAY_SUPPORTER:
                q = self.make_query(QueryTypes.SUPPORTER)
                if(q is None):
                    self.turn_flow.append(Flow.PHASE_TWO)
                    self.make_notif("Returning due to quit")
                else:
                    item_id : str = q[0]
                    if(not self.card_holders[Pile.HAND].has_card(item_id)):
                        self.make_notif("No such card id exists in player hand! Try again!")
                        self.turn_flow.append(Flow.PHASE_TWO)
                    else:
                        card : AVGETrainerCard = self.card_holders[Pile.HAND].get_card(item_id)
                        if(not isinstance(card, AVGETrainerCard) or card.trainer_type != Trainer.SUPPORTER):
                            self.make_notif(f"Wrong type: wanted supporter!")
                            self.turn_flow.append(Flow.PHASE_TWO)
                        else:
                            #use supporter, discard it
                            card.play_card([])
                            self.turn_flow.append(Flow.POST_PLAY_SUPPORTER)
            case Flow.PLAY_STADIUM:
                q = self.make_query(QueryTypes.STADIUM)
                if(q is None):
                    self.turn_flow.append(Flow.PHASE_TWO)
                    self.make_notif("Returning due to quit")
                else:
                    item_id : str = q[0]
                    if(not self.card_holders[Pile.HAND].has_card(item_id)):
                        self.make_notif("No such card id exists in player hand! Try again!")
                        self.turn_flow.append(Flow.PHASE_TWO)
                    else:
                        card : AVGETrainerCard = self.card_holders[Pile.HAND].get_card(item_id)
                        if(not isinstance(card, AVGETrainerCard) or card.trainer_type != Trainer.STADIUM):
                            self.make_notif(f"Wrong type: wanted stadium!")
                            self.turn_flow.append(Flow.PHASE_TWO)
                        else:
                            #swap the stadium out
                            self.game_environment._swap_stadium(card)
                            self.turn_flow.append(Flow.POST_PLAY_STADIUM)
            case Flow.SWITCH:
                q = self.make_query(QueryTypes.SWITCH)
                if(q is None):
                    self.turn_flow.append(Flow.PHASE_TWO)
                    self.make_notif("Resetting due to quit")
                else:
                    char_id : str = q[0]
                    if(not self.card_holders[Pile.BENCH].has_card(char_id)):
                        self.make_notif("No such card id exists in player bench! Try again!")
                        self.turn_flow.append(Flow.PHASE_TWO)
                    else:
                        card : AVGECharacterCard = self.card_holders[Pile.BENCH].get_card(char_id)
                        if(not isinstance(card, AVGECharacterCard)):
                            self.make_notif(f"Wrong type: can only swap with characters")
                            self.turn_flow.append(Flow.PHASE_TWO)
                        else:
                            #get the current active card, transfer back to bench
                            current_active_card : AVGECharacterCard = self.game_environment.get_active_card(self.ingame_id)
                            transfer_card(current_active_card.ingame_id, self.card_holders[Pile.ACTIVE], self.card_holders[Pile.BENCH])
                            #transfer the card asked for to the active slot
                            transfer_card(card.ingame_id, self.card_holders[Pile.BENCH], self.card_holders[Pile.ACTIVE])
                            self.turn_flow.append(Flow.POST_SWITCH)
            case Flow.ADD_NRG_TOKEN:
                q = self.make_query(QueryTypes.ADD_NRG)
                if(q is None):
                    self.turn_flow.append(Flow.PHASE_TWO)
                    self.make_notif("Resetting due to quit")
                else:

                    char_id = q[0]
                    if(not(self.card_holders[Pile.BENCH].has_card(char_id)) and not(self.card_holders[Pile.ACTIVE].has_card(char_id))):
                        self.make_notif("No such card id exists in player bench or player active slot! Try again!")
                        self.turn_flow.append(Flow.PHASE_TWO)
                    else:
                        char_card : AVGECharacterCard = None
                        if(self.card_holders[Pile.BENCH].has_card(char_id)):
                            char_card = self.card_holders[Pile.BENCH].get_card(char_id)
                        elif(self.card_holders[Pile.ACTIVE].has_card(char_id)):
                            char_card = self.card_holders[Pile.ACTIVE].get_card(char_id)
                        char_card.energies_attached[Type.ALL] += 1
                        self.energy_adds_remaining -= 1
                        self.turn_flow.append(Flow.PHASE_TWO)
            case Flow.ATTACH_NRG:
                q = self.make_query(QueryTypes.ATTACH_NRG)
                if(q is None):
                    self.turn_flow.append(Flow.PHASE_TWO)
                    self.make_notif("Resetting due to quit")
                else:
                    char_id = q[0]
                    item_id = q[1]
                    if(not self.card_holders[Pile.HAND].has_card(item_id)
                        or (not self.card_holders[Pile.BENCH].has_card(char_id)
                            and not self.card_holders[Pile.ACTIVE].has_card(char_id))):
                        self.make_notif("1+ cards aren't in the right slot! Try again.")
                        self.turn_flow.append(Flow.PHASE_TWO)
                    else:
                        char_card : AVGECharacterCard = None
                        if(self.card_holders[Pile.BENCH].has_card(char_id)):
                            char_card = self.card_holders[Pile.BENCH].get_card(char_id)
                        elif(self.card_holders[Pile.ACTIVE].has_card(char_id)):
                            char_card = self.card_holders[Pile.ACTIVE].get_card(char_id)
                        nrg_card : AVGEEnergyCard = self.card_holders[Pile.HAND].get_card(item_id)
                        if(not isinstance(char_card, AVGECharacterCard)):
                            self.make_notif(f"Wrong type: can only give characters energy")
                            self.turn_flow.append(Flow.PHASE_TWO)
                        elif(not isinstance(nrg_card, AVGEEnergyCard)):
                            self.make_notif(f"Wrong type of energy card(?!!)")
                            self.turn_flow.append(Flow.PHASE_TWO)
                        else:
                            char_card.energies_attached[nrg_card.energy_type] += 1
                            self.turn_flow.append(Flow.PHASE_TWO)
            case Flow.PLAY_BENCH:
                q = self.make_query(QueryTypes.TO_BENCH)
                if(q is None):
                    self.turn_flow.append(Flow.PHASE_TWO)
                    self.make_notif("Resetting due to quit")
                else:
                    char_id = q[0]
                    if(not self.card_holders[Pile.HAND].has_card(char_id)):
                        self.make_notif("No such card id exists in player hand! Try again!")
                        self.turn_flow.append(Flow.PHASE_TWO)
                    else:
                        card : AVGECharacterCard = self.card_holders[Pile.HAND].get_card(char_id)
                        if(not isinstance(card, AVGECharacterCard)):
                            self.make_notif(f"Wrong type: can only place characters on bench!")
                            self.turn_flow.append(Flow.PHASE_TWO)
                        else:
                            #transfer hand -> bench
                            transfer_card(card.ingame_id, self.card_holders[Pile.HAND], self.card_holders[Pile.BENCH])
                            if(card.has_passive_ability):
                                card.play_card([ActionTypes.PASSIVE])#insta play ability
                            self.turn_flow.append(Flow.POST_PLAY_BENCH)
            
            #out of phase 2
            case Flow.PRE_ATTACK:
                self.turn_flow.append(Flow.ATTACK)
            case Flow.ATTACK:
                if(self.card_holders[Pile.ACTIVE].num_cards() != 1):
                    raise Exception("yeah so wtaf")
                active_card : AVGECharacterCard = None
                _, active_card = self.card_holders[Pile.ACTIVE].peek()
                if(not active_card.can_play_move_1() and (not active_card.can_play_move_2())):
                    self.make_notif("No attacks can be made! Moving on...")
                    self.turn_flow.append(Flow.POST_ATTACK)
                    return [False]
                q = self.make_query(QueryTypes.ATK)
                if(q is None):
                    self.make_notif("ATK Failed!")
                    self.turn_flow.append(Flow.ATTACK)
                else:
                    atk : str = q[0]
                    if(atk == 'mv_1'):
                        if(not active_card.has_move_1):
                            self.make_notif("Tried to use move 1 when it doesn't exist!")
                            self.turn_flow.append(Flow.ATTACK)
                        elif(not active_card.can_play_move_1()):
                            self.make_notif("Tried to use move 2 when it can't be played!")
                            self.turn_flow.append(Flow.ATTACK)
                        else:
                            if(not active_card.play_card([ActionTypes.ATK_1])):
                                self.make_notif("ATK 1 Failed!")
                                self.turn_flow.append(Flow.ATTACK)
                            else:
                                print("ATK 1 Succeeded")
                                self.turn_flow.append(Flow.POST_ATTACK)
                    elif(atk == 'mv_2'):
                        if(not active_card.has_move_2):
                            self.make_notif("Tried to use move 2 when it doesn't exist!")
                            self.turn_flow.append(Flow.ATTACK)
                        elif(not active_card.can_play_move_2()):
                            self.make_notif("Tried to use move 2 when it can't be played!")
                            self.turn_flow.append(Flow.ATTACK)
                        else:
                            if(not active_card.play_card([ActionTypes.ATK_2])):
                                self.make_notif("ATK 2 Failed!")
                                self.turn_flow.append(Flow.ATTACK)
                            else:
                                print("ATK 2 Succeeded")
                                self.turn_flow.append(Flow.POST_ATTACK)
                    else:
                        self.make_notif("ATK Failed!")
                        self.turn_flow.append(Flow.ATTACK)
            case Flow.POST_ATTACK:
                self.turn_flow.append(Flow.POST_TURN)
        return [False]        
    
class AVGEEnvironment(GameEnvironment):
    def __init__(self):
        super().__init__()
        self.players : dict[PlayerID, AVGEPlayer] = {}
        #adds both players(p1, p2)
        player_one : AVGEPlayer = AVGEPlayer()
        player_two : AVGEPlayer = AVGEPlayer()
        self.register_new_player(player_one, PlayerID.P1, True)
        self.register_new_player(player_two, PlayerID.P2, True)
        player_one.register_opponent(player_two)
        player_two.register_opponent(player_one)

        #randomly establish order
        if(random.random() < 0.5):
            self.establish_order([PlayerID.P1, PlayerID.P2])
        else:
            self.establish_order([PlayerID.P2, PlayerID.P1])
        
        self.stadium_owner_id : str = None
        self.stadium : AVGETrainerCard = None
        self.counter : int = 0#literally just an id thing
    
    @override
    def notify(self, player_id: Any, notif : list = []):
        print(f"Notification for Player: {str(player_id)}")
        print(notif[0])

    @override
    def query(self, player_id : Any, query : list = []):
        print("---------------------------")
        print(f"Player: {str(player_id)}")
        match query[0]:
            case QueryTypes.MAKE_ACTIVE:
                print("You have no active card. Please select one from your hand / bench:")
                for card in self.players[player_id].card_holders[Pile.HAND].get_cards():
                    print(str(card))
                for card in self.players[player_id].card_holders[Pile.BENCH].get_cards():
                    print(str(card))
            case QueryTypes.PHASE_2:
                print("Main phase:")
                print("Active card: ", str(self.get_active_card(player_id)))
                print("Benched cards: ", [str(card) for card in self.players[player_id].card_holders[Pile.BENCH].get_cards()])
                print("")
                print("Cards in hand: ", [str(card) for card in self.players[player_id].card_holders[Pile.HAND].get_cards()])
                print("")
                print(f"Supporter cards remaining: {self.players[player_id].support_cards_remaining}")
                print(f"Energy attachments remaining: {self.players[player_id].energy_adds_remaining}")
                print(f"Swaps remaining: {self.players[player_id].swaps_remaining}")
                print("Please choose an action among: [item, switch, stadium, supporter, bench, tool, nrg_token, atk].")
            case QueryTypes.ITEM:
                print("Which item card would you like to use?(q to go back)")
                for card in self.players[player_id].card_holders[Pile.HAND].get_cards():
                    if(isinstance(card, AVGETrainerCard) and card.trainer_type == Trainer.ITEM):
                        print(str(card))
            case QueryTypes.TOOL:
                print("Which tool would you like to use?(q to go back)")
                for card in self.players[player_id].card_holders[Pile.HAND].get_cards():
                    if(isinstance(card, AVGETrainerCard) and card.trainer_type == Trainer.ITEM):
                        print(str(card))
            case QueryTypes.SUPPORTER:
                if(self.players[player_id].support_cards_remaining < 1):
                    print("No more supporter cards left! Please try another action")
                    return None
                else:
                    print("Which stadium would you like to use?(q to go back)")
                    for card in self.players[player_id].card_holders[Pile.HAND].get_cards():
                        if(isinstance(card, AVGETrainerCard) and card.trainer_type == Trainer.SUPPORTER):
                            print(str(card))
            case QueryTypes.STADIUM:
                print("Which stadium would you like to use?(q to go back)")
                for card in self.players[player_id].card_holders[Pile.HAND].get_cards():
                    if(isinstance(card, AVGETrainerCard) and card.trainer_type == Trainer.STADIUM):
                        print(str(card))
            case QueryTypes.SWITCH:
                if(self.players[player_id].swaps_remaining < 1):
                    print("No more swaps left! Please try another action\n")
                    return None
                elif(not self.get_active_card(player_id).can_swap()):
                    print("Not enough energy to swap! Please try another action\n")
                    return None
                else:
                    print("Which character would you like to swap on?(q to go back)")
                    for card in self.players[player_id].card_holders[Pile.BENCH].get_cards():
                        if(isinstance(card, AVGECharacterCard)):
                            print(str(card))
            case QueryTypes.ADD_NRG:
                if(self.players[player_id].energy_tokens_remaining <= 0):
                    print("No more energy tokens!")
                    return None
                elif(self.players[player_id].energy_adds_remaining <= 0):
                    print("No more energy adds left")
                    return None
                else:
                    print("Which card would you like to give energy to?(q to go back)")
                    print(self.get_active_card(player_id))
                    for card in self.players[player_id].card_holders[Pile.BENCH].get_cards():
                        if(isinstance(card, AVGECharacterCard)):
                            print(str(card))
            case QueryTypes.ATTACH_NRG:
                pass
            case QueryTypes.TO_BENCH:
                print("Which card would you like to move from your hand to the bench?(q to go back)")
                print(self.get_active_card(player_id))
                print(player_id)
                for card in self.players[player_id].card_holders[Pile.HAND].get_cards():
                    if(isinstance(card, AVGECharacterCard)):
                        print(str(card))
            case QueryTypes.ATK:
                active_card = self.get_active_card(player_id)
                print("Which attack would you like to use?(q to go back)")
                if(active_card.can_play_move_1()):
                    print("mv_1")
                if(active_card.can_play_move_2()):
                    print("mv_2")
        s = input("Input: ")
        print("---------------------------")
        if(s == "q"):
            return None
        return s.split(" ")
    def make_active(self, player : PlayerID) -> bool:
        #tries to query a player to pick a card from their hand or bench to be active
        #returns false if they do, true if they don't
        if(self.has_active_card(player)):
            raise Exception('tried to make player pick a card when one is already active')
        card_id = self.query(player, [QueryTypes.MAKE_ACTIVE])[0]
        if(card_id is None):
            return False
        else:
            if(not self.players[player].card_holders[Pile.HAND].has_card(card_id)
               and not self.players[player].card_holders[Pile.BENCH].has_card(card_id)):
                return False
            else:
                if(self.players[player].card_holders[Pile.HAND].has_card(card_id)):
                    card : AVGECharacterCard = self.players[player].card_holders[Pile.HAND].get_card(card_id)
                    if(not isinstance(card, AVGECharacterCard)):
                        return False
                    if(card.has_passive_ability):
                        card.play_card([ActionTypes.PASSIVE])
                    transfer_card(card_id, self.players[player].card_holders[Pile.HAND],
                                self.players[player].card_holders[Pile.ACTIVE])
                    return True
                else:
                    card : AVGECharacterCard = self.players[player].card_holders[Pile.BENCH].get_card(card_id)
                    if(not isinstance(card, AVGECharacterCard)):
                        return False
                    if(card.has_passive_ability):
                        card.play_card([ActionTypes.PASSIVE])
                    transfer_card(card_id, self.players[player].card_holders[Pile.BENCH],
                                  self.players[player].card_holders[Pile.ACTIVE])
                    return True
    def has_active_card(self, player : PlayerID) -> bool:
        #returns whether a player has an active card on field
        return len(self.players[player].card_holders[Pile.ACTIVE].cards_holding.values()) > 0
    def get_active_card(self, player : PlayerID) -> AVGECharacterCard:
        #gets the active card of a player, assuming one is present
        return next(iter(self.players[player].card_holders[Pile.ACTIVE].cards_holding.values()))
    
    def initialize_player(self, deck : list[GenericCard], player_id : PlayerID):
        #adds a list of cards to the deck. then, gives player hand some of them
        if(len(deck) != cards_per_deck):
            raise Exception("deck invalid")
        if(player_id not in self.players):
            raise Exception("player invalid")
        #any other conditions on cards go under
        for card in deck:
            if(not card.check()):
                raise Exception("card invalid")
            #i gave up making good uuids ima be deadass. 
            self.players[player_id].card_holders[Pile.DECK].register_card(card, card_id = f"card_{str(self.counter)}")
            self.counter+=1
        self.players[player_id].card_holders[Pile.DECK].shuffle()
        characters = 0
        card_ids = []
        for _ in range(initial_hand_size):
            card_id, card = self.players[player_id].card_holders[Pile.DECK].peek()
            transfer_card(card_id, self.players[player_id].card_holders[Pile.DECK],
                              self.players[player_id].card_holders[Pile.HAND])
            if(isinstance(card, AVGECharacterCard)):
                characters += 1
            card_ids.append(card_id)
        if(characters > 0):
            #gives them energy tokens to start off with
            self.players[player_id].give_tokens(initial_tokens)
            active_card_placed = False
            while(not active_card_placed):#now try to get them to put a char card as active
                active_card_placed = self.make_active(player_id)
            return    
        else:
            for cid in card_ids:
                self.players[player_id].card_holders[Pile.HAND].remove_card(cid)
            
            #if failed, try again(mulligan)
            self.initialize_player(deck, player_id)

    def _swap_stadium(self, new_stadium :AVGETrainerCard):
        if(new_stadium.trainer_type != Trainer.STADIUM or
        not new_stadium.player.card_holders[Pile.HAND].has_card(new_stadium.ingame_id)):
            raise Exception("bruh")
        else:
            if(self.stadium is not None):
                self.players[self.stadium_owner_id].card_holders[Pile.DISCARD].register_card(
                    self.stadium, card_id = self.stadium.ingame_id
                )
            self.stadium_owner_id = new_stadium.player.ingame_id
            self.stadium = new_stadium
            self.players[self.stadium_owner_id].card_holders[Pile.HAND].remove_card(self.stadium.ingame_id)
    
    def winner_protocol(self):
        if(self.num_players == 1):
            print("Player ", self.winner_flag, " won!")
        else:
            print("Tie! (miraculous god damn)")

    def check_hp(self) -> bool:
        #helper function that simply runs through all players to check their character hp's
        #returns true if it believes the game should end
        to_ret = False
        for player_id in self.players.keys():   
            active_card = self.get_active_card(player_id)
            cards = self.players[player_id].card_holders[Pile.BENCH].get_cards() + [active_card]
            for card in cards:
                if(isinstance(card, AVGECharacterCard)):
                    if(card.current_hp <= 0):
                    #move it to discard pile if card on <=0 hp
                        if(card.ingame_id == active_card.ingame_id):
                            
                            transfer_card(card.ingame_id, self.players[player_id].card_holders[Pile.ACTIVE],
                                        self.players[player_id].card_holders[Pile.DISCARD])
                        else:
                            transfer_card(card.ingame_id, self.players[player_id].card_holders[Pile.BENCH],
                                        self.players[player_id].card_holders[Pile.DISCARD])
                        if(not card.cleanup()):#try to perform a card cleanup
                            raise Exception("Cleanup failed!")
                        else:
                            card.cleanup_flag = False#performed the cleanup, no longer needs to
                        #increment ko's for the other player
                        self.players[self.players[player_id].opponent.ingame_id].kos += 1
            #check both player's kos for win conditions
            if(self.players[PlayerID.P1].kos >= kos_to_win):
                self.deactivate_player(PlayerID.P2)
                self.players[PlayerID.P2].has_lost = True
                to_ret = True
            elif(self.players[PlayerID.P2].kos >= kos_to_win):
                self.deactivate_player(PlayerID.P1)
                self.players[PlayerID.P1].has_lost = True
                to_ret = True
            else:
                #if a player doesn't have an active card, make them try to pick
                if(not self.winner_flag and not self.has_active_card(player_id)):# if not
                    succeeded = self.make_active(player_id)
                    if(not succeeded):
                        #if they have a dead active char and can't pick a new card, they lose
                        self.deactivate_player(player_id)
                        self.players[player_id].has_lost = True
                        to_ret = True
            return to_ret
    def check_cleanups(self) -> bool:
        for player_id in self.players.keys():   
            active_card = self.get_active_card(player_id)
            cards = self.players[player_id].card_holders[Pile.BENCH].get_cards() + [active_card]
            for card in cards:
                if(isinstance(card, AVGECharacterCard)):
                    if(card.cleanup_flag):
                        if(not card.cleanup()):
                            raise Exception("Cleanup failed!")
                        else:
                            card.cleanup_flag = False#performed cleanup, can move on now
        return True
    def run(self) -> bool:
        #runs the game
        while(self.winner_flag is None):
            current_turn : PlayerID = self.cardholder_turn
            current_player : AVGEPlayer = self.players[current_turn]
            current_player.turn_reset()#perform turn reset before the player's flow begins
            while(len(current_player.turn_flow) > 0):
                next_turn = current_player.turn_flow.pop()
                print(next_turn)
                end_of_turn = current_player.action([next_turn])[0]
                #after each action, clean up, and then
                # check through all player's bench and active slot for dead characters
                
                self.check_cleanups()
                end_of_game = self.check_hp()
                
                if(end_of_game or end_of_turn):
                    break
            if(self.winner_flag is None):
                self.next_turn()
        self.winner_protocol()
