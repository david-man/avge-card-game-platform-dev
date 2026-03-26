from __future__ import annotations
from .avge_abstracts.AVGEEvent import *
from .avge_abstracts.AVGECards import *
from .avge_abstracts.AVGEPlayer import *
from .avge_abstracts.AVGEEnvironment import AVGEEnvironment
from .avge_abstracts.AVGECardholder import AVGEStadiumCardholder, AVGEToolCardholder
from .abstract.cardholder import Cardholder
from .constants import *
class AVGECardAttributeChange(AVGEEvent):
    def __init__(self, 
                 target_card : AVGECharacterCard,
                 attribute : AVGECardAttribute,
                 change_amount : int,
                 attribute_modifier_type : AVGEAttributeModifier,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None,
                 change_type : Type = None):
        super().__init__(catalyst_action,caller_card)
        self.change_amount = change_amount
        self.attribute = attribute
        self.target_card = target_card
        self.change_type = change_type
        self.attribute_modifier_type = attribute_modifier_type
        self.old_amt = None
    
    def make_announcement(self):
        return True
    
    def core(self, args :Data | None = None) -> Response:
        if(args is None):
            args = {}
        self.old_amt = self.target_card.attributes[self.attribute]
        if(self.attribute_modifier_type == AVGEAttributeModifier.ADDITIVE):
            self.target_card.attributes[self.attribute] += self.change_amount
        else:
            self.target_card.attributes[self.attribute] = self.change_amount
        return self.generate_core_response()
    
    def invert_core(self, args : Data | None = None):
        self.target_card.attributes[self.attribute] = self.old_amt

    def generate_internal_listeners(self):
        from .internal_listeners import AVGECardAttributeChangeAssessment, AVGECardAttributeChangePostCheck, AVGECardAttributeChangeReactor, AVGECardAttributeChangeModifier
        self.attach_listener(AVGECardAttributeChangeAssessment())
        self.attach_listener(AVGECardAttributeChangeModifier())
        self.attach_listener(AVGECardAttributeChangeReactor())#this needs to go first!(we need to react and then quit for discards)
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
        super().__init__(catalyst_action,caller_card)
        self.change_amount = change_amount
        self.attribute = attribute
        self.target_player = target_player
        self.attribute_modifier_type = attribute_modifier_type
        self.old_amt = None
    
    def make_announcement(self):
        return True
    
    def core(self, args :Data | None = None) -> Response:
        if(args is None):
            args = {}
        self.old_amt = self.target_player.attributes[self.attribute]
        if(self.attribute_modifier_type == AVGEAttributeModifier.ADDITIVE):
            self.target_player.attributes[self.attribute] += self.change_amount
        else:
            self.target_player.attributes[self.attribute] = self.change_amount
        return self.generate_core_response()
    
    def invert_core(self, args : Data | None = None):
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
                 pile_from : AVGECardholder,
                 pile_to : AVGECardholder,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None,
                 new_idx : int = None):
        super().__init__(catalyst_action,caller_card)
        self.card = card
        self.pile_to = pile_to
        self.pile_from = pile_from
        self.new_idx = new_idx
        self.old_idx = pile_from.get_posn(self.card)

        self._previous_card = None#only for tools
    
    def make_announcement(self):
        return True
    
    def core(self, args :Data | None = None) -> Response:
        if(args is None):
            args = {}
        if(isinstance(self.card, AVGEToolCard) and isinstance(self.pile_from, AVGEToolCardholder)):
            if(self.card.card_attached is not None):
                self._previous_card = self.card.card_attached
            self.card.card_attached = self.pile_from.parent_card
        self.card.env.transfer_card(self.card, self.pile_from, self.pile_to, self.new_idx)
        return self.generate_core_response()
    
    def invert_core(self, args : Data | None = None):
        if(isinstance(self.card, AVGEToolCard) and isinstance(self.pile_from, AVGEToolCardholder)):
            self.card.card_attached = self._previous_card
        self.card.env.transfer_card(self.card, self.pile_to, self.pile_from, self.old_idx)

    def generate_internal_listeners(self):
        from .internal_listeners import AVGETransferValidityCheck, AVGEDiscardReactor
        self.attach_listener(AVGETransferValidityCheck())
        self.attach_listener(AVGEDiscardReactor())
    
    def package(self):
        return f"{self.card} from {self.pile_from} to {self.pile_to}"
    
class ReorderCardholder(AVGEEvent):
    def __init__(self,
                 cardholder : Cardholder,
                 new_order : list[str],
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__(catalyst_action, caller_card)
        self.cardholder = cardholder
        self.new_order = new_order
        self.original_order = [k for k in self.cardholder.get_order()]
    def core(self, args : Data | None = None) -> Response:
        if(args is None):
            args = {}
        self.cardholder.reorder(self.new_order)
        return self.generate_core_response()
    def invert_core(self, args : Data | None = None):
        self.cardholder.reorder(self.original_order)
    def make_announcement(self):
        return True
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"Reordering {self.cardholder.player.unique_id}'s {self.cardholder.pile_type}"

#In PlayCharacter & PlayNoncharacter Card it is assumed that if the caller card is a character card,
#the action should be done on behalf of the caller card. 
        
    
class PlayCharacterCard(AVGEEvent):
    def __init__(self, 
                 card : AVGECharacterCard,
                 card_action : ActionTypes,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__(catalyst_action,caller_card)
        self.card = card
        self.card_action = card_action
        self.cache_snapshot = None
    def core(self, args : Data | None = None) -> Response:
        if(args is None):
            args = {}
        
        if(self.card_action == ActionTypes.SKIP):
            return self.generate_core_response()
        else:
            return self.card.play_card(self, self.caller_card if isinstance(self.caller_card, AVGECharacterCard) else self.card, 
                                       args)
    def invert_core(self, args : Data | None = None):
        return
    def make_announcement(self):
        return True
    def generate_internal_listeners(self):
        from .internal_listeners import AVGEPlayCharacterCardValidityCheck, AVGERNGHook
        self.attach_listener(AVGEPlayCharacterCardValidityCheck())
        self.attach_listener(AVGERNGHook())
    def package(self):
        return f"{self.card_action} action from {self.card}"
    
class PlayNonCharacterCard(AVGEEvent):
    def __init__(self, 
                 card : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__(catalyst_action,caller_card)
        self.card = card
    def core(self, args : Data | None = None) -> Response:
        if(args is None):
            args = {}
        for rng_type in RNGType:
            if(rng_type in self.temp_cache):
                args[rng_type] = self.temp_cache[rng_type]
        return self.card.play_card(self, self.caller_card, args)
    def invert_core(self, args : Data | None = None):
        return
    def make_announcement(self):
        return True
    def generate_internal_listeners(self):
        from .internal_listeners import AVGEPlayNonCharacterCardValidityCheck, AVGERNGHook
        self.attach_listener(AVGEPlayNonCharacterCardValidityCheck())
        self.attach_listener(AVGERNGHook())
    def package(self):
        return f"{self.card} was played!"
class PhasePickCard(AVGEEvent):
    def __init__(self, 
                 player : AVGEPlayer,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__(catalyst_action,caller_card)
        self.player = player
    def core(self, args : Data | None = None) -> Response:
        if(args is None):
            args = {}
        if(len(self.player.cardholders[Pile.DECK]) > 0):
            deck = self.player.cardholders[Pile.DECK]
            hand = self.player.cardholders[Pile.HAND]
            top_card = deck.peek()
            self.propose(TransferCard(top_card,
                                      deck,
                                      hand,
                                      ActionTypes.ENV,
                                      None))
        return self.generate_core_response()
    def invert_core(self, args : Data | None = None):
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
        super().__init__(catalyst_action,caller_card)
        self.player = player
    def core(self, args : Data | None = None) -> Response:
        from .avge_abstracts.AVGEEnvironment import GamePhase
        if(args is None):
            args = {}
        env : AVGEEnvironment = self.player.env
        env.game_phase = GamePhase.PHASE_2
        active_card : AVGECharacterCard = env.get_active_card(self.player.unique_id)
        next_action = args.get('next')

        if(next_action is None):
            return self.generate_core_response(ResponseType.REQUIRES_QUERY,
                                            {'query_type': 'phase2', 'player_involved': self.player})

        if(next_action == 'atk'):
            self.propose(AtkPhase(self.player,
                                  ActionTypes.PLAYER_CHOICE,
                                  None))
            return self.generate_core_response()

        elif(next_action == 'tool'):
            tool = args.get('tool')
            attach_to = args.get('attach_to')
            if(isinstance(tool, AVGEToolCard)
               and tool in self.player.cardholders[Pile.HAND]
               and isinstance(attach_to, AVGECharacterCard)):
                event_1 = TransferCard(tool,
                                       self.player.cardholders[Pile.HAND],
                                       attach_to.tools_attached,
                                       ActionTypes.PLAYER_CHOICE,
                                       None)
                event_2 = PlayNonCharacterCard(tool,
                                               ActionTypes.PLAYER_CHOICE,
                                               None)
                self.propose([event_1, event_2])
                return self.generate_core_response()

        elif(next_action == 'supporter'):
            supporter_card = args.get('supporter_card')
            if(isinstance(supporter_card, AVGESupporterCard)
               and supporter_card in self.player.cardholders[Pile.HAND]):
                event_1 = PlayNonCharacterCard(supporter_card,
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
                event_3 = TransferCard(supporter_card,
                                       supporter_card.cardholder,
                                       supporter_card.player.cardholders[Pile.DISCARD],
                                       ActionTypes.PLAYER_CHOICE,
                                       None)
                self.propose([event_1, event_2, event_3])
                return self.generate_core_response()

        elif(next_action == 'item'):
            item_card = args.get('item_card')
            if(isinstance(item_card, AVGEItemCard)
               and item_card in self.player.cardholders[Pile.HAND]):
                packet = []
                packet.append(PlayNonCharacterCard(item_card,
                                                   ActionTypes.PLAYER_CHOICE,
                                                   None))
                packet.append(TransferCard(item_card,
                                           item_card.cardholder,
                                           item_card.player.cardholders[Pile.DISCARD],
                                           ActionTypes.PLAYER_CHOICE,
                                           None))
                self.propose(packet)
                return self.generate_core_response()

        elif(next_action == 'stadium'):
            stadium_card = args.get('stadium_card')
            if(isinstance(stadium_card, AVGEStadiumCard)
               and stadium_card in self.player.cardholders[Pile.HAND]):
                packet = []
                if(len(env.stadium_cardholder) > 0):
                    old_stadium : AVGEStadiumCard = env.stadium_cardholder.peek()
                    packet.append(TransferCard(old_stadium,
                                               env.stadium_cardholder,
                                               old_stadium.original_owner.cardholders[Pile.DISCARD],
                                               ActionTypes.PLAYER_CHOICE,
                                               None))
                packet.append(TransferCard(stadium_card,
                                           self.player.cardholders[Pile.HAND],
                                           env.stadium_cardholder,
                                           ActionTypes.PLAYER_CHOICE,
                                           None))
                packet.append(PlayNonCharacterCard(stadium_card,
                                                   ActionTypes.PLAYER_CHOICE,
                                                   None))
                self.propose(packet)
                return self.generate_core_response()

        elif(next_action == 'swap'):
            bench_card = args.get('bench_card')
            if(isinstance(bench_card, AVGECharacterCard)
               and bench_card in self.player.cardholders[Pile.BENCH]):
                event_1 = TransferCard(bench_card,
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

        elif(next_action == 'energy'):
            attach_to = args.get('attach_to')
            if(isinstance(attach_to, AVGECharacterCard)):
                event_1 = AVGECardAttributeChange(attach_to,
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

        elif(next_action == 'hand2bench'):
            hand2bench_card = args.get('hand2bench')
            if(isinstance(hand2bench_card, AVGECharacterCard)
               and hand2bench_card in self.player.cardholders[Pile.HAND]):
                packet = []
                packet.append(TransferCard(hand2bench_card,
                                           self.player.cardholders[Pile.HAND],
                                           self.player.cardholders[Pile.BENCH],
                                           ActionTypes.PLAYER_CHOICE,
                                           None))
                if(hand2bench_card.has_passive):
                    packet.append(PlayCharacterCard(hand2bench_card,
                                                    ActionTypes.PASSIVE,
                                                    ActionTypes.PLAYER_CHOICE,
                                                    None))
                self.propose(packet)
                return self.generate_core_response()

        return self.generate_core_response(ResponseType.REQUIRES_QUERY,
                                           {'query_type': 'phase2', 'player_involved': self.player})
    def invert_core(self, args : Data | None = None):
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
        super().__init__(catalyst_action,caller_card)
        self.player = player
    def make_announcement(self):
        return True
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"Atk phase"
    def invert_core(self, args : Data | None = None):
        raise Exception("A phase should never be canceled")
    def core(self, args : Data | None = None) -> Response:
        from .avge_abstracts.AVGEEnvironment import GamePhase
        
        if(args is None):
            args = {}
        env : AVGEEnvironment = self.player.env
        env.game_phase = GamePhase.ATK_PHASE
        active_card = env.get_active_card(self.player.unique_id)
        atk_type = args.get('type')
        if(atk_type == ActionTypes.ATK_1 or atk_type == ActionTypes.ATK_2):
            packet = []
            packet.append(PlayCharacterCard(
                active_card,
                atk_type,
                ActionTypes.PLAYER_CHOICE,
                None
            ))
            packet.append(AVGEPlayerAttributeChange(
                env.player_turn,
                AVGEPlayerAttribute.ATTACKS_LEFT,
                -1,
                AVGEAttributeModifier.ADDITIVE,
                ActionTypes.ENV,
                None
            ))
            self.propose(packet)
            return self.generate_core_response()
        else:
            return self.generate_core_response(ResponseType.REQUIRES_QUERY, 
                                               {'query_type': 'atk', 'player_involved': self.player})

class ChangeStatus(AVGEEvent):
    def __init__(self,
                 card : AVGECharacterCard,
                 status : StatusEffect,
                 change_type : ChangeType,
                 catalyst_action : ActionTypes,
                 caller_card : Card | None):
        super().__init__(catalyst_action, caller_card)
        self.card= card
        self.change_type = change_type
        self.status=status
        self._old_count = None
    def core(self, args : Data | None = None) -> Response:
        self._old_count = self.card.statuses_attached.get(self.status, 0)
        if(self.change_type == ChangeType.ADD):
            self.card.statuses_attached[self.status] = self.card.statuses_attached.get(self.status,0)+1
        elif(self.change_type == ChangeType.REMOVE):
            if(self.status in self.card.statuses_attached and self.card.statuses_attached[self.status] > 0):
                self.card.statuses_attached[self.status] = self.card.statuses_attached[self.status] - 1
                if(self.card.statuses_attached[self.status] == 0):
                    del self.card.statuses_attached[self.status]
        return self.generate_core_response()
    def invert_core(self, args = None):
        if(self._old_count == 0):
            if(self.status in self.card.statuses_attached):
                del self.card.statuses_attached[self.status]
        elif(self._old_count > 0):
            self.card.statuses_attached[self.status] = self._old_count
    def make_announcement(self):
        return True
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"{self.status} change type of {self.change_type} to {self.card}"
    
class TurnEnd(AVGEEvent):
    def __init__(self,
                 environment : AVGEEnvironment,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__(catalyst_action,caller_card)
        self.env = environment
    def core(self, args : Data | None = None) -> Response:
        from .avge_abstracts.AVGEEnvironment import GamePhase
        if(args is None):
            args = {}
        self.env.game_phase = GamePhase.TURN_END
        for player in self.env.players.values():
            player : AVGEPlayer = player
            player.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] = per_turn_token_add
            player.attributes[AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN] = per_turn_supporter
            player.attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN] = per_turn_swaps
            player.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = per_turn_atks
        self.env.player_turn = player.opponent
        round_num, increment = self.env.round
        if(increment):
            self.env.round = (round_num + 1, False)
        else:
            self.env.round = (round_num, True)
        self.propose(PhasePickCard(self.env.player_turn,
                                   ActionTypes.ENV,
                                   None))
        return self.generate_core_response()
    def invert_core(self, args : Data | None = None):
        raise Exception("A phase should never be canceled")
    def make_announcement(self):
        return True
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"Ending Turn! Resetting all to default"