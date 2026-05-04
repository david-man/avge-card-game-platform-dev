from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, cast
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
                 core_notif : Notify | None,
                 caller : AVGECard | AVGEEnvironment | AVGEPlayer):
        super().__init__(target_card = target_card,
                         magnitude = magnitude,
                         modifier_type = modifier_type,
                         catalyst_action=catalyst_action,
                         caller=caller,
                         change_type=change_type,
                         core_notif=core_notif)
        self.magnitude = magnitude
        self.target_card = target_card
        self.change_type = change_type
        self.modifier_type = modifier_type
        self.old_amt = None
        self.final_change = None
        self.is_crit = False
    def modify_magnitude(self, change : int):
        #please use this function when modifying magnitudes, thanks!
        if(self.modifier_type != AVGEAttributeModifier.SET_STATE):
            if(self.magnitude == 0):#once a heal/dmg move hits 0, it can't be changed
                return
        self.magnitude += change
        self.magnitude = max(0, self.magnitude)
    def current_proposed_value(self):
        if(self.modifier_type == AVGEAttributeModifier.ADDITIVE):
            return min(self.target_card.hp + self.magnitude, self.target_card.max_hp)
        elif(self.modifier_type == AVGEAttributeModifier.SUBSTRACTIVE):
            return max(0, self.target_card.hp - self.magnitude)
        else:
            return self.magnitude
    def clamp_magnitude(self):
        if(self.modifier_type == AVGEAttributeModifier.ADDITIVE):
            self.magnitude = min(self.target_card.max_hp - self.target_card.hp, self.magnitude)
        elif(self.modifier_type == AVGEAttributeModifier.SUBSTRACTIVE):
            self.magnitude = min(self.target_card.hp, self.magnitude)
        else:
            self.magnitude = max(0, min(self.magnitude, self.target_card.max_hp))
    def core(self, args : dict | None = None) -> Response:
        self.old_amt = self.target_card.hp
        self.clamp_magnitude()
        self.target_card.hp = self.current_proposed_value()
        self.final_change = self.target_card.hp
        if(self.target_card.hp <= 0 and self.target_card.cardholder.pile_type != Pile.DISCARD):
            self.target_card.env.extend_event(
                [TransferCard(self.target_card,
                                                self.target_card.cardholder,
                                                self.target_card.player.cardholders[Pile.DISCARD],
                                                ActionTypes.ENV,
                                                self.caller,
                                                None)]
            )
        animation = None
        if(self.modifier_type == AVGEAttributeModifier.ADDITIVE and self.magnitude > 0):
            animation = Animation(
                [SoundEffect("sparkle.mp3"), ParticleExplosion(self.target_card, "regeneration.png")], all_players)
        elif(self.modifier_type == AVGEAttributeModifier.SUBSTRACTIVE and self.magnitude > 0):
            animation = Animation([SoundEffect("punch.mp3")], all_players)
            if(self.is_crit):
                animation = Animation([SoundEffect("heavy_punch.mp3"), ParticleExplosion(self.target_card, "crit.png")], all_players)
        if(self.core_notif is None):
            return Response(ResponseType.CORE, Data(), animation)
        return Response(ResponseType.CORE, self.core_notif, animation)
    
    def invert_core(self, args : dict | None = None):
        assert(not self.old_amt is None)
        self.target_card.hp = self.old_amt

    def generate_internal_listeners(self):
        from .internal_listeners import AVGEHPChangeAssessment, AVGEWeaknessModifier
        from .catalog.status_effects.Maid import MaidStatusDamageShieldModifier
        self.attach_listener(AVGEHPChangeAssessment(self.target_card.env))
        self.attach_listener(AVGEWeaknessModifier(self.target_card.env))
        self.attach_listener(MaidStatusDamageShieldModifier(self.target_card.env))

        
class AVGECardMaxHPChange(AVGEEvent):
    def __init__(self,
                 target_card : AVGECharacterCard,
                 magnitude : int,
                 modifier_type : AVGEAttributeModifier,
                 catalyst_action : ActionTypes,
                 core_notif : Notify | None,
                 caller : AVGECard | AVGEEnvironment | AVGEPlayer):
        super().__init__(target_card = target_card,
                         magnitude = magnitude,
                         modifier_type = modifier_type,
                         catalyst_action=catalyst_action,
                         caller=caller,
                         core_notif=core_notif)
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
    
    def core(self, args : dict | None = None) -> Response:
        self.old_max = self.target_card.max_hp
        self.old_hp = self.target_card.hp
        self.target_card.max_hp = self.current_proposed_value()
        self.target_card.hp = min(self.target_card.hp, self.target_card.max_hp)
        if(self.core_notif is None):
            return Response(ResponseType.CORE, Data())
        return Response(ResponseType.CORE, self.core_notif)
    
    def invert_core(self, args : dict | None = None):
        assert(not self.old_hp is None)
        assert(not self.old_max is None)
        self.target_card.hp = self.old_hp
        self.target_card.max_hp = self.old_max

    def generate_internal_listeners(self):
        from .internal_listeners import AVGEMaxHPChangeAssessment
        self.attach_listener(AVGEMaxHPChangeAssessment(self.target_card.env))
        return

    
class AVGECardTypeChange(AVGEEvent):
    def __init__(self,
                 target_card : AVGECharacterCard,
                 new_type : CardType,
                 catalyst_action : ActionTypes,
                 caller : AVGECard | AVGEEnvironment | AVGEPlayer,
                 core_notif : Notify | None):
        super().__init__(target_card=target_card,
                         new_type=new_type,
                         catalyst_action=catalyst_action,
                         caller=caller,
                         core_notif=core_notif)
        self.target_card = target_card
        self.new_type = new_type
        self.old_type = None
    def core(self, args :dict | None = None) -> Response:
        self.old_type = self.target_card.card_type
        self.target_card.card_type = self.new_type
        if(self.core_notif is None):
            return Response(ResponseType.CORE, Data())
        return Response(ResponseType.CORE, self.core_notif)
    
    def invert_core(self, args : dict | None = None):
        assert(not self.old_type is None)
        self.target_card.card_type = self.old_type

    def generate_internal_listeners(self):
        return

class AVGECardStatusChange(AVGEEvent):
    def __init__(self,
                 status_effect : StatusEffect,
                 change_type : StatusChangeType,
                 target : AVGECharacterCard,
                 catalyst_action : ActionTypes,
                 caller : AVGECard | AVGEEnvironment | AVGEPlayer,
                 core_notif : Notify | None):
        #caller card is the one who gives the effect. None when ENV
        super().__init__(status_effect=status_effect,change_type=change_type,target=target,catalyst_action=catalyst_action,caller=caller,core_notif=core_notif)
        self.status_effect = status_effect
        self.target = target
        self.change_type = change_type

        self.made_change = True
        self._old = []
    def core(self, args = None) -> Response:
        if(self.change_type == StatusChangeType.ADD):
            if(self.caller not in self.target.statuses_attached[self.status_effect]):
                self.target.statuses_attached[self.status_effect].append(self.caller)
                if(isinstance(self.caller, AVGECharacterCard)):
                    self.caller.statuses_responsible[self.status_effect].append(self.target)
            else:
                self.made_change = False
        elif(self.change_type == StatusChangeType.ERASE):
            if(self.caller in self.target.statuses_attached[self.status_effect]):
                self.target.statuses_attached[self.status_effect].remove(self.caller)
                if(isinstance(self.caller, AVGECharacterCard)):
                    self.caller.statuses_responsible[self.status_effect].remove(self.target)
            else:
                self.made_change = False
        elif(self.change_type == StatusChangeType.REMOVE):
            if(len(self.target.statuses_attached[self.status_effect]) == 0):
                self.made_change = False
            else:
                self._old = self.target.statuses_attached[self.status_effect]
                for card in self.target.statuses_attached[self.status_effect]:
                    if(isinstance(card, AVGECharacterCard)):
                        card.statuses_responsible[self.status_effect].remove(self.target)
                self.target.statuses_attached[self.status_effect] = []
        if(self.core_notif is None):
            return Response(ResponseType.CORE, Data())
        return Response(ResponseType.CORE, self.core_notif)
    def invert_core(self, args = None):
        if(not self.made_change):
            return
        if(self.change_type == StatusChangeType.ADD):
            self.target.statuses_attached[self.status_effect].remove(self.caller)
            if(isinstance(self.caller, AVGECharacterCard)):
                self.caller.statuses_responsible[self.status_effect].remove(self.target)
        elif(self.change_type == StatusChangeType.ERASE):
            self.target.statuses_attached[self.status_effect].append(self.caller)
            if(isinstance(self.caller, AVGECharacterCard)):
                self.caller.statuses_responsible[self.status_effect].append(self.target)
        elif(self.change_type == StatusChangeType.REMOVE):
            self.target.statuses_attached[self.status_effect] = self._old
            for card in self.target.statuses_attached[self.status_effect]:
                if(isinstance(card, AVGECharacterCard)):
                    card.statuses_responsible[self.status_effect].append(self.target)
    def generate_internal_listeners(self):
        return

class AVGEEnergyTransfer(AVGEEvent):
    def __init__(self,
                 token : EnergyToken,
                 source : AVGEPlayer | AVGECharacterCard | AVGEEnvironment,
                 target : AVGEPlayer | AVGECharacterCard | AVGEEnvironment,
                 catalyst_action : ActionTypes, 
                 caller : AVGECard | AVGEEnvironment | AVGEPlayer,
                 core_notif : Notify | None):
        super().__init__(token=token,source = source, target=target, catalyst_action=catalyst_action, caller=caller,core_notif=core_notif)
        self.token = token
        self.source = source
        self.target = target
    def core(self, args = None) -> Response:
        self.token.detach()
        self.token.attach(self.target)
        animation = Animation([SoundEffect("play_chip.ogg")], all_players)
        if(self.core_notif is None):
            return Response(ResponseType.CORE, Data(), animation)
        return Response(ResponseType.CORE, self.core_notif, animation)
    def invert_core(self, args = None):
        self.token.detach()
        self.token.attach(self.source)

    def generate_internal_listeners(self):
        from .internal_listeners import AVGETokenTransferAssessment
        from .avge_abstracts.AVGEEnvironment import AVGEEnvironment
        if(isinstance(self.caller, (AVGEEnvironment))):
            self.attach_listener(AVGETokenTransferAssessment(self.caller))
        else:
            self.attach_listener(AVGETokenTransferAssessment(self.caller.env))

class AVGEPlayerAttributeChange(AVGEEvent):
    def __init__(self, 
                 target_player : AVGEPlayer, #can be delayed to runtime if wanted
                 attribute : AVGEPlayerAttribute,
                 magnitude : int, #can be delayed to runtime if wanted
                 attribute_modifier_type : AVGEAttributeModifier,
                 catalyst_action : ActionTypes, 
                 caller : AVGECard | AVGEEnvironment | AVGEPlayer,
                 core_notif : Notify | None):
        super().__init__(target_player=target_player,
                 attribute=attribute,
                 magnitude=magnitude,
                 attribute_modifier_type=attribute_modifier_type,
                 catalyst_action=catalyst_action,
                 caller=caller,core_notif=core_notif)
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
        if(self.core_notif is None):
            return Response(ResponseType.CORE, Data())
        return Response(ResponseType.CORE, self.core_notif)
    
    def invert_core(self, args = None):
        assert self.old_amt is not None
        self.target_player.attributes[self.attribute] = self.old_amt

    def generate_internal_listeners(self):
        from .internal_listeners import AVGEPlayerAttributeChangePostChecker
        self.attach_listener(AVGEPlayerAttributeChangePostChecker(self.target_player.env))


class TransferCard(AVGEEvent):
    _ACTIVE_REPLACE_KEY = "internal_active_replace_pick"
    _PRE_TRANSFER = "pre_transfer"
    _TRANSFER = "transfer"
    _POST_TRANSFER = "post_transfer"
    def __init__(self, 
                 card : AVGECard, #can be delayed to runtime if wanted
                 pile_from : AVGECardholder, #can be delayed to runtime if wanted
                 pile_to : AVGECardholder, #can be delayed to runtime if wanted
                 catalyst_action : ActionTypes, 
                 caller : AVGECard | AVGEEnvironment | AVGEPlayer,
                 core_notif : Notify | None,
                 new_idx : int | None= None, #can be delayed to runtime if wanted
                 energy_requirement : int = 0,
                 ):
        super().__init__(card=card,
                 pile_from=pile_from,
                 pile_to=pile_to,
                 catalyst_action=catalyst_action,
                 caller=caller,
                 new_idx=new_idx,
                 core_notif=core_notif)
        self.card = card
        self.pile_to = pile_to
        self.pile_from = pile_from
        self.new_idx = new_idx
        self.old_idx = None
        self.energy_requirement = energy_requirement
        self._previous_card = None#only for tools

    
    def core(self, args :dict | None = None) -> Response:
        if(self.temp_cache.get(self._PRE_TRANSFER, None) is None):
            """
            STAGE 1: PRE TRANSFER
            """
            self.old_idx = self.pile_from.get_posn(self.card)
            to_dos : PacketType = []

            #tool, stadium discard
            if(self.pile_from.pile_type == Pile.TOOL and isinstance(self.card, AVGEToolCard)):
                temp = self.card.deactivate_card()
                if(temp is not None):
                    to_dos.extend(temp)
            if(self.pile_from.pile_type == Pile.STADIUM and isinstance(self.card, AVGEStadiumCard)):
                temp = self.card.deactivate_card()
                if(temp is not None):
                    to_dos.extend(temp)
            #character setup for discard
            if(self.pile_from.pile_type in [Pile.ACTIVE, Pile.BENCH] and isinstance(self.card, AVGECharacterCard) 
            and self.pile_to.pile_type not in [Pile.ACTIVE, Pile.BENCH]):
                #find the replacement for active
                if(self.pile_from.pile_type == Pile.ACTIVE and self.temp_cache.get("CARD_REPLACED", None) is None):
                    if(len(self.card.player.cardholders[Pile.BENCH]) == 0):
                        e : AVGEEnvironment = self.card.env
                        e.winner = self.card.player.opponent
                        return Response(ResponseType.GAME_END, GameEnd(e.winner.unique_id, "KO and no cards left on bench"))
                    else:
                        swap_with = self.card.env.cache.get(
                            None,
                            TransferCard._ACTIVE_REPLACE_KEY,
                            None,
                            True
                        )
                        if(swap_with is None):
                            return Response(ResponseType.INTERRUPT,
                                            Interrupt[InputEvent](
                                                [
                                                InputEvent(
                                                    self.card.player,
                                                    [TransferCard._ACTIVE_REPLACE_KEY],
                                                    lambda r : True,
                                                    self.catalyst_action,
                                                    self.card.env,
                                                    CardSelectionQuery(
                                                        "Choose a benched character to switch the KO'd character with: ",
                                                        list(self.card.player.cardholders[Pile.BENCH]),
                                                        list(self.card.player.cardholders[Pile.BENCH]),
                                                        False,
                                                        False
                                                    )
                                                )
                                            ]
                                            ))
                        to_dos.append(TransferCard(swap_with,
                                            self.card.player.cardholders[Pile.BENCH],
                                            self.card.player.cardholders[Pile.ACTIVE],
                                            self.catalyst_action,
                                            self.caller,
                                            None))#propose the swap from the bench first, and then propose the discard
                        if(self.pile_to.pile_type == Pile.DISCARD):
                            to_dos.append(AVGEPlayerAttributeChange(self.card.player.opponent,
                                                                    AVGEPlayerAttribute.KO_COUNT,
                                                                    1,
                                                                    AVGEAttributeModifier.ADDITIVE,
                                                                    self.catalyst_action,
                                                                    self.caller,
                                                                    None))
                        self.temp_cache["CARD_REPLACED"] = True
                #discard tools
                def packet_1():
                    assert isinstance(self.card, AVGECharacterCard)
                    packet : PacketType = [TransferCard(tool,
                                                self.card.tools_attached,
                                                self.pile_to,
                                                self.catalyst_action,
                                                self.card.env,
                                                None) for tool in self.card.tools_attached]
                    return packet
                #drop the energy
                def packet_2():
                    assert isinstance(self.card, AVGECharacterCard)
                    packet : PacketType = [AVGEEnergyTransfer(token,
                                                self.card,
                                                self.card.env,
                                                self.catalyst_action,
                                                self.card.env,
                                                None) for token in self.card.energy]
                    return packet
                #drop the statuses
                def packet_3():
                    assert isinstance(self.card, AVGECharacterCard)
                    packet : PacketType = []
                    #drop all statuses
                    for status_effect in self.card.statuses_attached.keys():
                        packet.append(AVGECardStatusChange(
                            status_effect,
                            StatusChangeType.REMOVE,
                            self.card,
                            self.catalyst_action,
                            self.card.env,
                            None
                        ))
                    return packet
                def packet_4():
                    assert isinstance(self.card, AVGECharacterCard)
                    packet : PacketType= []
                    for status in self.card.statuses_responsible:
                        for card in self.card.statuses_responsible[status]:
                            assert isinstance(card, AVGECharacterCard)
                            packet.append(AVGECardStatusChange(
                                status,
                                StatusChangeType.ERASE,
                                card,
                                self.catalyst_action,
                                self.card,
                                None
                            ))
                    return packet
                #reset HP/MAXHP
                def packet_5():
                    assert isinstance(self.card, AVGECharacterCard)
                    packet : PacketType = []
                    packet.append(AVGECardMaxHPChange(
                        self.card,
                        self.card.default_max_hp,
                        AVGEAttributeModifier.SET_STATE,
                        self.catalyst_action,
                        None,
                        self.card.env
                    ))
                    packet.append(AVGECardHPChange(
                        self.card,
                        self.card.default_max_hp,
                        AVGEAttributeModifier.SET_STATE,
                        CardType.ALL,
                        self.catalyst_action,
                        None,
                        self.card.env
                    ))
                    return packet
                temp = self.card.deactivate_card()
                if(temp is not None):
                    to_dos.extend(temp)
                to_dos.extend([packet_1, packet_2, packet_3, packet_4, packet_5])
            self.temp_cache[self._PRE_TRANSFER] = True
            if(len(to_dos) > 0):
                return Response(ResponseType.INTERRUPT, Interrupt(
                    to_dos
                ))
        
        if(self.temp_cache.get(self._TRANSFER, None) is None):
            """
            STAGE 2: TRANSFER
            """
            if(isinstance(self.card, AVGEToolCard)):
                self._previous_card = self.card.card_attached
            self.card.env.transfer_card(self.card, self.pile_from, self.pile_to, self.new_idx)
            self.temp_cache[self._TRANSFER] = True
        if(self.temp_cache.get(self._POST_TRANSFER, None) is None):
            """
            STAGE 3: POST-TRANSFER
            """
            to_dos : PacketType= [] 
            if(self.pile_to.pile_type == Pile.TOOL and isinstance(self.card, AVGEToolCard) and self.pile_from.pile_type != Pile.TOOL):
                #on tool attachment
                packet : PacketType = [PlayNonCharacterCard(
                    self.card,
                    self.catalyst_action,
                    self.card,
                )]
                to_dos.extend(packet)

            if(self.pile_to.pile_type == Pile.STADIUM and isinstance(self.card, AVGEStadiumCard) and self.pile_from.pile_type != Pile.STADIUM):
                #on stadium attachment
                packet : PacketType = [PlayNonCharacterCard(
                    self.card,
                    self.catalyst_action,
                    self.card,
                )]
                to_dos.extend(packet)

            if(self.pile_to.pile_type in [Pile.ACTIVE, Pile.BENCH] and isinstance(self.card, AVGECharacterCard) and self.pile_from.pile_type not in [Pile.ACTIVE, Pile.BENCH]):
                #on card activation
                if(self.card.has_passive):
                    packet : PacketType = [PlayCharacterCard(
                        self.card,
                        ActionTypes.PASSIVE,
                        self.catalyst_action,
                        self.card
                    )]
                    to_dos.extend(packet)

            self.temp_cache[self._POST_TRANSFER] = True
            if(len(to_dos) > 0):
                self.card.env.extend_event(to_dos)

        animation = Animation([SoundEffect("card_shove.ogg")], all_players)
        if(self.catalyst_action == ActionTypes.PLAYER_CHOICE):
            animation = Animation([SoundEffect("card_slide.ogg")], all_players)
        if(self.core_notif is None):
            return Response(ResponseType.CORE, Data(), animation)
        return Response(ResponseType.CORE, self.core_notif, animation)
    
    def invert_core(self, args : dict | None = None):
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
        from .avge_abstracts.AVGEEnvironment import AVGEEnvironment
        if(isinstance(self.caller, AVGEEnvironment)):
            self.attach_listener(AVGETransferValidityCheck(self.caller))
            self.attach_listener(AVGETransferEnergyRequirementReactor(self.caller))
        else:
            self.attach_listener(AVGETransferValidityCheck(self.caller.env))
            self.attach_listener(AVGETransferEnergyRequirementReactor(self.caller.env))
    

class ReorderCardholder(AVGEEvent):
    def __init__(self,
                 cardholder : AVGECardholder,
                 new_order : list[str], #can be delayed to runtime if wanted
                 catalyst_action : ActionTypes, 
                 caller : AVGECard | AVGEEnvironment | AVGEPlayer,
                 core_notif : Notify | None):
        super().__init__(cardholder=cardholder,
                 new_order=new_order,
                 catalyst_action=catalyst_action,
                 caller=caller,
                 core_notif=core_notif)
        self.cardholder = cardholder
        self.new_order = new_order
        self.original_order = [k for k in self.cardholder.get_order()]#copies order
    def core(self, args : dict | None = None) -> Response:
        self.cardholder.reorder(self.new_order)
        animation = Animation([SoundEffect("shuffle_deck.wav")], all_players)
        if(self.core_notif is None):
            return Response(ResponseType.CORE, Data(), animation)
        return Response(ResponseType.CORE, self.core_notif, animation)
    def invert_core(self, args : dict | None = None):
        self.cardholder.reorder(self.original_order)
    def generate_internal_listeners(self):
        return

#In PlayCharacter & PlayNoncharacter Card, the caller card should always be either set to the card itself or a card that is appropriating that card's ability
        
#In addition, if a card requires an input, it is expected that they use the InputEvent. Don't use args
    
class PlayCharacterCard(AVGEEvent):
    def __init__(self, 
                 card : AVGECharacterCard,
                 card_action : ActionTypes,
                 catalyst_action : ActionTypes, 
                 caller : AVGECharacterCard,
                 energy_requirement : int = 0):
        super().__init__(card=card,
                 card_action=card_action,
                 catalyst_action=catalyst_action,
                 caller=caller,
                 energy_requirement=energy_requirement,
                 core_notif=None)
        self.card = card
        self.card_action = card_action
        self.cache_snapshot = None
        self.energy_requirement = energy_requirement
    def core(self, args : dict | None = None) -> Response:
        if(args is None):
            args = {}
        if(self.card_action == ActionTypes.SKIP):
            if(self.core_notif is None):
                return Response(ResponseType.CORE, Data())
            return Response(ResponseType.CORE, self.core_notif)
        else:
            args['type'] = self.card_action
            args['caller_type'] = self.catalyst_action
            assert isinstance(self.caller, AVGECharacterCard)
            return self.card.play_card(self.caller, args)
    def invert_core(self, args : dict | None = None):
        return
    def generate_internal_listeners(self):
        from .internal_listeners import AVGEPlayCharacterCardValidityCheck
        self.attach_listener(AVGEPlayCharacterCardValidityCheck(self.card.env))
class PlayNonCharacterCard(AVGEEvent):
    def __init__(self, 
                 card : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard,
                 catalyst_action : ActionTypes, 
                 caller : AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard):
        super().__init__(card=card,
                 catalyst_action=catalyst_action,
                 caller=caller,
                 core_notif=None)
        self.card = card
    def core(self, args : dict | None = None) -> Response:
        if(isinstance(self.card, (AVGEToolCard, AVGEStadiumCard))):
            if(not self.card == self.caller):
                raise Exception("Tried to appropriate an ability that can't be appropriated")
            return self.card.play_card()
        else:
            assert isinstance(self.caller, (AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard))
            return self.card.play_card(self.caller)
    def invert_core(self, args : dict | None = None):
        return
    def generate_internal_listeners(self):
        from .internal_listeners import AVGEPlayNonCharacterCardValidityCheck
        self.attach_listener(AVGEPlayNonCharacterCardValidityCheck(self.card.env))
class PhasePickCard(AVGEEvent):
    def __init__(self, 
                 env : AVGEEnvironment,
                 catalyst_action : ActionTypes, 
                 caller : AVGECard | AVGEEnvironment | AVGEPlayer):
        self.env = env
        super().__init__(env=env,
                 catalyst_action=catalyst_action,
                 caller=caller,
                 core_notif = None)
    def core(self, args : dict | None = None) -> Response:
        player = self.env.player_turn
        if(len(player.cardholders[Pile.DECK]) > 0):
            deck = player.cardholders[Pile.DECK]
            hand = player.cardholders[Pile.HAND]
            top_card = deck.peek()
            player.env.extend([TransferCard(top_card,
                                      deck,
                                      hand,
                                      ActionTypes.ENV,
                                      self.env,
                                      None)])
            self.propose(AVGEPacket([Phase2(self.env,
                                             ActionTypes.ENV,
                                             self.env)], AVGEEngineID(self.env, ActionTypes.ENV, None)))
            return Response(ResponseType.CORE, Data())
        else:
            self.propose(AVGEPacket([Phase2(self.env,
                                             ActionTypes.ENV,
                                             self.env)], AVGEEngineID(self.env, ActionTypes.ENV, None)))
            return Response(ResponseType.CORE, Data())
            # self.player.env.winner = self.player.opponent
            # return self.generate_core_response(ResponseType.GAME_END, {"winner": self.player.opponent, "reason": "no cards left to draw"})
    def invert_core(self, args : dict | None = None):
        raise Exception("A phase should never be canceled")
    def generate_internal_listeners(self):
        return
    
class Phase2(AVGEEvent):
    def __init__(self, 
                 env : AVGEEnvironment,
                 catalyst_action : ActionTypes, 
                 caller : AVGECard | AVGEEnvironment | AVGEPlayer):
        super().__init__(env=env,
                         catalyst_action=catalyst_action,
                         caller=caller,
                         core_notif = None)
        self.env = env
    def core(self, args : dict | None = None) -> Response:
        from .avge_abstracts.AVGEEnvironment import GamePhase
        if(args is None):
            args = {}
        env : AVGEEnvironment = self.env
        player  = self.env.player_turn
        env.game_phase = GamePhase.PHASE_2
        active_card : AVGECharacterCard = cast(AVGECharacterCard, env.get_active_card(player.unique_id))
        next_action = args.get('next', "")

        if(next_action == 'atk'):
            if(env.round_id == 0):
                env.game_phase = GamePhase.TURN_END
                self.propose(AVGEPacket([TurnEnd(env,
                                  ActionTypes.PLAYER_CHOICE,
                                  env)], AVGEEngineID(self.env.player_turn, ActionTypes.PLAYER_CHOICE, None)))
            else:
                env.game_phase = GamePhase.ATK_PHASE
                self.propose(AVGEPacket([AtkPhase(self.env,
                                    ActionTypes.PLAYER_CHOICE,
                                    self.env.player_turn)], AVGEEngineID(self.env.player_turn, ActionTypes.PLAYER_CHOICE, None)))
            return Response(ResponseType.CORE, Data())

        elif(next_action == 'tool'):
            tool = args.get('tool')
            attach_to = args.get('attach_to')
            if(isinstance(tool, AVGEToolCard)
               and tool in player.cardholders[Pile.HAND]
               and isinstance(attach_to, AVGECharacterCard)):
                packet = []
                packet.append(TransferCard(tool,
                                       player.cardholders[Pile.HAND],
                                       attach_to.tools_attached,
                                       ActionTypes.PLAYER_CHOICE,
                                       self.env.player_turn,
                                       None))
                if(len(attach_to.tools_attached) > 0):
                    packet.append(TransferCard(attach_to.tools_attached.peek(),
                                               attach_to.tools_attached,
                                               player.cardholders[Pile.DISCARD],
                                               ActionTypes.PLAYER_CHOICE,
                                               self.env.player_turn,
                                               None))
                self.propose(AVGEPacket(packet, AVGEEngineID(self.env.player_turn, ActionTypes.PLAYER_CHOICE, None)))
                return Response(ResponseType.CORE, Data())

        elif(next_action == 'supporter'):
            supporter_card = args.get('supporter_card')
            if(isinstance(supporter_card, AVGESupporterCard)
               and supporter_card in player.cardholders[Pile.HAND]):
                event_1 = PlayNonCharacterCard(supporter_card,
                                               ActionTypes.PLAYER_CHOICE,
                                               supporter_card)
                event_2 = AVGEPlayerAttributeChange(
                    player,
                    AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN,
                    1,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    ActionTypes.PLAYER_CHOICE,
                    self.env.player_turn,
                    None
                )
                event_3 = TransferCard(supporter_card,
                                       supporter_card.cardholder,
                                       supporter_card.player.cardholders[Pile.DISCARD],
                                       ActionTypes.PLAYER_CHOICE,
                                       self.env.player_turn,
                                       None)
                self.propose(AVGEPacket([event_1, event_2, event_3], AVGEEngineID(self.env.player_turn, ActionTypes.PLAYER_CHOICE, None)))
                return Response(ResponseType.CORE, Data())

        elif(next_action == 'item'):
            item_card = args.get('item_card')
            if(isinstance(item_card, AVGEItemCard)
               and item_card in player.cardholders[Pile.HAND]):
                packet = []
                packet.append(PlayNonCharacterCard(item_card,
                                                   ActionTypes.PLAYER_CHOICE,
                                                   item_card))
                packet.append(TransferCard(item_card,
                                           item_card.cardholder,
                                           item_card.player.cardholders[Pile.DISCARD],
                                           ActionTypes.PLAYER_CHOICE,
                                           self.env.player_turn,
                                           None))
                self.propose(AVGEPacket(packet,AVGEEngineID(self.env.player_turn, ActionTypes.PLAYER_CHOICE, None)))
                return Response(ResponseType.CORE, Data())

        elif(next_action == 'stadium'):
            stadium_card = args.get('stadium_card')
            if(isinstance(stadium_card, AVGEStadiumCard)
               and stadium_card in player.cardholders[Pile.HAND]):
                packet = []
                packet.append(TransferCard(stadium_card,
                                           player.cardholders[Pile.HAND],
                                           env.stadium_cardholder,
                                           ActionTypes.PLAYER_CHOICE,
                                           self.env.player_turn,
                                           None))
                if(len(env.stadium_cardholder) > 0):
                    old_stadium : AVGEStadiumCard = cast(AVGEStadiumCard, env.stadium_cardholder.peek())
                    packet.append(TransferCard(old_stadium,
                                               env.stadium_cardholder,
                                               old_stadium.player.cardholders[Pile.DISCARD],
                                               ActionTypes.PLAYER_CHOICE,
                                               self.env.player_turn,
                                               None))
                self.propose(AVGEPacket(packet,AVGEEngineID(self.env.player_turn, ActionTypes.PLAYER_CHOICE, None)))
                return Response(ResponseType.CORE, Data())

        elif(next_action == 'swap'):
            bench_card = args.get('bench_card')
            if(isinstance(bench_card, AVGECharacterCard)
               and bench_card in player.cardholders[Pile.BENCH]):
                event_1 = TransferCard(bench_card,
                                       player.cardholders[Pile.BENCH],
                                       player.cardholders[Pile.ACTIVE],
                                       ActionTypes.PLAYER_CHOICE,
                                       self.env.player_turn,
                                       None)
                event_2 = TransferCard(active_card,
                                       player.cardholders[Pile.ACTIVE],
                                       player.cardholders[Pile.BENCH],
                                       ActionTypes.PLAYER_CHOICE,
                                       self.env.player_turn,
                                       None,
                                       energy_requirement=active_card.retreat_cost)
                event_3 = AVGEPlayerAttributeChange(
                    player,
                    AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN,
                    1,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    ActionTypes.PLAYER_CHOICE,
                    self.env.player_turn,
                    None
                )
                self.propose(AVGEPacket([event_1, event_2, event_3],AVGEEngineID(self.env.player_turn, ActionTypes.PLAYER_CHOICE, None)))
                return Response(ResponseType.CORE, Data())

        elif(next_action == 'energy'):
            attach_to = args.get('attach_to')
            if(isinstance(attach_to, AVGECharacterCard)):
                if(len(player.env.energy) > 0):
                    requested_token = args.get('token')
                    token = requested_token if isinstance(requested_token, EnergyToken) and requested_token in player.env.energy else player.env.energy[0]
                    event = AVGEEnergyTransfer(token,
                                               player.env,
                                               attach_to,
                                               ActionTypes.PLAYER_CHOICE,
                                               self.env.player_turn,
                                               None)
                    event_2 = AVGEPlayerAttributeChange(player,
                                               AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN,
                                               1,
                                               AVGEAttributeModifier.SUBSTRACTIVE,
                                               ActionTypes.ENV,
                                               self.env.player_turn,
                                               None)
                    self.propose(AVGEPacket([event, event_2],AVGEEngineID(self.env.player_turn, ActionTypes.PLAYER_CHOICE, None)))
                else:
                    return Response(ResponseType.CORE, Notify("You don't have enough energy!", [player.unique_id], None))
                return Response(ResponseType.CORE, Data())

        elif(next_action == 'hand2bench'):
            hand2bench_card = args.get('hand2bench')
            if(isinstance(hand2bench_card, AVGECharacterCard)
               and hand2bench_card in player.cardholders[Pile.HAND]):
                packet = []
                packet.append(TransferCard(hand2bench_card,
                                           player.cardholders[Pile.HAND],
                                           player.cardholders[Pile.BENCH],
                                           ActionTypes.PLAYER_CHOICE,
                                           self.env.player_turn,
                                           None))
                self.propose(AVGEPacket(packet,AVGEEngineID(self.env.player_turn, ActionTypes.PLAYER_CHOICE, None)))
                return Response(ResponseType.CORE, Data())

        return Response(ResponseType.REQUIRES_QUERY, Phase2Data(player.unique_id))
    def invert_core(self, args : dict | None = None):
        raise Exception("A phase should never be canceled")
    def generate_internal_listeners(self):
        return
    
class AtkPhase(AVGEEvent):
    def __init__(self, 
                 env : AVGEEnvironment,
                 catalyst_action : ActionTypes, 
                 caller : AVGECard | AVGEEnvironment | AVGEPlayer):
        super().__init__(env=env,
                 catalyst_action=catalyst_action,
                 caller=caller,
                 core_notif = Notify(f"{env.player_turn.username} is now attacking!", [PlayerID.P1, PlayerID.P2],  5))
        self.env = env
    def generate_internal_listeners(self):
        return
    def invert_core(self, args : dict | None = None):
        raise Exception("A phase should never be canceled")
    def core(self, args : dict | None = None) -> Response:
        from .avge_abstracts.AVGEEnvironment import GamePhase
        if(args is None):
            args = {}
        env : AVGEEnvironment = self.env
        player  = self.env.player_turn
        env.game_phase = GamePhase.ATK_PHASE
        active_card = env.get_active_card(player.unique_id)
        assert isinstance(active_card, AVGECharacterCard)
        atk_type = args.get('type')
        if(atk_type == ActionTypes.ATK_1 or atk_type == ActionTypes.ATK_2):
            if(atk_type == ActionTypes.ATK_1 and active_card.atk_1_name is not None or
               atk_type == ActionTypes.ATK_2 and active_card.atk_2_name is not None):
                packet = []
                packet.append(PlayCharacterCard(
                    cast(AVGECharacterCard, active_card),
                    atk_type,
                    ActionTypes.PLAYER_CHOICE,
                    cast(AVGECharacterCard, active_card),
                    active_card.atk_1_cost if atk_type==ActionTypes.ATK_1 else active_card.atk_2_cost,
                ))
                packet.append(AVGEPlayerAttributeChange(
                    env.player_turn,
                    AVGEPlayerAttribute.ATTACKS_LEFT,
                    1,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    ActionTypes.ENV,
                    self.env,
                    None
                ))# --> need a better way to figure out end of attack than this. this runs into the issue where the actual contents of the atk itself get SKIPPED, but the player still loses their attack
                self.propose(AVGEPacket(packet,AVGEEngineID(self.env.player_turn, ActionTypes.PLAYER_CHOICE, None)))
                return Response(ResponseType.CORE, Data())
            return Response(ResponseType.REQUIRES_QUERY, AtkPhaseData(player.unique_id))
        elif(atk_type == ActionTypes.SKIP):
            packet = []
            packet.append(AVGEPlayerAttributeChange(
                    env.player_turn,
                    AVGEPlayerAttribute.ATTACKS_LEFT,
                    0,
                    AVGEAttributeModifier.SET_STATE,
                    ActionTypes.ENV,
                    self.env,
                    None
                ))
            self.propose(AVGEPacket(packet,AVGEEngineID(self.env.player_turn, ActionTypes.PLAYER_CHOICE, None)))
            return Response(ResponseType.CORE, Data())
        else:
            return Response(ResponseType.REQUIRES_QUERY, AtkPhaseData(player.unique_id))
class EmptyEvent(AVGEEvent):
    def __init__(self,
                 catalyst_action: ActionTypes,
                 caller: AVGECard | AVGEEnvironment | AVGEPlayer,
                 response_type : ResponseType,
                 response_data : Data):#effectively will either be CORE or SKIP, depending on the behavior you want
        super().__init__(response_type=response_type,
                         response_data=response_data,
        catalyst_action=catalyst_action,
        caller=caller,
        core_notif = None)
        self.response_type = response_type
        self.response_data=response_data
    def core(self, args = {}):
        return Response(self.response_type, self.response_data)
    def invert_core(self, args ={}):
        return
    def generate_internal_listeners(self):
        return
class InputEvent(AVGEEvent):
    def __init__(self,
                 player_for : AVGEPlayer,
                 input_keys : list[str],#keys on which to attach inputs to. these should be UNIQUE, and when accessing, you are expected to use get(one_look = True)
                 input_validation : Callable[[list[Any]], bool],#function that validates all inputs
                 catalyst_action : ActionTypes,
                 caller : AVGECard | AVGEEnvironment | AVGEPlayer,#the caller whose cache to use
                 query_data : Data):
        super().__init__(player_for=player_for,
                 input_keys=input_keys,
                 input_validation=input_validation,
                 catalyst_action=catalyst_action,
                 caller=caller,
                 query_data=query_data,
                 core_notif = None)
        self.player_for = player_for
        self.input_keys = input_keys
        self.input_validation = input_validation
        self.query_data = query_data

    def _requires_query_response(self) -> Response:
        return Response(ResponseType.REQUIRES_QUERY, self.query_data)

    def _validate_with_query_data(self, input_result: list[Any]) -> bool:
        if isinstance(self.query_data, CardSelectionQuery):
            targets = list(self.query_data.targets)
            if self.query_data.allows_none:
                targets = targets + [None]
            seen_cards: list[AVGECard] = []
            for value in input_result:
                if value not in targets:
                    return False
                if value is None:
                    continue
                if (not self.query_data.allows_repeat) and value in seen_cards:
                    return False
                if isinstance(value, AVGECard):
                    seen_cards.append(value)
            return True

        if isinstance(self.query_data, StrSelectionQuery):
            targets = list(self.query_data.targets)
            if self.query_data.allows_none:
                targets = targets + [None]
            seen_items: list[str] = []
            for value in input_result:
                if value not in targets:
                    return False
                if value is None:
                    continue
                if not isinstance(value, str):
                    return False
                if (not self.query_data.allows_repeat) and value in seen_items:
                    return False
                seen_items.append(value)
            return True

        if isinstance(self.query_data, IntegerInputData):
            for value in input_result:
                if not isinstance(value, int):
                    return False
                if value < self.query_data.min_num or value > self.query_data.max_num:
                    return False
            return True

        return True

    def core(self, args : dict | None = None) -> Response:
        if(args is None):
            args = {}

        input_result = args.get("input_result", [])
        if(not isinstance(input_result, list)
           or len(input_result) != len(self.input_keys)
           or not self._validate_with_query_data(input_result)
           or not self.input_validation(input_result)):
            return self._requires_query_response()

        from .avge_abstracts.AVGEEnvironment import AVGEEnvironment
        env : AVGEEnvironment = self.player_for.env
        for i in range(len(input_result)):
            key = self.caller
            if(isinstance(key, (AVGEPlayer, AVGEEnvironment))):
                key = None
            env.cache.set(key, self.input_keys[i], input_result[i])
        return Response(ResponseType.CORE, Data())
    def invert_core(self, args = None):
        assert self.caller is not None
        from .avge_abstracts.AVGEEnvironment import AVGEEnvironment
        env : AVGEEnvironment = self.player_for.env
        for input_key in self.input_keys:
            k = self.caller
            if(isinstance(k, (AVGEPlayer, AVGEEnvironment))):
                k = None
            env.cache.delete(k, input_key)
    def generate_internal_listeners(self):
        return
class TurnEnd(AVGEEvent):
    def __init__(self,
                 environment : AVGEEnvironment,
                 catalyst_action : ActionTypes, 
                 caller : AVGECard | AVGEPlayer | AVGEEnvironment):
        super().__init__(environment=environment,
                 catalyst_action=catalyst_action,
                 caller=caller,
                 core_notif = None)
        self.env = environment
    def core(self, args : dict | None = None) -> Response:
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
        self.propose(AVGEPacket([PhasePickCard(self.env,
                                   ActionTypes.ENV,
                                   self.env)],AVGEEngineID(self.env, ActionTypes.ENV, None)))
        return Response(ResponseType.CORE, EndOfTurn(f"{self.env.player_turn.opponent.username}'s turn has ended!", [PlayerID.P1, PlayerID.P2], default_timeout))
    def invert_core(self, args : dict | None = None):
        raise Exception("A phase should never be canceled")
    def generate_internal_listeners(self):
        return

    