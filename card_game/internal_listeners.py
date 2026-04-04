from __future__ import annotations
from typing import TYPE_CHECKING
from .engine.engine_constants import *
from .constants import *
from .avge_abstracts.AVGEEventListeners import *
from .avge_abstracts.AVGECards import *
from .avge_abstracts.AVGEEnvironment import *
from .avge_abstracts.AVGECardholder import *

if TYPE_CHECKING:
    from .avge_abstracts.AVGEPlayer import AVGEPlayer
    

class AVGETokenTransferAssessment(AVGEAssessor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = (None, AVGEEventListenerType.ENV),
                         internal = True,
                         requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGEEnergyTransfer
        return isinstance(event, AVGEEnergyTransfer)
    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def assess(self, args=None) -> Response:
        from .internal_events import AVGEEnergyTransfer
        event : AVGEEnergyTransfer = self.attached_event
        if(event.token not in event.source):
            return self.generate_response(ResponseType.SKIP, {'msg': 'Token doesn\'t exist in source. Skipping.'})
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE):
            if(isinstance(event.target, AVGECharacterCard) and isinstance(event.source, AVGEPlayer)):
                if(event.source.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] == 0):
                    return self.generate_response(ResponseType.SKIP, {'msg': 'Can\'t add any more tokens this turn'})
        return self.generate_response()
        
        
class AVGEHPChangeAssessment(AVGEAssessor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = (None, AVGEEventListenerType.ENV),
                         internal = True,
                         requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGECardHPChange
        return isinstance(event, AVGECardHPChange)
    def assess(self, args=None) -> Response:
        from .internal_events import AVGECardHPChange
        event : AVGECardHPChange = self.attached_event
        if(event.target_card.cardholder.pile_type not in [Pile.BENCH, Pile.ACTIVE]):
            return self.generate_response(ResponseType.FAST_FORWARD, {'msg': 'HP Changes should only be directed at BENCH, ACTIVE cards. This packet is likely a lingering packet'})
        return self.generate_response()

class AVGEWeaknessModifier(AVGEModifier):
    _CRIT_KEY = "global_crit_key"
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = (None, AVGEEventListenerType.ENV),
                         internal = True,
                         requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGECardHPChange
        return isinstance(event, AVGECardHPChange) and isinstance(event.caller_card, AVGECharacterCard)
    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def modify(self, args) -> Response:
        from .internal_events import AVGECardHPChange, InputEvent
        event : AVGECardHPChange = self.attached_event
        if(type_weaknesses[event.target_card.card_type]) == event.change_type:
            coin_toss = event.target_card.env.cache.get(None, AVGEWeaknessModifier._CRIT_KEY,
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
                            {"query_label": "global-crit-coinflip"}
                        )
                    ]
                })
            if(coin_toss == 1):
                event.modify_magnitude(event.magnitude)
        return self.generate_response()
class AVGECardHPChangeReactor(AVGEReactor):
    _KO_REPLACE_KEY = "internal_ko_replace_pick"

    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_3,
                         identifier = (None, AVGEEventListenerType.ENV),
                         internal = True,
                        requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGECardHPChange
        return isinstance(event, AVGECardHPChange)
    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def react(self, args=None) -> Response:
        from .internal_events import AVGECardHPChange, TransferCard, AVGEPlayerAttributeChange, InputEvent
        event : AVGECardHPChange = self.attached_event
        if(event.target_card.hp <= 0):
            parent_player : AVGEPlayer = event.target_card.player
            packet = []
            if(parent_player.get_active_card() == event.target_card):
                if(len(parent_player.cardholders[Pile.BENCH]) == 0):
                    e : AVGEEnvironment = event.target_card.env
                    e.winner = parent_player.opponent
                    return self.generate_response(ResponseType.GAME_END, {"winner": e.winner, "reason": "KO and no cards left on bench"})

                swap_with = event.target_card.env.cache.get(
                        event.target_card,
                        AVGECardHPChangeReactor._KO_REPLACE_KEY,
                        None,
                        one_look=True,
                    )
                if(swap_with is None):
                    return self.generate_response(
                        ResponseType.INTERRUPT,
                        {
                            INTERRUPT_KEY: [
                                InputEvent(
                                    parent_player,
                                    [AVGECardHPChangeReactor._KO_REPLACE_KEY],
                                    InputType.SELECTION,
                                    lambda r : True,
                                    ActionTypes.ENV,
                                    event.target_card,
                                    {
                                        'query_label': 'ko_replace',
                                        'bench': list(parent_player.cardholders[Pile.BENCH])
                                    },
                                )
                            ]
                        },
                    )
                packet.append(TransferCard(swap_with,
                                            parent_player.cardholders[Pile.BENCH],
                                            parent_player.cardholders[Pile.ACTIVE],
                                            ActionTypes.ENV,
                                            None))#propose the swap from the bench, and then propose the discard
            packet.append(TransferCard(event.target_card,
                                            event.target_card.cardholder,
                                            parent_player.cardholders[Pile.DISCARD],
                                            ActionTypes.ENV,
                                            None))
            packet.append(AVGEPlayerAttributeChange(event.target_card.player.opponent,
                                                    AVGEPlayerAttribute.KO_COUNT,
                                                    1,
                                                    AVGEAttributeModifier.ADDITIVE,
                                                    ActionTypes.ENV,
                                                    None))
            return self.generate_response(
                        ResponseType.INTERRUPT,
                        {
                            INTERRUPT_KEY: packet
                        },
                    )
        return self.generate_response()

    

class AVGEPlayerAttributeChangePostChecker(AVGEPostcheck):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_3,
                         identifier = (None, AVGEEventListenerType.ENV),
                         internal = True,
                          requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGEPlayerAttributeChange
        return isinstance(event, AVGEPlayerAttributeChange)

    def make_announcement(self) -> bool:
        return True
    def package(self):
        return "Clamping player change if necessary"
    def assess(self, args=None):
        from .internal_events import AVGEPlayerAttributeChange
        event : AVGEPlayerAttributeChange = self.attached_event
        if(event.attribute == AVGEPlayerAttribute.KO_COUNT and event.target_player.attributes[AVGEPlayerAttribute.KO_COUNT] >= 3):
            env : AVGEEnvironment = event.target_player.env
            env.winner = event.target_player
            return self.generate_response(ResponseType.GAME_END, {"winner": env.winner, "reason": "player hit 3 KO's"})
        return self.generate_response()

class AVGETransferValidityCheck(AVGEAssessor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = (None, AVGEEventListenerType.ENV),
                         internal = True,
                          requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import TransferCard
        return isinstance(event, TransferCard)

    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def assess(self, args=None) -> Response:
        from .internal_events import TransferCard
        event : TransferCard = self.attached_event
        if(not (event.card in event.pile_from)):#if this case happens, something wonk has happened
            return self.generate_response(ResponseType.FAST_FORWARD, {'msg': 'Card transfer from cardholder that doesn\'t contain it. This is likely a dead packet'})
        if(event.pile_to.pile_type in [Pile.BENCH, Pile.ACTIVE] and not isinstance(event.card, AVGECharacterCard)):
            return self.generate_response(ResponseType.SKIP, {'msg': 'Can\'t move non-character cards here!'})
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE and 
           event.pile_from.pile_type == Pile.HAND and 
           event.pile_to.pile_type == Pile.BENCH):#tried to add a card to the bench but bench is full / card isn't character
            bench = event.pile_to
            if(not isinstance(event.card, AVGECharacterCard) or len(bench) == max_bench_size):
                return self.generate_response(ResponseType.SKIP, {'msg': 'Can\'t add this card to bench since bench is full!'})
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE and 
           event.card.player.attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN] == 0):
            return self.generate_response(ResponseType.SKIP, {'msg': 'no more swaps this turn!'})
        if(isinstance(event.card, AVGECharacterCard) and event.energy_requirement > len(event.card.energy)):
            return self.generate_response(ResponseType.SKIP, {'msg': 'not enough energy to perform this transfer!'})
        return self.generate_response()

class AVGETransferEnergyRequirementReactor(AVGEReactor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_3,
                         identifier = (None, AVGEEventListenerType.ENV),
                         internal = True,
                          requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import TransferCard
        return isinstance(event, TransferCard)
    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def react(self, args = None) -> Response:
        from .internal_events import TransferCard, AVGEEnergyTransfer
        event : TransferCard = self.attached_event
        card : AVGECharacterCard = event.card
        packet = []
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
        self.propose(packet)
        return self.generate_response()
class AVGEDiscardReactor(AVGEReactor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_3,
                         identifier = (None, AVGEEventListenerType.ENV),
                         internal = True,
                          requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import TransferCard
        return isinstance(event, TransferCard) and event.pile_to.pile_type == Pile.DISCARD

    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def react(self, args = None) -> Response:
        from .internal_events import TransferCard, AVGEEnergyTransfer, AVGECardHPChange, AVGECardMaxHPChange, AVGEStatusChange
        event : TransferCard = self.attached_event
        if(isinstance(event.card, AVGECharacterCard) and event.pile_from.pile_type in [Pile.ACTIVE, Pile.BENCH]
           and event.pile_to.pile_type not in [Pile.BENCH, Pile.ACTIVE]):#character card getting discarded
            card : AVGECharacterCard= event.card
            #discard tools
            def packet_1():
                return [TransferCard(tool,
                                            card.tools_attached,
                                            event.pile_to,
                                            ActionTypes.ENV,
                                            None) for tool in card.tools_attached] 
            #drop the energy
            def packet_2():
                return [AVGEEnergyTransfer(token,
                                            card,
                                            card.env,
                                            ActionTypes.ENV,
                                            None) for token in card.energy] 
            #drop the statuses
            def packet_3():
                packet = []
                #drop all statuses
                for status_effect, cards in event.card.statuses_attached.items():
                    for card in cards:
                        packet.append(AVGEStatusChange(
                            event.card,
                            status_effect,
                            StatusChangeType.REMOVE,
                            ActionTypes.ENV,
                            card
                        ))
                return packet
            def packet_4():
                packet = []
                #reset MAXHP
                packet.append(AVGECardMaxHPChange(
                    card,
                    card.default_max_hp,
                    AVGEAttributeModifier.SET_STATE,
                    ActionTypes.ENV,
                    None
                ))
                #reset HP
                packet.append(AVGECardHPChange(
                    card,
                    card.default_max_hp,
                    AVGEAttributeModifier.SET_STATE,
                    CardType.ALL,
                    ActionTypes.ENV,
                    None
                ))
                return packet
            self.propose(packet_1, 1)
            self.propose(packet_2, 1)
            self.propose(packet_3, 1)
            self.propose(packet_4, 1)
        event.card.env.cache.wipe(event.card)
        return self.generate_response()

class AVGEPlayCharacterCardValidityCheck(AVGEAssessor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = (None, AVGEEventListenerType.ENV),
                         internal = True,
                         requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import PlayCharacterCard
        return isinstance(event, PlayCharacterCard)
    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def assess(self, data =None) -> Response:
        from .internal_events import PlayCharacterCard
        event : PlayCharacterCard = self.attached_event
        if(event.card_action == ActionTypes.ATK_1):
            if(not event.card.has_atk_1):
                return self.generate_response(ResponseType.SKIP, {'msg': 'no atk 1 to play!'})
        elif(event.card_action == ActionTypes.ATK_2):
            if(not event.card.has_atk_2):
                return self.generate_response(ResponseType.SKIP, {'msg': 'no atk 2 to play!'})
        elif(event.card_action == ActionTypes.ACTIVATE_ABILITY):
            if(not isinstance(event.caller_card, AVGECharacterCard) or not event.card.has_active or not event.card.can_play_active(event.caller_card)):
                return self.generate_response(ResponseType.SKIP, {'msg': 'cannot play ability right now!'})
        elif(event.card_action == ActionTypes.PASSIVE):
            if(not event.card.has_passive):
                return self.generate_response(ResponseType.SKIP, {'msg': 'cannot play ability right now!'})
            
        if(event.energy_requirement > len(event.card.energy)):
            return self.generate_response(ResponseType.SKIP, {'msg': 'not enough energy!'})
        return self.generate_response()
    
class AVGEPlayNonCharacterCardValidityCheck(AVGEAssessor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = (None, AVGEEventListenerType.ENV),
                         internal = True,
                         requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import PlayNonCharacterCard
        return isinstance(event, PlayNonCharacterCard)
    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def assess(self, data=None) -> Response:
        from .internal_events import PlayNonCharacterCard
        event : PlayNonCharacterCard = self.attached_event
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE):
            if(isinstance(event.card, AVGESupporterCard)):
                card : AVGESupporterCard = event.card
                player : AVGEPlayer = card.player
                if(player.attributes[AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN] == 0):
                    return self.generate_response(ResponseType.SKIP, {'msg': 'cannot use any more supporter cards this turn!'})
        return self.generate_response()