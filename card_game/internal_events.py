from .avge_abstracts.AVGEEvent import *
from .avge_abstracts.AVGECards import *
from .avge_abstracts.AVGEPlayer import *
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
        super().__init__([AVGEFlag.CARD_ATTR_CHANGE], catalyst_action,caller_card)
        self.change_amount = change_amount
        self.attribute = attribute
        self.target_card = target_card
        self.change_type = change_type
        self.attribute_modifier_type = attribute_modifier_type
    
    def make_announcement(self):
        return True
    
    def core(self, args :Data = {}) -> Response:
        #you should override this!
        #note that, in place of ACCEPT, you should return CORE 
        if(self.attribute_modifier_type == AVGEAttributeModifier.ADDITIVE):
            self.target_card.attributes[self.attribute] += self.change_amount
        else:
            self.target_card.attributes[self.attribute] = self.change_amount

    def generate_internal_listeners(self):
        #you should override this!
        raise NotImplementedError()
    
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
    
    def make_announcement(self):
        return True
    
    def core(self, args :Data = {}) -> Response:
        if(self.attribute_modifier_type == AVGEAttributeModifier.ADDITIVE):
            self.target_player.attributes[self.attribute] += self.change_amount
        else:
            self.target_player.attributes[self.attribute] = self.change_amount
        return self.generate_response()

    def generate_internal_listeners(self):
        #you should override this!
        raise NotImplementedError()
    
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
        self.card.env.transfer_card(self.card, self.pile_to, self.pile_from)
        return self.generate_response()

    def generate_internal_listeners(self):
        #you should override this!
        raise NotImplementedError()
    
    def package(self):
        return f"{self.card} from {self.pile_from} to {self.pile_to}"
    
class PlayCharacterCard(AVGEEvent):
    def __init__(self, 
                 card : AVGECharacterCard,
                 card_action : ActionTypes,
                 catalyst_action : ActionTypes, 
                 caller_card : Card | None):
        super().__init__([AVGEFlag.CARD_ATTR_CHANGE], catalyst_action,caller_card)
        self.card = card
        self.card_action = card_action
    def core(self, args : Data = {}) -> Response:
        if(self.card_action == ActionTypes.SKIP):
            return self.generate_response()
        else:
            args['type'] = self.card_action
            return self.card.play_card(args)
    def make_announcement(self):
        return True
    def package(self):
        return f"{self.card_action} action from {self.card}"
    