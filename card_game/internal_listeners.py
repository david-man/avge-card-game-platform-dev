from __future__ import annotations
from .engine.event_listener import *
from .engine.engine_constants import *
from .constants import *
from .avge_abstracts.AVGEPlayer import AVGEPlayer
from .avge_abstracts.AVGECards import *
from .avge_abstracts.AVGEEnvironment import *

class AVGECardAttributeChangeModifier(ModifierEventListener):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_2,
                         flags = [AVGEFlag.CARD_ATTR_CHANGE],
                         internal = True)
    def is_valid(self) -> bool:
        return True
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
            if(event.change_amount < 0):
                event.change_amount = 0
        return self.generate_response()
    
class AVGECardAttributeChangeAssessment(AssessorEventListener):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         flags = [AVGEFlag.CARD_ATTR_CHANGE],
                         internal = True)
    def is_valid(self) -> bool:
        return True
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

class AVGECardAttributeChangeReactor(ReactorEventListener):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_3,
                         flags = [AVGEFlag.CARD_ATTR_CHANGE],
                         internal = True)
    def is_valid(self) -> bool:
        return True
    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def react(self, args) -> Response:
        from .internal_events import AVGECardAttributeChange, TransferCard, AVGEPlayerAttributeChange
        event : AVGECardAttributeChange = self.attached_event
        if(event.attribute == AVGECardAttribute.HP and event.target_card.attributes[AVGECardAttribute.HP] <= 0):
            parent_player : AVGEPlayer = event.target_card.player
            packet = []
            if(parent_player.get_active_card() == event.target_card):
                if(len(parent_player.cardholders[Pile.BENCH]) == 0):
                    e : AVGEEnvironment = event.target_card.env
                    e.winner = parent_player.opponent
                    return self.generate_response()
                swap_with = args.get('swap_with')
                if(swap_with is None):
                    return self.generate_response(ResponseType.REQUIRES_QUERY, {'query_type': 'ko_replace', 'target_player': parent_player})
                if(isinstance(swap_with, AVGECharacterCard) and swap_with in parent_player.cardholders[Pile.BENCH]):
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

class AVGECardAttributeChangePostCheck(PostCheckEventListener):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_3,
                         flags = [AVGEFlag.CARD_ATTR_CHANGE],
                         internal = True)
    def is_valid(self) -> bool:
        return True
    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def assess(self, args) -> Response:
        from .internal_events import AVGECardAttributeChange
        event : AVGECardAttributeChange = self.attached_event
        if(event.attribute == AVGECardAttribute.HP and event.target_card.attributes[AVGECardAttribute.HP] <= 0):
            return self.generate_response(ResponseType.SKIP, {"msg": "KO!"})
        return self.generate_response()
    
class AVGEPlayerAttributeChangeModifier(ModifierEventListener):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_2,
                         flags = [AVGEFlag.PLAYER_ATTR_CHANGE],
                         internal = True)
    def is_valid(self) -> bool:
        return True
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
            if(event.change_amount < 0):
                event.change_amount = 0
        return self.generate_response()

class AVGEPlayerAttributeChangePostChecker(PostCheckEventListener):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_3,
                         flags = [AVGEFlag.PLAYER_ATTR_CHANGE],
                         internal = True)
    def is_valid(self) -> bool:
        return True
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
            return self.generate_response(ResponseType.SKIP, {'msg': 'player has won!'})
        return self.generate_response()

class AVGETransferValidityCheck(AssessorEventListener):
    
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         flags = [AVGEFlag.CARD_TRANSITION],
                         internal = True)
    def is_valid(self) -> bool:
        return True
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
           event.pile_from.pile_type == Pile.BENCH and 
           event.pile_to.pile_type == Pile.ACTIVE):#attempt to retreat
            #only need this once b/c a swap is made of 2 coupled transfers
            player :AVGEPlayer = event.card.player
            if(player.attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN] == 0):
                return self.generate_response(ResponseType.SKIP, {'msg': 'no more swaps this turn!'})
        return self.generate_response()

class AVGEDiscardReactor(ReactorEventListener):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_3,
                         flags = [AVGEFlag.CARD_TRANSITION],
                         internal = True)
    def is_valid(self) -> bool:
        return True
    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def react(self, args) -> Response:
        from .internal_events import TransferCard
        event : TransferCard = self.attached_event
        if(isinstance(event.card, AVGECharacterCard)):#character card getting discarded
            event.card.deactivate_card()
            for tool in event.card.tools_attached:
                self.propose(TransferCard(tool,
                                          event.card.tools_attached,
                                          event.card.player.cardholders[Pile.DISCARD],
                                          ActionTypes.ENV,
                                          None))
        elif(isinstance(event.card, AVGEToolCard) or isinstance(event.card, AVGEStadiumCard)):
            event.card.deactivate_card()
        return self.generate_response()

class AVGEPlayCharacterCardValidityCheck(AssessorEventListener):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         flags = [AVGEFlag.PLAY_CHAR_CARD],
                         internal = True)
    def is_valid(self) -> bool:
        return True
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
    
class AVGEPlayNonCharacterCardValidityCheck(AssessorEventListener):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         flags = [AVGEFlag.PLAY_NONCHAR_CARD],
                         internal = True)
    def is_valid(self) -> bool:
        return True
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
    
class AVGERNGHook(ModifierEventListener):
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_1,
                         flags = [AVGEFlag.PLAY_NONCHAR_CARD, AVGEFlag.PLAY_CHAR_CARD],
                         internal = True)
    def is_valid(self) -> bool:
        return True
    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def modify(self, args) -> Response:
        from .internal_events import PlayNonCharacterCard, PlayCharacterCard
        if(isinstance(self.attached_event, PlayCharacterCard)):
            if(self.attached_event.card.RNG_type[self.attached_event.card_action] is not None):
                resp = args.get("rng_response")
                rng_type = self.attached_event.card.RNG_type[self.attached_event.card_action]
                if(resp is None):
                    return self.generate_response(ResponseType.REQUIRES_QUERY, {'query_type': 'rng', 'rng_type': str(rng_type)})
                else:
                    self.attached_event.card.data_cache[rng_type] = int(resp)
        elif(isinstance(self.attached_event, PlayNonCharacterCard)):
            if(self.attached_event.card.RNG_type is not None):
                resp = args.get("rng_response")
                rng_type = self.attached_event.card.RNG_type
                if(resp is None):
                    return self.generate_response(ResponseType.REQUIRES_QUERY, {'query_type': 'rng', 'rng_type': str(rng_type)})
                else:
                    self.attached_event.card.data_cache[rng_type] = int(resp)
                    
        return self.generate_response()

class AVGERNGEphemerality(ReactorEventListener):
    #a reactor listener that simply ensures that no RNG values are lingering
    def __init__(self):
        super().__init__(group = EngineGroup.INTERNAL_4,
                         flags = [AVGEFlag.PLAY_NONCHAR_CARD, AVGEFlag.PLAY_CHAR_CARD],
                         internal = True)
    def is_valid(self) -> bool:
        return True
    def make_announcement(self) -> bool:
        return False
    def package(self):
        return ""
    def react(self, args) -> Response:
        from .internal_events import PlayNonCharacterCard, PlayCharacterCard
        if(isinstance(self.attached_event, PlayCharacterCard)):
            if(self.attached_event.card.RNG_type[self.attached_event.card_action] is not None):
                rng_type = self.attached_event.card.RNG_type[self.attached_event.card_action]
                if(rng_type in self.attached_event.card.data_cache):
                    del self.attached_event.card.data_cache[rng_type]
        elif(isinstance(self.attached_event, PlayNonCharacterCard)):
            if(self.attached_event.card.RNG_type is not None):
                rng_type = self.attached_event.card.RNG_type
                if(rng_type in self.attached_event.card.data_cache):
                    del self.attached_event.card.data_cache[rng_type]
                    
        return self.generate_response()