from __future__ import annotations
from typing import TYPE_CHECKING
from .engine.engine_constants import *
from .constants import *
from .avge_abstracts import *
from .constants import ActionTypes

if TYPE_CHECKING:
    from .avge_abstracts.AVGEPlayer import AVGEPlayer
    

class AVGETokenTransferAssessment(AVGEAssessor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(None, ActionTypes.ENV, None),
                         internal = True,
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
            return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: 'Token doesn\'t exist in source. Skipping.'})
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE):
            if(isinstance(event.target, AVGECharacterCard) and isinstance(event.source, AVGEPlayer)):
                if(event.source.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] == 0):
                    return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: 'Can\'t add any more tokens this turn'})
        return self.generate_response()
        
        
class AVGEHPChangeAssessment(AVGEAssessor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(None, ActionTypes.ENV, None),
                         internal = True,
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
            return self.generate_response(ResponseType.FAST_FORWARD, {MESSAGE_KEY: 'HP Changes should only be directed at BENCH, ACTIVE cards. This packet is likely a lingering packet'})
        return self.generate_response()
    
class AVGEMaxHPChangeAssessment(AVGEAssessor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(None, ActionTypes.ENV, None),
                         internal = True,
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
            return self.generate_response(ResponseType.FAST_FORWARD, {MESSAGE_KEY: 'MAXHP Changes should only be directed at BENCH, ACTIVE cards. This packet is likely a lingering packet'})
        return self.generate_response()

class AVGEWeaknessModifier(AVGEModifier):
    _CRIT_KEY = "global_crit_key"
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(None, ActionTypes.ENV, None),
                         internal = True,
                         requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGECardHPChange
        return isinstance(event, AVGECardHPChange) and isinstance(event.caller_card, AVGECharacterCard) and not event.change_type==CardType.ALL and event.modifier_type==AVGEAttributeModifier.SUBSTRACTIVE
    def modify(self, args = None) -> Response:
        from .internal_events import AVGECardHPChange, InputEvent
        event = self.attached_event
        assert(isinstance(event, AVGECardHPChange))
        assert(not event.caller_card is None)
        if(type_weaknesses[event.target_card.card_type]) == event.change_type:
            coin_toss = event.caller_card.env.cache.get(event.caller_card, AVGEWeaknessModifier._CRIT_KEY,
                                                        None, True)
            if coin_toss is None:
                return self.generate_response(ResponseType.INTERRUPT,{
                    INTERRUPT_KEY:[
                        InputEvent(
                            event.caller_card.player,
                            [AVGEWeaknessModifier._CRIT_KEY],
                            InputType.COIN,
                            lambda r : True,
                            ActionTypes.ENV,
                            event.caller_card,
                            {LABEL_FLAG: "global-crit-coinflip"}
                        )
                    ]
                })
            if(coin_toss == 1):
                event.modify_magnitude(event.magnitude)
        return self.generate_response()

class AVGEPlayerAttributeChangePostChecker(AVGEPostcheck):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_3,
                         identifier = AVGEEngineID(None, ActionTypes.ENV, None),
                         internal = True,
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
            return self.generate_response(ResponseType.GAME_END, {"winner": env.winner, "reason": "player hit 3 KO's"})
        return self.generate_response()

class AVGETransferValidityCheck(AVGEAssessor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(None, ActionTypes.ENV, None),
                         internal = True,
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
            return self.generate_response(ResponseType.FAST_FORWARD, {MESSAGE_KEY: 'Card transfer from cardholder that doesn\'t contain it. This is likely a dead packet'})
        if(event.pile_to.pile_type in [Pile.BENCH, Pile.ACTIVE] and not isinstance(event.card, AVGECharacterCard)):
            return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: 'Can\'t move non-character cards here!'})
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE and 
           event.pile_from.pile_type == Pile.HAND and 
           event.pile_to.pile_type == Pile.BENCH):#tried to add a card to the bench but bench is full / card isn't character
            bench = event.pile_to
            if(not isinstance(event.card, AVGECharacterCard) or len(bench) == max_bench_size):
                return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: 'Can\'t add this card to bench since bench is full!'})
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE and 
           isinstance(event.card, AVGECharacterCard) and
           event.pile_from.pile_type == Pile.BENCH and 
           event.pile_to.pile_type == Pile.ACTIVE and
           event.card.player.attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN] == 0):
            return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: 'no more swaps this turn!'})
        if(isinstance(event.card, AVGECharacterCard) and event.energy_requirement > len(event.card.energy)):
            return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: 'not enough energy to perform this transfer!'})
        return self.generate_response()

class AVGETransferEnergyRequirementReactor(AVGEReactor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_3,
                         identifier = AVGEEngineID(None, ActionTypes.ENV, None),
                         internal = True,
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
                    None
                ))
        self.propose(AVGEPacket(packet, AVGEEngineID(None, ActionTypes.ENV, None)))
        return self.generate_response()

class AVGEPlayCharacterCardValidityCheck(AVGEAssessor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(None, ActionTypes.ENV, None),
                         internal = True,
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
            if(not event.card.has_atk_1):
                return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: 'no atk 1 to play!'})
        elif(event.card_action == ActionTypes.ATK_2):
            if(not event.card.has_atk_2):
                return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: 'no atk 2 to play!'})
        elif(event.card_action == ActionTypes.ACTIVATE_ABILITY):
            if(not isinstance(event.caller_card, AVGECharacterCard) or not event.card.has_active or not event.card.can_play_active(event.caller_card)):
                return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: 'cannot play ability right now!'})
        elif(event.card_action == ActionTypes.PASSIVE):
            if(not event.card.has_passive):
                return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: 'cannot play ability right now!'})
            
        if(event.energy_requirement > len(event.card.energy)):
            return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: 'not enough energy!'})
        return self.generate_response()
    
class AVGEPlayNonCharacterCardValidityCheck(AVGEAssessor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = AVGEEngineID(None, ActionTypes.ENV, None),
                         internal = True,
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
                    return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: 'cannot use any more supporter cards this turn!'})
        return self.generate_response()