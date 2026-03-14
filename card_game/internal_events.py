from __future__ import annotations
from .avge_abstracts.AVGEEvent import *
from .avge_abstracts.AVGECards import *
from .avge_abstracts.AVGEPlayer import *
from .avge_abstracts.AVGEEnvironment import AVGEEnvironment
from .avge_abstracts.AVGECardholder import AVGEStadiumCardholder, AVGEToolCardholder
from .constants import *
from copy import deepcopy
class AVGECardAttributeChange(AVGEEvent):
    def __init__(self, 
                 target_card : AVGECharacterCard,
                 attribute : AVGECardAttribute,
                 change_amount : int,
                 attribute_modifier_type : AVGEAttributeModifier,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None,
                 change_type : Type = None):
        super().__init__([AVGEFlag.CARD_ATTR_CHANGE], catalyst_action,caller_card)
        self.change_amount = change_amount
        self.attribute = attribute
        self.target_card = target_card
        self.change_type = change_type
        self.attribute_modifier_type = attribute_modifier_type
        self.old_amt = None
    
    def make_announcement(self):
        return True
    
    def core(self, args :Data = {}) -> Response:
        self.old_amt = self.target_card.attributes[self.attribute]
        if(self.attribute_modifier_type == AVGEAttributeModifier.ADDITIVE):
            self.target_card.attributes[self.attribute] += self.change_amount
        else:
            self.target_card.attributes[self.attribute] = self.change_amount
        return self.generate_core_response()
    
    def invert_core(self, args : Data = {}):
        self.target_card.attributes[self.attribute] = self.old_amt

    def generate_internal_listeners(self):
        from .internal_listeners import AVGECardAttributeChangeAssessment, AVGECardAttributeChangePostCheck, AVGECardAttributeChangeReactor, AVGECardAttributeChangeModifier
        self.attach_listener(AVGECardAttributeChangeAssessment())
        self.attach_listener(AVGECardAttributeChangeModifier())
        self.attach_listener(AVGECardAttributeChangeReactor())#this needs to go first!
        self.attach_listener(AVGECardAttributeChangePostCheck())
    
    def package(self):
        return f"{self.attribute_modifier_type} AVGECardAttributeChange on {self.target_card} for {self.attribute} of {self.change_amount}"
    

class AVGEPlayerAttributeChange(AVGEEvent):
    def __init__(self, 
                 target_player : AVGEPlayer,
                 attribute : AVGEPlayerAttribute,
                 change_amount : int,
                 attribute_modifier_type : AVGEAttributeModifier,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__([AVGEFlag.CARD_ATTR_CHANGE], catalyst_action,caller_card)
        self.change_amount = change_amount
        self.attribute = attribute
        self.target_player = target_player
        self.attribute_modifier_type = attribute_modifier_type
        self.old_amt = None
    
    def make_announcement(self):
        return True
    
    def core(self, args :Data = {}) -> Response:
        self.old_amt = self.target_player.attributes[self.attribute]
        if(self.attribute_modifier_type == AVGEAttributeModifier.ADDITIVE):
            self.target_player.attributes[self.attribute] += self.change_amount
        else:
            self.target_player.attributes[self.attribute] = self.change_amount
        return self.generate_core_response()
    
    def invert_core(self, args : Data = {}):
        self.target_player.attributes[self.attribute] = self.old_amt

    def generate_internal_listeners(self):
        from .internal_listeners import AVGEPlayerAttributeChangeModifier, AVGEPlayerAttributeChangePostChecker
        self.attach_listener(AVGEPlayerAttributeChangeModifier())
        self.attach_listener(AVGEPlayerAttributeChangePostChecker())
    
    def package(self):
        return f"{self.attribute_modifier_type} AVGECardAttributeChange on {self.target_player} for {self.attribute} of {self.change_amount}"
    
class TransferCard(AVGEEvent):
    def __init__(self, 
                 card : Card,
                 pile_to : AVGECardholder,
                 pile_from : AVGECardholder,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__([AVGEFlag.CARD_ATTR_CHANGE], catalyst_action,caller_card)
        self.card = card
        self.pile_to = pile_to
        self.pile_from = pile_from
    
    def make_announcement(self):
        return True
    
    def core(self, args :Data = {}) -> Response:
        if(isinstance(self.card, AVGEToolCard) and isinstance(self.pile_from, AVGEToolCardholder)):
            self.card.card_attached = self.pile_from.parent_card
        elif(isinstance(self.card, AVGEStadiumCard) and isinstance(self.pile_from, AVGEStadiumCardholder)):
            self.card.is_active = True
        self.card.env.transfer_card(self.card, self.pile_to, self.pile_from)
        return self.generate_core_response()
    
    def invert_core(self, args : Data = {}):
        if(isinstance(self.card, AVGEToolCard) and isinstance(self.pile_from, AVGEToolCardholder)):
            self.card.card_attached = None
        elif(isinstance(self.card, AVGEStadiumCard) and isinstance(self.pile_from, AVGEStadiumCardholder)):
            self.card.is_active = False
        self.card.env.transfer_card(self.card, self.pile_from, self.pile_to)

    def generate_internal_listeners(self):
        from .internal_listeners import AVGETransferValidityCheck
        self.attach_listener(AVGETransferValidityCheck())
    
    def package(self):
        return f"{self.card} from {self.pile_from} to {self.pile_to}"
    
class PlayCharacterCard(AVGEEvent):
    def __init__(self, 
                 card : AVGECharacterCard,
                 card_action : ActionTypes,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__([AVGEFlag.PLAY_CHAR_CARD], catalyst_action,caller_card)
        self.card = card
        self.card_action = card_action
        self.cache_snapshot = None
    def core(self, args : Data = {}) -> Response:
        self.cache_snapshot = deepcopy(self.card.data_cache)
        if(self.card_action == ActionTypes.SKIP):
            return self.generate_core_response()
        else:
            args['type'] = self.card_action
            if(self.card.play_card(args)):
                return self.generate_core_response()
            else:
                return self.generate_core_response(ResponseType.REQUIRES_QUERY)
    def invert_core(self, args : Data = {}):
        #since a card can only propose events and add event listeners, the only thing to invert is the cache
        self.card.data_cache = self.cache_snapshot
        return
    def make_announcement(self):
        return True
    def generate_internal_listeners(self):
        from .internal_listeners import AVGEPlayCharacterCardValidityCheck
        self.attach_listener(AVGEPlayCharacterCardValidityCheck())
    def package(self):
        return f"{self.card_action} action from {self.card}"
    
class PlayNonCharacterCard(AVGEEvent):
    def __init__(self, 
                 card : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__([AVGEFlag.PLAY_NONCHAR_CARD], catalyst_action,caller_card)
        self.card = card
    def core(self, args : Data = {}) -> Response:
        self.cache_snapshot = deepcopy(self.card.data_cache)
        return self.card.play_card(args)
    def invert_core(self, args : Data = {}):
        self.card.data_cache = self.cache_snapshot
        return
    def make_announcement(self):
        return True
    def generate_internal_listeners(self):
        from .internal_listeners import AVGEPlayNonCharacterCardValidityCheck
        self.attach_listener(AVGEPlayNonCharacterCardValidityCheck())
    def package(self):
        return f"{self.card} was played!"

class PhasePickCard(AVGEEvent):
    def __init__(self, 
                 player : AVGEPlayer,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__([AVGEFlag.PHASE_PICK_CARD], catalyst_action,caller_card)
        self.player = player
    def core(self, args : Data = {}) -> Response:
        if(len(self.player.cardholders[Pile.DECK]) > 0):
            deck = self.player.cardholders[Pile.DECK]
            hand = self.player.cardholders[Pile.HAND]
            top_card = deck.peek_n(1)
            self.player.env.transfer_card(top_card, deck, hand)
    def invert_core(self, args = {}):
        raise Exception("A phase should never be canceled")
    def make_announcement(self):
        return True
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"Pick Up Card Phase"

class Phase2(AVGEEvent):
    def __init__(self, 
                 player : AVGEPlayer,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__([AVGEFlag.PHASE_2], catalyst_action,caller_card)
        self.player = player
    def core(self, args : Data = {}) -> Response:
        env : AVGEEnvironment = self.player.env
        active_card : AVGECharacterCard = env.get_active_card(self.player.unique_id)
        if(args['next'] == 'atk'):
            self.propose(AtkPhase(self.player, 
                                        ActionTypes.PLAYER_CHOICE,
                                        None))
            return self.generate_core_response()
        elif(args['next'] == 'tool'):
            if('tool' in args and isinstance(args['tool'], AVGEToolCard)
               and args['tool'] in self.player.cardholders[Pile.HAND]
               and 'attach_to' in args and isinstance(args['attach_to'], AVGECharacterCard)):
                event_1 = TransferCard(args['tool'], 
                                                self.player.cardholders[Pile.HAND], 
                                                args['attach_to'].tools_attached,
                                                ActionTypes.PLAYER_CHOICE,
                                                None)
                event_2 = PlayNonCharacterCard(args['tool'],
                                            ActionTypes.PLAYER_CHOICE,
                                            None)
                self.propose([event_1, event_2])
                return self.generate_core_response()
        elif(args['next'] == 'supporter'):
            if('supporter_card' in args and isinstance(args['supporter_card'], AVGESupporterCard)
               and args['supporter_card'] in self.player.cardholders[Pile.HAND]):
                event_1 = PlayNonCharacterCard(args['supporter_card'],
                                            ActionTypes.PLAYER_CHOICE,
                                            None)
                event_2 = AVGEPlayerAttributeChange(
                    self.player,
                    AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN,
                    -1,
                    AVGEAttributeModifier.ADDITIVE,
                    ActionTypes.PLAYER_CHOICE,
                    None
                )
                self.propose([event_1, event_2])
                return self.generate_core_response()
        elif(args['next'] == 'item'):
            if('item_card' in args and isinstance(args['item_card'], AVGEItemCard)
               and args['item_card'] in self.player.cardholders[Pile.HAND]):
                self.propose(PlayNonCharacterCard(args['item_card'], 
                                                ActionTypes.PLAYER_CHOICE,
                                                None))
                return self.generate_core_response()
        elif(args['next'] == 'stadium'):
            if('stadium_card' in args and isinstance(args['stadium_card'], AVGEStadiumCard)
               and args['stadium_card'] in self.player.cardholders[Pile.HAND]):
                self.propose(TransferCard(args['stadium_card'],
                                                env.stadium_cardholder,
                                                self.player.cardholders[Pile.HAND],
                                                ActionTypes.PLAYER_CHOICE,
                                                None))
                return self.generate_core_response()
        elif(args['next'] == 'swap'):
            if('bench_card' in args and isinstance(args['bench_card'], AVGECharacterCard) and
               args['bench_card'] in self.player.cardholders[Pile.BENCH]):
                event_1 = TransferCard(args['bench'], 
                                                self.player.cardholders[Pile.BENCH], 
                                                self.player.cardholders[Pile.ACTIVE],
                                                ActionTypes.PLAYER_CHOICE,
                                                None)
                event_2 = TransferCard(active_card, 
                                                self.player.cardholders[Pile.ACTIVE], 
                                                self.player.cardholders[Pile.BENCH],
                                                ActionTypes.PLAYER_CHOICE,
                                                None)
                event_3 = AVGEPlayerAttributeChange(
                    self.player,
                    AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN,
                    -1,
                    AVGEAttributeModifier.ADDITIVE,
                    ActionTypes.PLAYER_CHOICE,
                    None
                )
                self.propose([event_1, event_2, event_3])
                return self.generate_core_response()
        elif(args['next'] == 'energy'):
            if('attach_to' in args and isinstance(args['attach_to'], AVGECharacterCard)):
                event_1 = AVGECardAttributeChange(args['attach_to'],
                                            AVGECardAttribute.ENERGY_ATTACHED,
                                            1,
                                            AVGEAttributeModifier.ADDITIVE,
                                            ActionTypes.PLAYER_CHOICE,
                                            None)
                event_2 = AVGEPlayerAttributeChange(
                    self.player,
                    AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN,
                    -1,
                    AVGEAttributeModifier.ADDITIVE,
                    ActionTypes.PLAYER_CHOICE,
                    None)
                event_3 = AVGEPlayerAttributeChange(
                    self.player,
                    AVGEPlayerAttribute.TOTAL_ENERGY_TOKENS,
                    -1,
                    AVGEAttributeModifier.ADDITIVE,
                    ActionTypes.PLAYER_CHOICE,
                    None)
                self.propose([event_1, event_2, event_3])
                return self.generate_core_response()
            
        elif(args['next'] == 'hand2bench'):
            if('hand2bench' in args and isinstance(args['hand2bench'], AVGECharacterCard) and
               args['hand2bench'] in self.player.cardholders[Pile.HAND]):
                packet = []
                packet.append(TransferCard(args['hand2bench'], 
                                                self.player.cardholders[Pile.HAND], 
                                                self.player.cardholders[Pile.BENCH],
                                                ActionTypes.PLAYER_CHOICE,
                                                None))
                if(args['hand2bench'].has_passive):
                    packet.append(PlayCharacterCard())
                self.propose([event_1, event_2, event_3])
                return self.generate_core_response()
        return self.generate_core_response(ResponseType.REQUIRES_QUERY,
                                            {'query_type': 'phase2', 'player_involved': self.player})
    def invert_core(self, args = {}):
        raise Exception("A phase should never be canceled")
    def make_announcement(self):
        return True
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"Phase 2"
    
class AtkPhase(AVGEEvent):
    def __init__(self, 
                 player : AVGEPlayer,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__([AVGEFlag.PHASE_ATK], catalyst_action,caller_card)
        self.player = player
    def make_announcement(self):
        return True
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"Atk phase"
    def invert_core(self, args = {}):
        raise Exception("A phase should never be canceled")
    def core(self, args : Data = {}) -> Response:
        env : AVGEEnvironment = self.player.env
        active_card = env.get_active_card(self.player.unique_id)
        if(args['type'] == ActionTypes.ATK_1 or args['type'] == ActionTypes.ATK_2):
            self.propose(PlayCharacterCard(
                active_card,
                args['type'],
                ActionTypes.PLAYER_CHOICE,
                None
            ))
            return self.generate_core_response()
        else:
            return self.generate_core_response(ResponseType.REQUIRES_QUERY, 
                                               {'query_type': 'atk', 'player_involved': self.player})
    
class TurnEnd(AVGEEvent):
    def __init__(self,
                 environment : AVGEEnvironment,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__([AVGEFlag.TURN_END], catalyst_action,caller_card)
        self.env = environment
    def core(self, args = {}) -> Response:
        for player in self.env.players.values():
            player : AVGEPlayer = player
            player.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] = per_turn_token_add
            player.attributes[AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN] = per_turn_supporter
            player.attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN] = per_turn_swaps
        return self.generate_core_response()
    def invert_core(self, args = {}):
        raise Exception("A phase should never be canceled")
    def make_announcement(self):
        return True
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"Ending Turn! Resetting all to default"