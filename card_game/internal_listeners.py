from __future__ import annotations
from typing import TYPE_CHECKING
from .engine.engine_constants import *
from .constants import *
from .avge_abstracts import *
from .constants import ActionTypes

if TYPE_CHECKING:
    from .avge_abstracts.AVGEPlayer import AVGEPlayer
    

class AVGETokenTransferAssessment(AVGEAssessor):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(env, ActionTypes.ENV, None),
                         requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGEEnergyTransfer
        return isinstance(event, AVGEEnergyTransfer)
    def assess(self, args=None) -> Response:
        from .internal_events import AVGEEnergyTransfer
        event = self.attached_event
        assert(isinstance(event, AVGEEnergyTransfer))
        assert(isinstance(event.token, EnergyToken))
        if(event.token not in event.source.energy):
            return Response(ResponseType.SKIP, Data())
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE):
            if(isinstance(event.target, AVGECharacterCard) and isinstance(event.identifier.caller, AVGEPlayer)):
                if(event.identifier.caller.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] == 0):
                    return Response(ResponseType.SKIP, Data())
        return Response(ResponseType.ACCEPT, Data())
        
        
class AVGEHPChangeAssessment(AVGEAssessor):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(env, ActionTypes.ENV, None),
                         requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGECardHPChange
        return isinstance(event, AVGECardHPChange) and event.catalyst_action != ActionTypes.ENV
    def assess(self, args=None) -> Response:
        from .internal_events import AVGECardHPChange
        event = self.attached_event
        assert(isinstance(event, AVGECardHPChange))
        assert(not event.target_card.cardholder is None)
        if(event.target_card.cardholder.pile_type not in [Pile.BENCH, Pile.ACTIVE] and event.catalyst_action != ActionTypes.ENV):
            return Response(ResponseType.FAST_FORWARD, Data())
        return Response(ResponseType.ACCEPT, Data())
    
class AVGEMaxHPChangeAssessment(AVGEAssessor):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(env, ActionTypes.ENV, None),
                         
                         requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGECardMaxHPChange
        return isinstance(event, AVGECardMaxHPChange) and event.catalyst_action != ActionTypes.ENV
    def assess(self, args=None) -> Response:
        from .internal_events import AVGECardMaxHPChange
        event = self.attached_event
        assert(isinstance(event, AVGECardMaxHPChange))
        assert(not event.target_card.cardholder is None)
        if(event.target_card.cardholder.pile_type not in [Pile.BENCH, Pile.ACTIVE] and event.catalyst_action != ActionTypes.ENV):
            return Response(ResponseType.FAST_FORWARD, Data())
        return Response(ResponseType.ACCEPT, Data())

class AVGEWeaknessModifier(AVGEModifier):
    _CRIT_KEY = "global_crit_key"
    def __init__(self, env : AVGEEnvironment):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(env, ActionTypes.ENV, None),
                         requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGECardHPChange
        return isinstance(event, AVGECardHPChange) and isinstance(event.caller, AVGECharacterCard) and not event.change_type==CardType.ALL and event.modifier_type==AVGEAttributeModifier.SUBSTRACTIVE
    def modify(self, args = None) -> Response:
        from .internal_events import AVGECardHPChange, InputEvent
        event = self.attached_event
        assert(isinstance(event, AVGECardHPChange))
        assert(not event.caller is None)
        if(type_weaknesses[event.target_card.card_type]) == event.change_type and isinstance(event.caller, AVGECharacterCard):
            coin_toss = event.caller.env.cache.get(event.caller, AVGEWeaknessModifier._CRIT_KEY,
                                                        None, True)
            if coin_toss is None:
                return Response(ResponseType.INTERRUPT,
                                Interrupt[InputEvent](
                                    [InputEvent(
                                        event.caller.player,
                                        [AVGEWeaknessModifier._CRIT_KEY],
                                        lambda r : True,
                                        ActionTypes.ENV,
                                        event.caller,
                                        CoinflipData("Critical! Flip a coin and get heads to double the damage!")
                                    )]
                                ))
            if(coin_toss == 1):
                event.modify_magnitude(event.magnitude)
        return Response(ResponseType.ACCEPT, Data())

class AVGEPlayerAttributeChangePostChecker(AVGEPostcheck):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(group = EngineGroup.INTERNAL_3,
                         identifier = AVGEEngineID(env, ActionTypes.ENV, None),
                         
                          requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGEPlayerAttributeChange
        return isinstance(event, AVGEPlayerAttributeChange)
    def assess(self, args=None):
        from .internal_events import AVGEPlayerAttributeChange
        assert(isinstance(self.attached_event, AVGEPlayerAttributeChange))
        event : AVGEPlayerAttributeChange = self.attached_event
        if(event.attribute == AVGEPlayerAttribute.KO_COUNT and event.target_player.attributes[AVGEPlayerAttribute.KO_COUNT] >= 3):
            env : AVGEEnvironment = event.target_player.env
            env.winner = event.target_player
            return Response(ResponseType.GAME_END, GameEnd(env.winner.unique_id, "player hit 3 KO's"))
        return Response(ResponseType.ACCEPT, Data())

class AVGETransferValidityCheck(AVGEAssessor):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(env, ActionTypes.ENV, None),
                         
                          requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import TransferCard
        return isinstance(event, TransferCard)
    def assess(self, args=None) -> Response:
        from .internal_events import TransferCard
        assert(isinstance(self.attached_event, TransferCard))
        event : TransferCard = self.attached_event
        if(not (event.card in event.pile_from)):#if this case happens, something wonk has happened
            return Response(ResponseType.FAST_FORWARD, Data())
        if(event.pile_to.pile_type in [Pile.BENCH, Pile.ACTIVE] and not isinstance(event.card, AVGECharacterCard)):
            return Response(ResponseType.SKIP, Data())
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE and 
           event.pile_from.pile_type == Pile.HAND and 
           event.pile_to.pile_type == Pile.BENCH):#tried to add a card to the bench but bench is full / card isn't character
            bench = event.pile_to
            player_responsible = event.card.env.player_turn
            if(not isinstance(event.card, AVGECharacterCard) or len(bench) == max_bench_size):
                return Response(ResponseType.SKIP, Notify("Can't add this card to the bench b/c the bench is full!", [player_responsible.unique_id], default_timeout))
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE and 
           isinstance(event.card, AVGECharacterCard) and
           event.pile_from.pile_type == Pile.BENCH and 
           event.pile_to.pile_type == Pile.ACTIVE and
           event.card.player.attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN] == 0):
           return Response(ResponseType.SKIP, Notify("Can't switch these cards, since you have no more swaps left this turn!", [event.card.player.unique_id], default_timeout))
        if(isinstance(event.card, AVGECharacterCard) and event.energy_requirement > len(event.card.energy)):
            return Response(ResponseType.SKIP, Notify("Not enough energy to perform this transfer!", [event.card.player.unique_id], default_timeout))
        return Response(ResponseType.ACCEPT, Data())

class AVGETransferEnergyRequirementReactor(AVGEReactor):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(group = EngineGroup.INTERNAL_3,
                         identifier = AVGEEngineID(env, ActionTypes.ENV, None),
                         
                          requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import TransferCard
        return isinstance(event, TransferCard) and isinstance(event.card, AVGECharacterCard) and event.energy_requirement > 0
    def react(self, args = None) -> Response:
        from .internal_events import TransferCard, AVGEEnergyTransfer
        assert(isinstance(self.attached_event, TransferCard))
        event : TransferCard = self.attached_event
        assert(isinstance(event.card, AVGECharacterCard))
        card : AVGECharacterCard = event.card
        packet : PacketType = []
        if(event.energy_requirement > 0):
            for token_idx in range(event.energy_requirement):
                token = card.energy[token_idx]
                packet.append(AVGEEnergyTransfer(
                    token,
                    card,
                    card.env,
                    ActionTypes.ENV,
                    card.env,
                    None
                ))
        self.propose(AVGEPacket(packet, AVGEEngineID(card.env, ActionTypes.ENV, None)))
        return Response(ResponseType.ACCEPT, Data())

class AVGEPlayCharacterCardValidityCheck(AVGEAssessor):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(env, ActionTypes.ENV, None),
                         
                         requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import PlayCharacterCard
        return isinstance(event, PlayCharacterCard)
    def assess(self, args =None) -> Response:
        from .internal_events import PlayCharacterCard
        assert(isinstance(self.attached_event, PlayCharacterCard))
        event : PlayCharacterCard = self.attached_event
        if(event.card_action == ActionTypes.ATK_1):
            if(event.card.atk_1_name is None):
                players = [PlayerID.P1, PlayerID.P2]
                if(event.catalyst_action == ActionTypes.PLAYER_CHOICE):
                    players = [event.card.env.player_turn.unique_id]
                return Response(ResponseType.SKIP, Notify("Tried to use an attack that doesn't exist!", players, default_timeout))
        elif(event.card_action == ActionTypes.ATK_2):
            if(event.card.atk_2_name is None):
                players = [PlayerID.P1, PlayerID.P2]
                if(event.catalyst_action == ActionTypes.PLAYER_CHOICE):
                    players = [event.card.env.player_turn.unique_id]
                return Response(ResponseType.SKIP, Notify("Tried to use an attack that doesn't exist!", players, default_timeout))
        elif(event.card_action == ActionTypes.ACTIVATE_ABILITY):
            if(not isinstance(event.caller, AVGECharacterCard) or event.card.active_name is None or not event.card.can_play_active()):
                players = [PlayerID.P1, PlayerID.P2]
                if(event.catalyst_action == ActionTypes.PLAYER_CHOICE):
                    players = [event.card.env.player_turn.unique_id]
                return Response(ResponseType.SKIP, Notify("Tried to use an ability that can't be played now!", players, default_timeout))
        elif(event.card_action == ActionTypes.PASSIVE):
            if(not event.card.has_passive):
                return Response(ResponseType.SKIP, Data())
            
        if(event.energy_requirement > len(event.card.energy)):
            players = [PlayerID.P1, PlayerID.P2]
            if(event.catalyst_action == ActionTypes.PLAYER_CHOICE):
                players = [event.card.env.player_turn.unique_id]
            return Response(ResponseType.SKIP, Notify("Not enough energy to play this move!", players, default_timeout))
        return Response(ResponseType.ACCEPT, Data())
    
class AVGEPlayNonCharacterCardValidityCheck(AVGEAssessor):
    def __init__(self, env : AVGEEnvironment):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(env, ActionTypes.ENV, None),
                         
                         requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import PlayNonCharacterCard
        return isinstance(event, PlayNonCharacterCard)
    def assess(self, args=None) -> Response:
        from .internal_events import PlayNonCharacterCard
        assert(isinstance(self.attached_event, PlayNonCharacterCard))
        event : PlayNonCharacterCard = self.attached_event
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE):
            if(isinstance(event.card, AVGESupporterCard)):
                card : AVGESupporterCard = event.card
                player : AVGEPlayer = card.player
                if(player.attributes[AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN] == 0):
                    return Response(ResponseType.SKIP, Notify("No more supporter uses left this turn!", [player.unique_id], default_timeout))
        return Response(ResponseType.ACCEPT, Data())