from __future__ import annotations
from .engine.engine_constants import *
from .constants import *
from .avge_abstracts.AVGEEventListeners import *
from .avge_abstracts.AVGEPlayer import AVGEPlayer
from .avge_abstracts.AVGECards import *
from .avge_abstracts.AVGEEnvironment import *
from .avge_abstracts.AVGECardholder import *

class AVGECardAttributeChangeModifier(AVGEModifier):
    def __init__(self):
        super().__init__((None, AVGEEventListenerType.ENV),
                          group = EngineGroup.INTERNAL_3,
                          internal = True,
                          requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGECardAttributeChange
        return isinstance(event, AVGECardAttributeChange)
    def make_announcement(self) -> bool:
        return True
    def package(self):
        return "Clamping attribute change if necessary"
    def modify(self, args):
        from .internal_events import AVGECardAttributeChange
        event : AVGECardAttributeChange = self.attached_event
        if(event.attribute_modifier_type == AVGEAttributeModifier.ADDITIVE):
            new_amt = event.target_card.attributes[event.attribute] + event.change_amount
            if(new_amt < 0):
                event.change_amount = -event.target_card.attributes[event.attribute]
        else:
            if(event.change_amount <= 0):
                event.change_amount = 0
        if(event.attribute == AVGECardAttribute.HP):
            new_amt = event.target_card.attributes[event.attribute] + event.change_amount
            if(new_amt > event.target_card.attributes[AVGECardAttribute.MAXHP]):
                event.change_amount = event.target_card.attributes[AVGECardAttribute.MAXHP] - event.target_card.attributes[AVGECardAttribute.HP]

        return self.generate_response()
    
class AVGECardAttributeChangeAssessment(AVGEAssessor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         identifier = (None, AVGEEventListenerType.ENV),
                         internal = True,
                         requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGECardAttributeChange
        return isinstance(event, AVGECardAttributeChange)
    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def assess(self, args) -> Response:
        from .internal_events import AVGECardAttributeChange
        event : AVGECardAttributeChange = self.attached_event
        parent_player : AVGEPlayer = event.target_card.player
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE
           and parent_player.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] == 0):
            return self.generate_response(ResponseType.SKIP, {'msg': 'Can\'t add any more tokens this turn'})
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE
           and parent_player.attributes[AVGEPlayerAttribute.TOTAL_ENERGY_TOKENS] == 0):
            return self.generate_response(ResponseType.SKIP, {'msg': 'No more tokens to add'})
        return self.generate_response()

class AVGECardAttributeChangeReactor(AVGEReactor):
    _KO_REPLACE_KEY = "internal_ko_replace_pick"

    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_4,
                         identifier = (None, AVGEEventListenerType.ENV),
                         internal = True,
                        requires_runtime_info=False)
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import AVGECardAttributeChange
        return isinstance(event, AVGECardAttributeChange)
    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def react(self, args) -> Response:
        from .internal_events import AVGECardAttributeChange, TransferCard, AVGEPlayerAttributeChange, InputEvent
        event : AVGECardAttributeChange = self.attached_event
        if(event.attribute == AVGECardAttribute.HP and event.target_card.attributes[AVGECardAttribute.HP] <= 0):
            parent_player : AVGEPlayer = event.target_card.player
            packet = []
            if(parent_player.get_active_card() == event.target_card):
                if(len(parent_player.cardholders[Pile.BENCH]) == 0):
                    e : AVGEEnvironment = event.target_card.env
                    e.winner = parent_player.opponent
                    return self.generate_response(ResponseType.GAME_END, {"winner": e.winner, "reason": "KO and no cards left on bench"})

                missing = object()
                swap_with = event.target_card.env.cache.get(
                        event.target_card,
                        AVGECardAttributeChangeReactor._KO_REPLACE_KEY,
                        missing,
                        one_look=True,
                    )
                if(swap_with is missing):
                    def _ko_replace_valid(result) -> bool:
                        return (
                            len(result) == 1
                            and isinstance(result[0], AVGECharacterCard)
                            and result[0] in parent_player.cardholders[Pile.BENCH]
                        )

                    return self.generate_response(
                        ResponseType.INTERRUPT,
                        {
                            INTERRUPT_KEY: [
                                InputEvent(
                                    parent_player,
                                    [AVGECardAttributeChangeReactor._KO_REPLACE_KEY],
                                    InputType.DETERMINISTIC,
                                    _ko_replace_valid,
                                    ActionTypes.ENV,
                                    event.target_card,
                                    {
                                        'query_type': 'ko_replace',
                                        'target_player': parent_player,
                                        'bench_ids': [card.unique_id for card in parent_player.cardholders[Pile.BENCH]],
                                        'pick_count': 1,
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
            self.propose(packet, 1)
        return self.generate_response()

    
class AVGEPlayerAttributeChangeModifier(AVGEModifier):
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
    def modify(self, args):
        from .internal_events import AVGEPlayerAttributeChange
        event : AVGEPlayerAttributeChange = self.attached_event
        if(event.attribute_modifier_type == AVGEAttributeModifier.ADDITIVE):
            new_amt = event.target_player.attributes[event.attribute] + event.change_amount
            if(new_amt < 0):
                event.change_amount = -event.target_player.attributes[event.attribute]
        else:
            if(event.change_amount <= 0):
                event.change_amount = 0
        return self.generate_response()

class AVGEPlayerAttributeChangePostChecker(AVGEPostcheck):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_4,
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
    def assess(self, args):
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
    def assess(self, args) -> Response:
        from .internal_events import TransferCard
        event : TransferCard = self.attached_event
        if(not (event.card in event.pile_from)):#if this case happens, something wonk has happened
            return self.generate_response(ResponseType.SKIP, {'msg': 'card transfer from cardholder that doesn\'t contain it'})
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE and 
           event.pile_from.pile_type == Pile.HAND and 
           event.pile_to.pile_type == Pile.BENCH):#tried to add a card to the bench but bench is full / card isn't character
            bench = event.pile_to
            if(not isinstance(event.card, AVGECharacterCard) or len(bench) == max_bench_size):
                return self.generate_response(ResponseType.SKIP, {'msg': 'can\'t add this card to bench!'})
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE and 
           event.pile_from.pile_type == Pile.ACTIVE and 
           event.pile_to.pile_type == Pile.BENCH):#attempt to retreat
            #only need this once b/c a swap is made of a packet
            player :AVGEPlayer = event.card.player
            if(player.attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN] == 0):
                return self.generate_response(ResponseType.SKIP, {'msg': 'no more swaps this turn!'})
            if(event.card.attributes[AVGECardAttribute.SWITCH_COST] > event.card.attributes[AVGECardAttribute.ENERGY_ATTACHED]):
                return self.generate_response(ResponseType.SKIP, {'msg': 'not enough energy'})
        return self.generate_response()

class AVGEDiscardReactor(AVGEReactor):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_4,
                         identifier = (None, AVGEEventListenerType.ENV),
                         internal = True,
                          requires_runtime_info=False)
        from .internal_events import TransferCard
    def update_status(self):
        return
    def event_match(self, event):
        from .internal_events import TransferCard
        return isinstance(event, TransferCard) and event.pile_to == Pile.DISCARD

    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def react(self, args) -> Response:
        from .internal_events import TransferCard, AVGECardAttributeChange, ChangeStatus
        event : TransferCard = self.attached_event
        if(isinstance(event.card, AVGECharacterCard) and event.pile_from.pile_type in [Pile.ACTIVE, Pile.BENCH]):#character card getting discarded
            card : AVGECharacterCard= event.card
            card.deactivate_card()
            packet = []
            #drop the tools
            for tool in event.card.tools_attached:
                packet.append(TransferCard(tool,
                                          card.tools_attached,
                                          card.player.cardholders[Pile.DISCARD],
                                          ActionTypes.ENV,
                                          None))
            #drop the statuses
            for status, count in event.card.statuses_attached.items():
                for _ in range(count):
                    packet.append(ChangeStatus(card,
                                               status,
                                               ChangeType.REMOVE,
                                               ActionTypes.ENV,
                                               None))
            #drop the energy
            packet.append(AVGECardAttributeChange(
                card,
                AVGECardAttribute.ENERGY_ATTACHED,
                0,
                AVGEAttributeModifier.SET_STATE,
                ActionTypes.ENV,
                None,
                None
            ))
            #reset HP
            packet.append(AVGECardAttributeChange(
                card,
                AVGECardAttribute.HP,
                AVGECardAttribute.MAXHP,
                AVGEAttributeModifier.SET_STATE,
                ActionTypes.ENV,
                None,
                None
            ))
            self.propose(packet)
        elif(isinstance(event.card, AVGEToolCard) and isinstance(event.pile_from, AVGEToolCardholder)):
            event.card.deactivate_card()
        elif(isinstance(event.card, AVGEStadiumCard) and isinstance(event.pile_from, AVGEStadiumCardholder)):
            event.card.deactivate_card()
        event.card.env.cache.wipe(card)
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
    def assess(self, data) -> Response:
        from .internal_events import PlayCharacterCard
        event : PlayCharacterCard = self.attached_event
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE):
            if(event.card_action == ActionTypes.ATK_1):
                if(not event.card.has_atk_1):
                    return self.generate_response(ResponseType.SKIP, {'msg': 'no atk 1 to play!'})
                if(event.card.attributes[AVGECardAttribute.ENERGY_ATTACHED] < event.card.attributes[AVGECardAttribute.MV_1_COST]):
                    return self.generate_response(ResponseType.SKIP, {'msg': 'not enough energy!'})
            elif(event.card_action == ActionTypes.ATK_2):
                if(not event.card.has_atk_2):
                    return self.generate_response(ResponseType.SKIP, {'msg': 'no atk 2 to play!'})
                if(event.card.attributes[AVGECardAttribute.ENERGY_ATTACHED] < event.card.attributes[AVGECardAttribute.MV_2_COST]):
                    return self.generate_response(ResponseType.SKIP, {'msg': 'not enough energy!'})
            elif(event.card_action == ActionTypes.ACTIVATE_ABILITY):
                if(not event.card.can_play_active()):
                    return self.generate_response(ResponseType.SKIP, {'msg': 'cannot play ability right!'})
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
    def assess(self, data) -> Response:
        from .internal_events import PlayNonCharacterCard
        event : PlayNonCharacterCard = self.attached_event
        if(event.catalyst_action == ActionTypes.PLAYER_CHOICE):
            if(isinstance(event.card, AVGESupporterCard)):
                card : AVGESupporterCard = event.card
                player : AVGEPlayer = card.player
                if(player.attributes[AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN] == 0):
                    return self.generate_response(ResponseType.SKIP, {'msg': 'cannot use any more supporter cards this turn!'})
        return self.generate_response()