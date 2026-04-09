from __future__ import annotations
from typing import TYPE_CHECKING
from .avge_abstracts.AVGEEvent import *
from .avge_abstracts.AVGECards import *
from .avge_abstracts.AVGEPlayer import *
from .avge_abstracts.AVGECardholder import AVGEStadiumCardholder, AVGEToolCardholder
from .constants import *

if TYPE_CHECKING:
    from .avge_abstracts.AVGEEnvironment import AVGEEnvironment


class AVGECardHPChange(AVGEEvent):
    def __init__(self,
                 target_card : AVGECharacterCard,
                 magnitude : int,
                 modifier_type : AVGEAttributeModifier,
                 change_type : CardType,
                 catalyst_action : ActionTypes,
                 caller_card : AVGECard | None):
        super().__init__(target_card = target_card,
                         magnitude = magnitude,
                         modifier_type = modifier_type,
                         catalyst_action=catalyst_action,
                         caller_card=caller_card,
                         change_type=change_type)
        self.magnitude = magnitude
        self.target_card = target_card
        self.change_type = change_type
        self.modifier_type = modifier_type
        self.old_amt = None
    def modify_magnitude(self, change : int):
        #please use this function when modifying magnitudes, thanks!
        if(self.modifier_type != AVGEAttributeModifier.SET_STATE):
            if(self.magnitude == 0):#once a heal/dmg move hits 0, it can't be changed
                return
        self.magnitude += change
        self.magnitude = max(0, self.magnitude)
        if(self.modifier_type == AVGEAttributeModifier.SUBSTRACTIVE):
            self.magnitude = min(self.target_card.hp, self.magnitude)
    def current_proposed_value(self):
        if(self.modifier_type == AVGEAttributeModifier.ADDITIVE):
            return self.target_card.hp + self.magnitude
        elif(self.modifier_type == AVGEAttributeModifier.SUBSTRACTIVE):
            return self.target_card.hp - self.magnitude
        else:
            return self.magnitude
    
    def core(self, args : Data | None = None) -> Response:
        self.old_amt = self.target_card.hp
        self.target_card.hp = self.current_proposed_value()
        self.target_card.hp = min(self.target_card.hp, self.target_card.max_hp)
        return self.generate_core_response()
    
    def invert_core(self, args : Data | None = None):
        assert(not self.old_amt is None)
        self.target_card.hp = self.old_amt

    def generate_internal_listeners(self):
        from .internal_listeners import AVGEHPChangeAssessment, AVGEWeaknessModifier, AVGECardHPChangeReactor
        from .catalog.status_effects.Maid import MaidStatusDamageShieldModifier
        self.attach_listener(AVGEHPChangeAssessment())
        self.attach_listener(AVGEWeaknessModifier())
        self.attach_listener(MaidStatusDamageShieldModifier())
        self.attach_listener(AVGECardHPChangeReactor())
    
    def package(self):
        return f"{self.modifier_type} change for {self.target_card} HP of magnitude {self.magnitude}"
        
class AVGECardMaxHPChange(AVGEEvent):
    def __init__(self,
                 target_card : AVGECharacterCard,
                 magnitude : int,
                 modifier_type : AVGEAttributeModifier,
                 catalyst_action : ActionTypes,
                 caller_card : AVGECard | None):
        super().__init__(target_card = target_card,
                         magnitude = magnitude,
                         modifier_type = modifier_type,
                         catalyst_action=catalyst_action,
                         caller_card=caller_card)
        self.magnitude = magnitude
        self.target_card = target_card
        self.modifier_type = modifier_type
        self.old_max = None
        self.old_hp = None
    
    def modify_magnitude(self, change : int):
        #please use this function when modifying magnitudes, thanks!
        self.magnitude += change
        self.magnitude = max(0, self.magnitude)
        if(self.modifier_type == AVGEAttributeModifier.SUBSTRACTIVE):
            self.magnitude = min(self.target_card.hp, self.magnitude)
    def current_proposed_value(self):
        if(self.modifier_type == AVGEAttributeModifier.ADDITIVE):
            return self.target_card.max_hp + self.magnitude
        elif(self.modifier_type == AVGEAttributeModifier.SUBSTRACTIVE):
            return self.target_card.max_hp - self.magnitude
        else:
            return self.magnitude
    
    def core(self, args :Data | None = None) -> Response:
        self.old_max = self.target_card.max_hp
        self.old_hp = self.target_card.hp
        self.target_card.max_hp = self.current_proposed_value()
        self.target_card.hp = min(self.target_card.hp, self.target_card.max_hp)
        return self.generate_core_response()
    
    def invert_core(self, args : Data | None = None):
        assert(not self.old_hp is None)
        assert(not self.old_max is None)
        self.target_card.hp = self.old_hp
        self.target_card.max_hp = self.old_max

    def generate_internal_listeners(self):
        from .internal_listeners import AVGEMaxHPChangeAssessment
        self.attach_listener(AVGEMaxHPChangeAssessment())
        return
    
    def package(self):
        return f"{self.modifier_type} change for {self.target_card} HP of magnitude {self.magnitude}"
    
class AVGECardTypeChange(AVGEEvent):
    def __init__(self,
                 target_card : AVGECharacterCard,
                 new_type : CardType,
                 catalyst_action : ActionTypes,
                 caller_card : AVGECard | None):
        super().__init__(target_card=target_card,
                         new_type=new_type,
                         catalyst_action=catalyst_action,
                         caller_card=caller_card)
        self.target_card = target_card
        self.new_type = new_type
        self.old_type = None
    def core(self, args :Data | None = None) -> Response:
        self.old_type = self.target_card.card_type
        self.target_card.card_type = self.new_type
        return self.generate_core_response()
    
    def invert_core(self, args : Data | None = None):
        assert(not self.old_type is None)
        self.target_card.card_type = self.old_type

    def generate_internal_listeners(self):
        return
    
    def package(self):
        return f"Changing {self.target_card} type to {self.new_type}"
class AVGECardStatusChange(AVGEEvent):
    def __init__(self,
                 status_effect : StatusEffect,
                 change_type : StatusChangeType,
                 target : AVGECharacterCard,
                 catalyst_action : ActionTypes,
                 caller_card : AVGECard | None):
        #caller card is the one who gives the effect. None when ENV
        super().__init__(status_effect=status_effect,change_type=change_type,target=target,catalyst_action=catalyst_action,caller_card=caller_card)
        self.status_effect = status_effect
        self.target = target
        self.change_type = change_type

        self.made_change = True
        self._old = []
    def core(self, args = None) -> Response:
        if(self.change_type == StatusChangeType.ADD):
            if(self.caller_card not in self.target.statuses_attached[self.status_effect]):
                self.target.statuses_attached[self.status_effect].append(self.caller_card)
                if(isinstance(self.caller_card, AVGECharacterCard)):
                    self.caller_card.statuses_responsible[self.status_effect].append(self.target)
            else:
                self.made_change = False
        elif(self.change_type == StatusChangeType.ERASE):
            if(self.caller_card in self.target.statuses_attached[self.status_effect]):
                self.target.statuses_attached[self.status_effect].remove(self.caller_card)
                if(isinstance(self.caller_card, AVGECharacterCard)):
                    self.caller_card.statuses_responsible[self.status_effect].remove(self.target)
            else:
                self.made_change = False
        elif(self.change_type == StatusChangeType.REMOVE):
            self._old = self.target.statuses_attached[self.status_effect]
            for card in self.target.statuses_attached[self.status_effect]:
                if(isinstance(card, AVGECharacterCard)):
                    card.statuses_responsible[self.status_effect].remove(self.target)
            self.target.statuses_attached[self.status_effect] = []
        return self.generate_core_response()
    def invert_core(self, args = None):
        if(not self.made_change):
            return
        if(self.change_type == StatusChangeType.ADD):
            self.target.statuses_attached[self.status_effect].remove(self.caller_card)
            if(isinstance(self.caller_card, AVGECharacterCard)):
                self.caller_card.statuses_responsible[self.status_effect].remove(self.target)
        elif(self.change_type == StatusChangeType.ERASE):
            self.target.statuses_attached[self.status_effect].append(self.caller_card)
            if(isinstance(self.caller_card, AVGECharacterCard)):
                self.caller_card.statuses_responsible[self.status_effect].append(self.target)
        elif(self.change_type == StatusChangeType.REMOVE):
            self.target.statuses_attached[self.status_effect] = self._old
            for card in self.target.statuses_attached[self.status_effect]:
                if(isinstance(card, AVGECharacterCard)):
                    card.statuses_responsible[self.status_effect].append(self.target)
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"Transferring energy!"
class AVGEEnergyTransfer(AVGEEvent):
    def __init__(self,
                 token : EnergyToken,
                 source : AVGEPlayer | AVGECharacterCard | AVGEEnvironment,
                 target : AVGEPlayer | AVGECharacterCard | AVGEEnvironment,
                 catalyst_action : ActionTypes, 
                 caller_card : AVGECard | None):
        super().__init__(token=token,source = source, target=target, catalyst_action=catalyst_action, caller_card=caller_card)
        self.token = token
        self.source = source
        self.target = target
    def core(self, args = None) -> Response:
        self.token.detach()
        self.token.attach(self.target)
        return self.generate_core_response()
    def invert_core(self, args = None):
        self.token.detach()
        self.token.attach(self.source)

    def generate_internal_listeners(self):
        from .internal_listeners import AVGETokenTransferAssessment
        self.attach_listener(AVGETokenTransferAssessment())
    def package(self):
        return f"Transferring energy!"
class AVGEPlayerAttributeChange(AVGEEvent):
    def __init__(self, 
                 target_player : AVGEPlayer, #can be delayed to runtime if wanted
                 attribute : AVGEPlayerAttribute,
                 magnitude : int, #can be delayed to runtime if wanted
                 attribute_modifier_type : AVGEAttributeModifier,
                 catalyst_action : ActionTypes, 
                 caller_card : AVGECard | None):
        super().__init__(target_player=target_player,
                 attribute=attribute,
                 magnitude=magnitude,
                 attribute_modifier_type=attribute_modifier_type,
                 catalyst_action=catalyst_action,
                 caller_card=caller_card)
        self.magnitude = magnitude
        self.attribute = attribute
        self.target_player = target_player
        self.attribute_modifier_type = attribute_modifier_type
        self.old_amt = None

    def modify_magnitude(self, change : int):
        #please use this function when modifying magnitudes, thanks!
        self.magnitude += change
        self.magnitude = max(0, self.magnitude)
        if(self.attribute_modifier_type == AVGEAttributeModifier.SUBSTRACTIVE):
            self.magnitude = min(self.target_player.attributes[self.attribute], self.magnitude)
    def current_proposed_value(self):
        true_mag = max(0, self.magnitude)#clamp magnitude to being only positive
        if(self.attribute_modifier_type == AVGEAttributeModifier.ADDITIVE):
            return self.target_player.attributes[self.attribute] + true_mag
        elif(self.attribute_modifier_type == AVGEAttributeModifier.SUBSTRACTIVE):
            return self.target_player.attributes[self.attribute] - true_mag
        else:
            return true_mag
    
    def core(self, args = None) -> Response:
        self.old_amt = self.target_player.attributes[self.attribute]
        self.target_player.attributes[self.attribute] = self.current_proposed_value()
        return self.generate_core_response()
    
    def invert_core(self, args = None):
        assert self.old_amt is not None
        self.target_player.attributes[self.attribute] = self.old_amt

    def generate_internal_listeners(self):
        from .internal_listeners import AVGEPlayerAttributeChangePostChecker
        self.attach_listener(AVGEPlayerAttributeChangePostChecker())
    
    def package(self):
        return f"{self.attribute_modifier_type} AVGEPlayerAttributeChange on {self.target_player} for {self.attribute} of magnitude {self.magnitude}"

class TransferCard(AVGEEvent):
    def __init__(self, 
                 card : AVGECard, #can be delayed to runtime if wanted
                 pile_from : AVGECardholder, #can be delayed to runtime if wanted
                 pile_to : AVGECardholder, #can be delayed to runtime if wanted
                 catalyst_action : ActionTypes, 
                 caller_card : AVGECard | None,
                 new_idx : int | None= None, #can be delayed to runtime if wanted
                 energy_requirement : int = 0
                 ):
        super().__init__(card=card,
                 pile_from=pile_from,
                 pile_to=pile_to,
                 catalyst_action=catalyst_action,
                 caller_card=caller_card,
                 new_idx=new_idx)
        self.card = card
        self.pile_to = pile_to
        self.pile_from = pile_from
        self.new_idx = new_idx
        self.old_idx = None
        self.energy_requirement = energy_requirement
        self._previous_card = None#only for tools

    
    def core(self, args :Data | None = None) -> Response:
        self.old_idx = self.pile_from.get_posn(self.card)

        if(isinstance(self.card, AVGEToolCard)):
            self._previous_card = self.card.card_attached
            self.card.card_attached = self.pile_to.parent_card if isinstance(self.pile_to, AVGEToolCardholder) else None

        
        self.card.env.transfer_card(self.card, self.pile_from, self.pile_to, self.new_idx)

        if(self.pile_to.pile_type == Pile.TOOL and isinstance(self.card, AVGEToolCard) and self.pile_from.pile_type != Pile.TOOL):
            #on tool attachment
            packet : PacketType = [PlayNonCharacterCard(
                self.card,
                ActionTypes.ENV,
                self.card,
            )]
            self.propose(AVGEPacket(packet, AVGEEngineID(None, ActionTypes.ENV, None)))

        if(self.pile_to.pile_type == Pile.STADIUM and isinstance(self.card, AVGEStadiumCard) and self.pile_from.pile_type != Pile.STADIUM):
            #on stadium attachment
            packet : PacketType = [PlayNonCharacterCard(
                self.card,
                ActionTypes.ENV,
                self.card,
            )]
            self.propose(AVGEPacket(packet, AVGEEngineID(None, ActionTypes.ENV, None)))

        if(self.pile_to.pile_type in [Pile.ACTIVE, Pile.BENCH] and isinstance(self.card, AVGECharacterCard) and self.pile_from.pile_type not in [Pile.ACTIVE, Pile.BENCH]):
            #on card activation
            if(self.card.has_passive):
                packet : PacketType = [PlayCharacterCard(
                    self.card,
                    ActionTypes.PASSIVE,
                    ActionTypes.ENV,
                    self.card,
                )]
                self.propose(AVGEPacket(packet, AVGEEngineID(None, ActionTypes.ENV, None)))

        if(self.pile_to.pile_type in [Pile.HAND, Pile.DECK, Pile.DISCARD]):
            #wipes cache when its convenient
            self.card.env.cache.wipe(self.card)

        if(self.pile_to.pile_type == Pile.DISCARD):
            #on tool/stadium discard
            if(self.pile_from.pile_type == Pile.TOOL and isinstance(self.card, AVGEToolCard)):
                self.card.deactivate_card()
            if(self.pile_from.pile_type == Pile.STADIUM and isinstance(self.card, AVGEStadiumCard)):
                self.card.deactivate_card()

        if(self.pile_from.pile_type in [Pile.ACTIVE, Pile.BENCH] and isinstance(self.card, AVGECharacterCard) and self.pile_to.pile_type not in [Pile.ACTIVE, Pile.BENCH]):
            #on card discard
            #discard tools
            def packet_1():
                assert isinstance(self.card, AVGECharacterCard)
                packet : PacketType = [TransferCard(tool,
                                            self.card.tools_attached,
                                            self.pile_to,
                                            ActionTypes.ENV,
                                            None) for tool in self.card.tools_attached]
                return packet
            #drop the energy
            def packet_2():
                assert isinstance(self.card, AVGECharacterCard)
                packet : PacketType = [AVGEEnergyTransfer(token,
                                            self.card,
                                            self.card.env,
                                            ActionTypes.ENV,
                                            None) for token in self.card.energy]
                return packet
            #drop the statuses
            def packet_3():
                assert isinstance(self.card, AVGECharacterCard)
                packet : PacketType = []
                #drop all statuses
                for status_effect, cards in self.card.statuses_attached.items():
                    for c in cards:
                        packet.append(AVGECardStatusChange(
                            status_effect,
                            StatusChangeType.REMOVE,
                            self.card,
                            ActionTypes.ENV,
                            c
                        ))
                return packet
            def packet_4():
                assert isinstance(self.card, AVGECharacterCard)
                packet : PacketType = []
                #reset MAXHP
                packet.append(AVGECardMaxHPChange(
                    self.card,
                    self.card.default_max_hp,
                    AVGEAttributeModifier.SET_STATE,
                    ActionTypes.ENV,
                    None
                ))
                #reset HP
                packet.append(AVGECardHPChange(
                    self.card,
                    self.card.default_max_hp,
                    AVGEAttributeModifier.SET_STATE,
                    CardType.ALL,
                    ActionTypes.ENV,
                    None
                ))
                return packet
            def packet_5():
                assert isinstance(self.card, AVGECharacterCard)
                packet : PacketType= []
                for status in self.card.statuses_responsible:
                    for card in self.card.statuses_responsible[status]:
                        assert isinstance(card, AVGECharacterCard)
                        packet.append(AVGECardStatusChange(
                            status,
                            StatusChangeType.ERASE,
                            card,
                            ActionTypes.ENV,
                            self.card
                        ))
                return packet
            self.propose(AVGEPacket([packet_1, packet_2, packet_3, packet_4, packet_5], AVGEEngineID(None, ActionTypes.ENV, None)), 1)
            self.card.deactivate_card()
            self.card.env.cache.wipe(self.card)
        return self.generate_core_response()
    
    def invert_core(self, args : Data | None = None):
        if(isinstance(self.card, AVGEToolCard)):
            self.card.card_attached = self._previous_card

        self.card.env.transfer_card(self.card, self.pile_to, self.pile_from, self.old_idx)

        if(self.pile_to.pile_type == Pile.DISCARD):
            if(self.pile_from.pile_type == Pile.TOOL and isinstance(self.card, AVGEToolCard)):
                self.card.reactivate_card()
            if(self.pile_from.pile_type == Pile.STADIUM and isinstance(self.card, AVGEStadiumCard)):
                self.card.reactivate_card()

        if(self.pile_from.pile_type in [Pile.ACTIVE, Pile.BENCH] and isinstance(self.card, AVGECharacterCard) and self.pile_to.pile_type not in [Pile.ACTIVE, Pile.BENCH]):
            self.card.reactivate_card()
        

    def generate_internal_listeners(self):
        from .internal_listeners import AVGETransferValidityCheck, AVGETransferEnergyRequirementReactor
        self.attach_listener(AVGETransferValidityCheck())
        self.attach_listener(AVGETransferEnergyRequirementReactor())
    
    def package(self):
        return f"{self.card} from {self.pile_from} to {self.pile_to}"
class ReorderCardholder(AVGEEvent):
    def __init__(self,
                 cardholder : AVGECardholder,
                 new_order : list[str], #can be delayed to runtime if wanted
                 catalyst_action : ActionTypes, 
                 caller_card : AVGECard | None):
        super().__init__(cardholder=cardholder,
                 new_order=new_order,
                 catalyst_action=catalyst_action,
                 caller_card=caller_card)
        self.cardholder = cardholder
        self.new_order = new_order
        self.original_order = [k for k in self.cardholder.get_order()]#copies order
    def core(self, args : Data | None = None) -> Response:
        self.cardholder.reorder(self.new_order)
        return self.generate_core_response()
    def invert_core(self, args : Data | None = None):
        self.cardholder.reorder(self.original_order)
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"Reordering {self.cardholder.player.unique_id}'s {self.cardholder.pile_type}"
#In PlayCharacter & PlayNoncharacter Card, the caller card should always be either set to the card itself or a card that is appropriating that card's ability
        
#In addition, if a card requires an input, it is expected that they use the InputEvent. Don't use args
    
class PlayCharacterCard(AVGEEvent):
    def __init__(self, 
                 card : AVGECharacterCard,
                 card_action : ActionTypes,
                 catalyst_action : ActionTypes, 
                 caller_card : AVGECharacterCard,
                 energy_requirement : int = 0):
        super().__init__(card=card,
                 card_action=card_action,
                 catalyst_action=catalyst_action,
                 caller_card=caller_card,
                 energy_requirement=energy_requirement)
        self.card = card
        self.card_action = card_action
        self.cache_snapshot = None
        self.energy_requirement = energy_requirement
    def core(self, args : Data | None = None) -> Response:
        if(args is None):
            args = {}
        if(self.card_action == ActionTypes.SKIP):
            return self.generate_core_response()
        else:
            args['type'] = self.card_action
            assert isinstance(self.caller_card, AVGECharacterCard)
            return self.card.play_card(self.caller_card, args)
    def invert_core(self, args : Data | None = None):
        return
    def generate_internal_listeners(self):
        from .internal_listeners import AVGEPlayCharacterCardValidityCheck
        self.attach_listener(AVGEPlayCharacterCardValidityCheck())
    def package(self):
        return f"{self.card_action} action from {self.card}"
    
class PlayNonCharacterCard(AVGEEvent):
    def __init__(self, 
                 card : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard,
                 catalyst_action : ActionTypes, 
                 caller_card : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard):
        super().__init__(card=card,
                 catalyst_action=catalyst_action,
                 caller_card=caller_card)
        self.card = card
    def core(self, args : Data | None = None) -> Response:
        if(isinstance(self.card, (AVGEToolCard, AVGEStadiumCard))):
            if(not self.card == self.caller_card):
                raise Exception("Tried to appropriate an ability that can't be appropriated")
            return self.card.play_card()
        else:
            assert isinstance(self.caller_card, (AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard))
            return self.card.play_card(self.caller_card)
    def invert_core(self, args : Data | None = None):
        return
    def generate_internal_listeners(self):
        from .internal_listeners import AVGEPlayNonCharacterCardValidityCheck
        self.attach_listener(AVGEPlayNonCharacterCardValidityCheck())
    def package(self):
        return f"{self.card} was played!"
class PhasePickCard(AVGEEvent):
    def __init__(self, 
                 player : AVGEPlayer,
                 catalyst_action : ActionTypes, 
                 caller_card : AVGECard | None):
        super().__init__(player=player,
                 catalyst_action=catalyst_action,
                 caller_card=caller_card)
        self.player = player
    def core(self, args : Data | None = None) -> Response:
        if(len(self.player.cardholders[Pile.DECK]) > 0):
            deck = self.player.cardholders[Pile.DECK]
            hand = self.player.cardholders[Pile.HAND]
            top_card = deck.peek()
            packet = AVGEPacket([TransferCard(top_card,
                                      deck,
                                      hand,
                                      ActionTypes.ENV,
                                      None),
                                      Phase2(top_card.player,
                                             ActionTypes.ENV,
                                             None)], 
                                      AVGEEngineID(None, ActionTypes.ENV, None))
            self.propose(packet)
            return self.generate_core_response()
        else:
            return self.generate_core_response(ResponseType.GAME_END, {"winner": self.player.opponent, "reason": "no cards left to draw"})
    def invert_core(self, args : Data | None = None):
        raise Exception("A phase should never be canceled")
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"Pick Up Card Phase"

class Phase2(AVGEEvent):
    def __init__(self, 
                 player : AVGEPlayer,
                 catalyst_action : ActionTypes, 
                 caller_card : AVGECard | None):
        super().__init__(player=player,
                         catalyst_action=catalyst_action,
                         caller_card=caller_card)
        self.player = player
    def core(self, args : Data | None = None) -> Response:
        from .avge_abstracts.AVGEEnvironment import GamePhase
        if(args is None):
            args = {}
        env : AVGEEnvironment = self.player.env
        env.game_phase = GamePhase.PHASE_2
        active_card : AVGECharacterCard = cast(AVGECharacterCard, env.get_active_card(self.player.unique_id))
        next_action = args.get('next', "")

        if(next_action == 'atk'):
            env.game_phase = GamePhase.ATK_PHASE
            self.propose(AVGEPacket([AtkPhase(self.player,
                                  ActionTypes.PLAYER_CHOICE,
                                  None)], AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)))
            return self.generate_core_response()

        elif(next_action == 'tool'):
            tool = args.get('tool')
            attach_to = args.get('attach_to')
            if(isinstance(tool, AVGEToolCard)
               and tool in self.player.cardholders[Pile.HAND]
               and isinstance(attach_to, AVGECharacterCard)):
                packet = []
                packet.append(TransferCard(tool,
                                       self.player.cardholders[Pile.HAND],
                                       attach_to.tools_attached,
                                       ActionTypes.PLAYER_CHOICE,
                                       None))
                if(len(attach_to.tools_attached) > 0):
                    packet.append(TransferCard(attach_to.tools_attached.peek(),
                                               attach_to.tools_attached,
                                               self.player.cardholders[Pile.DISCARD],
                                               ActionTypes.PLAYER_CHOICE,
                                               None))
                self.propose(AVGEPacket(packet, AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)))
                return self.generate_core_response()

        elif(next_action == 'supporter'):
            supporter_card = args.get('supporter_card')
            if(isinstance(supporter_card, AVGESupporterCard)
               and supporter_card in self.player.cardholders[Pile.HAND]):
                event_1 = PlayNonCharacterCard(supporter_card,
                                               ActionTypes.PLAYER_CHOICE,
                                               supporter_card)
                event_2 = AVGEPlayerAttributeChange(
                    self.player,
                    AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN,
                    1,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    ActionTypes.PLAYER_CHOICE,
                    None
                )
                event_3 = TransferCard(supporter_card,
                                       supporter_card.cardholder,
                                       supporter_card.player.cardholders[Pile.DISCARD],
                                       ActionTypes.PLAYER_CHOICE,
                                       None)
                self.propose(AVGEPacket([event_1, event_2, event_3], AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)))
                return self.generate_core_response()

        elif(next_action == 'item'):
            item_card = args.get('item_card')
            if(isinstance(item_card, AVGEItemCard)
               and item_card in self.player.cardholders[Pile.HAND]):
                packet = []
                packet.append(PlayNonCharacterCard(item_card,
                                                   ActionTypes.PLAYER_CHOICE,
                                                   item_card))
                packet.append(TransferCard(item_card,
                                           item_card.cardholder,
                                           item_card.player.cardholders[Pile.DISCARD],
                                           ActionTypes.PLAYER_CHOICE,
                                           None))
                self.propose(AVGEPacket(packet,AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)))
                return self.generate_core_response()

        elif(next_action == 'stadium'):
            stadium_card = args.get('stadium_card')
            if(isinstance(stadium_card, AVGEStadiumCard)
               and stadium_card in self.player.cardholders[Pile.HAND]):
                packet = []
                packet.append(TransferCard(stadium_card,
                                           self.player.cardholders[Pile.HAND],
                                           env.stadium_cardholder,
                                           ActionTypes.PLAYER_CHOICE,
                                           None))
                if(len(env.stadium_cardholder) > 0):
                    old_stadium : AVGEStadiumCard = cast(AVGEStadiumCard, env.stadium_cardholder.peek())
                    assert old_stadium.original_owner is not None
                    packet.append(TransferCard(old_stadium,
                                               env.stadium_cardholder,
                                               old_stadium.original_owner.cardholders[Pile.DISCARD],
                                               ActionTypes.PLAYER_CHOICE,
                                               None))
                self.propose(AVGEPacket(packet,AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)))
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
                                       None,
                                       energy_requirement=active_card.retreat_cost)
                event_3 = AVGEPlayerAttributeChange(
                    self.player,
                    AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN,
                    1,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    ActionTypes.PLAYER_CHOICE,
                    None
                )
                self.propose(AVGEPacket([event_1, event_2, event_3],AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)))
                return self.generate_core_response()

        elif(next_action == 'energy'):
            attach_to = args.get('attach_to')
            if(isinstance(attach_to, AVGECharacterCard)):
                if(len(self.player.energy) > 0):
                    token = self.player.energy[0]
                    event = AVGEEnergyTransfer(token,
                                               self.player,
                                               attach_to,
                                               ActionTypes.PLAYER_CHOICE,
                                               None)
                    event_2 = AVGEPlayerAttributeChange(self.player,
                                               AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN,
                                               1,
                                               AVGEAttributeModifier.SUBSTRACTIVE,
                                               ActionTypes.ENV,
                                               None)
                    self.propose(AVGEPacket([event, event_2],AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)))
                else:
                    return self.generate_core_response(ResponseType.REQUIRES_QUERY,
                                           {'query_type': 'phase2', 'player_involved': self.player, MESSAGE_KEY: "No energy left to give!"})
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
                self.propose(AVGEPacket(packet,AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)))
                return self.generate_core_response()

        return self.generate_core_response(ResponseType.REQUIRES_QUERY,
                                           {'query_type': 'phase2', 'player_involved': self.player})
    def invert_core(self, args : Data | None = None):
        raise Exception("A phase should never be canceled")
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"Phase 2"
    
class AtkPhase(AVGEEvent):
    def __init__(self, 
                 player : AVGEPlayer,
                 catalyst_action : ActionTypes, 
                 caller_card : AVGECard | None):
        super().__init__(player=player,
                 catalyst_action=catalyst_action,
                 caller_card=caller_card)
        self.player = player
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
        assert isinstance(active_card, AVGECharacterCard)
        atk_type = args.get('type')
        if(atk_type == ActionTypes.ATK_1 or atk_type == ActionTypes.ATK_2):
            if(atk_type == ActionTypes.ATK_1 and active_card.has_atk_1 or
               atk_type == ActionTypes.ATK_2 and active_card.has_atk_2):
                packet = []
                packet.append(PlayCharacterCard(
                    cast(AVGECharacterCard, active_card),
                    atk_type,
                    ActionTypes.PLAYER_CHOICE,
                    cast(AVGECharacterCard, active_card),
                    active_card.atk_1_cost if atk_type==ActionTypes.ATK_1 else active_card.atk_2_cost
                ))
                packet.append(AVGEPlayerAttributeChange(
                    env.player_turn,
                    AVGEPlayerAttribute.ATTACKS_LEFT,
                    1,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    ActionTypes.ENV,
                    None
                ))# --> need a better way to figure out end of attack than this. this runs into the issue where the actual contents of the atk itself get SKIPPED, but the player still loses their attack
                self.propose(AVGEPacket(packet,AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)))
                return self.generate_core_response()
            return self.generate_core_response(ResponseType.REQUIRES_QUERY, 
                                               {'query_type': 'atk', 'player_involved': self.player})
        elif(atk_type == ActionTypes.SKIP):
            packet = []
            packet.append(AVGEPlayerAttributeChange(
                    env.player_turn,
                    AVGEPlayerAttribute.ATTACKS_LEFT,
                    0,
                    AVGEAttributeModifier.SET_STATE,
                    ActionTypes.ENV,
                    None
                ))
            self.propose(AVGEPacket(packet,AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)))
            return self.generate_core_response()
        else:
            return self.generate_core_response(ResponseType.REQUIRES_QUERY, 
                                               {'query_type': 'atk', 'player_involved': self.player})
class EmptyEvent(AVGEEvent):
    def __init__(self,
                 catalyst_action: ActionTypes,
                 caller_card : AVGECard | None,
                 response_type : ResponseType = ResponseType.CORE,
                 response_data : Data | None = None):#effectively will either be CORE or SKIP, depending on the behavior you want
        super().__init__(response_type=response_type,
                         response_data=response_data,
        catalyst_action=catalyst_action,
        caller_card=caller_card)
        self.response_type = response_type
        self.response_data=response_data
    def core(self, args = {}):
        return Response(self, self.response_type, self.response_data)
    def invert_core(self, args ={}):
        return
    def package(self):
        return
    def generate_internal_listeners(self):
        return
class InputEvent(AVGEEvent):
    def __init__(self,
                 player_for : AVGEPlayer,
                 input_keys : list[str],#keys on which to attach inputs to. these should be UNIQUE, and when accessing, you are expected to use get(one_look = True)
                 input_type : InputType | list[InputType],#type of input
                 input_validation : Callable[[list[Any]], bool],#function that validates all inputs
                 catalyst_action : ActionTypes,
                 caller_card : AVGECard | None,#the caller card whose cache to use for inputs
                 query_data : Data | None = None):
        super().__init__(player_for=player_for,
                 input_keys=input_keys,
                 input_type=input_type,
                 input_validation=input_validation,
                 catalyst_action=catalyst_action,
                 caller_card=caller_card,
                 query_data=query_data)
        self.player_for = player_for
        self.input_keys = input_keys
        self.input_type = input_type
        self.input_validation = input_validation
        if(query_data is None):
            self.query_data = {}
        else:
            self.query_data = query_data
    def core(self, args : Data | None = None) -> Response:
        if(args is None):
            args = {}
        self.query_data["player_for"] = self.player_for
        if(self.input_type == InputType.SELECTION):
            allow_none = self.query_data.get("allow_none", False)
            allow_repeats = self.query_data.get("allow_repeats", False)
            self.query_data["allow_none"] = allow_none
            self.query_data["allow_repeats"] = allow_repeats

        if(not isinstance(args.get("input_result", []), list) 
           or len(args.get("input_result", [])) != len(self.input_keys)
           or not self.input_validation(args.get("input_result", []))):
            return self.generate_core_response(ResponseType.REQUIRES_QUERY,
                                               {'query_type': 'card_query',
                                                'input_type': self.input_type, 
                                                'num_inputs': len(self.input_keys),
                                                } | ({} if self.query_data is None else self.query_data))
        else:
            assert self.caller_card is not None
            env : AVGEEnvironment = self.caller_card.env
            input_result = args.get("input_result", [])
            
            if(input_result == None):
                return self.generate_core_response(ResponseType.FAST_FORWARD)
            if(self.input_type == InputType.SELECTION):
                valid = True
                display = self.query_data.get("display", None)#all the items that should be displayed. this may or may not be equivalent to targets
                targets = self.query_data.get("targets", None)
                assert isinstance(targets, list)
                assert isinstance(display, list)
                seen = []
                for i, res in enumerate(input_result):
                    allow_none = self.query_data.get("allow_none", False)
                    allow_repeats = self.query_data.get("allow_repeats", False)
                    if((res is None and not allow_none) or (res in seen and not allow_repeats)):
                        if(res not in targets):
                            valid = False
                            break
                    seen.append(res)
                if not valid:
                    return self.generate_core_response(ResponseType.REQUIRES_QUERY,
                                               {'query_type': 'card_query',
                                                'input_type': self.input_type, 
                                                'num_inputs': len(self.input_keys),
                                                } | ({} if self.query_data is None else self.query_data))
            else:
                if(not isinstance(self.input_type, list)):
                    self.input_type = [self.input_type] * len(self.input_keys)
                for i in range(len(input_result)):
                    match self.input_type[i]:
                        case InputType.D6:
                            if(not input_result[i] in [1,2,3,4,5,6]):
                                return self.generate_core_response(ResponseType.REQUIRES_QUERY,
                                                {'query_type': 'card_query',
                                                    'input_type': self.input_type, 
                                                    'num_inputs': len(self.input_keys),
                                                    } | ({} if self.query_data is None else self.query_data))
                        case InputType.COIN:
                            if(not input_result[i] in [0, 1] and isinstance(input_result[i], int)):
                                return self.generate_core_response(ResponseType.REQUIRES_QUERY,
                                                {'query_type': 'card_query',
                                                    'input_type': self.input_type, 
                                                    'num_inputs': len(self.input_keys),
                                                    } | ({} if self.query_data is None else self.query_data))
                        case InputType.BINARY:
                            if(not input_result[i] in [False, True] and isinstance(input_result[i], bool)):
                                return self.generate_core_response(ResponseType.REQUIRES_QUERY,
                                                {'query_type': 'card_query',
                                                    'input_type': self.input_type, 
                                                    'num_inputs': len(self.input_keys),
                                                    } | ({} if self.query_data is None else self.query_data))
                        case _:
                            continue
            #if got down here: passed all tests
            for i in range(len(input_result)):
                env.cache.set(self.caller_card, self.input_keys[i], input_result[i])
            return self.generate_core_response()
    def invert_core(self, args = None):
        assert self.caller_card is not None
        env : AVGEEnvironment = self.caller_card.env
        for key in self.input_keys:
            env.cache.delete(self.caller_card, key)
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"Input Event!"
class TurnEnd(AVGEEvent):
    def __init__(self,
                 environment : AVGEEnvironment,
                 catalyst_action : ActionTypes, 
                 caller_card : AVGECard | None):
        super().__init__(environment=environment,
                 catalyst_action=catalyst_action,
                 caller_card=caller_card)
        self.env = environment
    def core(self, args : Data | None = None) -> Response:
        from .avge_abstracts.AVGEEnvironment import GamePhase
        assert self.env is not None
        self.env.game_phase = GamePhase.TURN_END
        for player in self.env.players.values():
            player : AVGEPlayer = player
            player.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] = per_turn_token_add
            player.attributes[AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN] = per_turn_supporter
            player.attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN] = per_turn_swaps
            player.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = per_turn_atks
        self.env.player_turn = self.env.player_turn.opponent
        self.env.round_id += 1
        self.propose(AVGEPacket([PhasePickCard(self.env.player_turn,
                                   ActionTypes.ENV,
                                   None)],AVGEEngineID(None, ActionTypes.ENV, None)))
        return self.generate_core_response()
    def invert_core(self, args : Data | None = None):
        raise Exception("A phase should never be canceled")
    def generate_internal_listeners(self):
        return
    def package(self):
        return f"Ending Turn! Resetting all to default"
    
class PlayerInitEvent(AVGEEvent):
    _PLAYER_ACTIVE = "PLAYER_ACTIVE"
    _BENCH_ACTIVE_BASE = "_BENCH_"
    def __init__(self, player : AVGEPlayer):
        super().__init__(player=player,
                 catalyst_action=ActionTypes.ENV,
                 caller_card=None)
        self.player = player
    def core(self, args : Data | None = None) -> Response:
        active_key = PlayerInitEvent._PLAYER_ACTIVE
        keys = [active_key] + [PlayerInitEvent._BENCH_ACTIVE_BASE + str(i) for i in range(max_bench_size)]
        missing = object()
        vals = [self.player.env.cache.get(None, key, missing, True) for key in keys]
        chars = [card for card in self.player.cardholders[Pile.HAND] if isinstance(card, AVGECharacterCard)]
        if(vals[0] == missing or vals[0] is None):#active must not be none; others can be none
            return self.generate_core_response(ResponseType.INTERRUPT,{
                INTERRUPT_KEY: [
                    InputEvent(
                        self.player,
                        keys,
                        InputType.SELECTION,
                        lambda res : True,
                        ActionTypes.ENV,
                        None,
                        {
                            "query_label": "player_init",
                            "targets": chars,
                            "display": list(self.player.cardholders[Pile.HAND]),
                            "allow_none": True
                        }
                    )
                ]
            })
        assert isinstance(vals[0], AVGECharacterCard)
        active_card = vals[0]
        bench_cards = vals[1:]
        p : PacketType = [
            TransferCard(active_card,
                         self.player.cardholders[Pile.HAND],
                         self.player.cardholders[Pile.ACTIVE],
                         ActionTypes.ENV,
                         None),
        ]
        for card in bench_cards:
            if(card is not None):
                p.append(TransferCard(active_card,
                         self.player.cardholders[Pile.HAND],
                         self.player.cardholders[Pile.BENCH],
                         ActionTypes.ENV,
                         None))
        self.propose(AVGEPacket(p, AVGEEngineID(None, ActionTypes.ENV, None)))
        return self.generate_core_response()
