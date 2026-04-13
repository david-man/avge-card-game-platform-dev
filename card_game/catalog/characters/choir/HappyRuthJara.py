from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import TransferCard

class HappyRuthJara(AVGECharacterCard):
    _ACTIVE_USE_KEY = "happy_ruth_active_used"
    _TARGET_BASE_KEY = "happy_satb_key"

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.CHOIR, 1, 1)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = False
        self.has_active = True

    @staticmethod
    def can_play_active(card : AVGECharacterCard) -> bool:
        # once per turn, must be on bench and have no tools attached
        # on bench
        if card.cardholder.pile_type != Pile.BENCH:
            return False
        # no tools attached
        if len(card.tools_attached) > 0:
            return False
        # not used this round
        last = card.env.cache.get(None, HappyRuthJara._ACTIVE_USE_KEY, None)
        if last is not None and last == card.env.round_id:
            return False
        return True

    @staticmethod
    def active(card : AVGECharacterCard) -> Response:
        # activating: remove all statuses, reset HP, move to owner's hand(reactor does all of this)
        # move to hand
        hand = card.player.cardholders[Pile.HAND]
        card.propose(
            AVGEPacket(
                [TransferCard(card, card.cardholder, hand, ActionTypes.ACTIVATE_ABILITY, card)],
                AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, HappyRuthJara),
            )
        )
        # mark used this round
        card.env.cache.set(None, HappyRuthJara._ACTIVE_USE_KEY, card.env.round_id)
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange

        player = card.player
        opponent = player.opponent

        # collect player's choir characters in play
        choir_count = 0
        for c in player.get_cards_in_play():
            if c.card_type == CardType.CHOIR:
                choir_count += 1

        if choir_count <= 0:
            return card.generate_response(data={MESSAGE_KEY: "No choir in play!"})

        # build list of opponent character targets (can be chosen multiple times)
        packet = []
 
        # multiple opponent choices: ask player to pick `choir_count` targets (allow repeats)
        keys = [HappyRuthJara._TARGET_BASE_KEY + str(i) for i in range(choir_count)]
        chars = [card.env.cache.get(card, key, None, True) for key in keys]
        if(chars[0] is None):
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            keys,
                            InputType.SELECTION,
                            lambda r :  True,
                            ActionTypes.ATK_1,
                            card,
                            {LABEL_FLAG: "happy_atk1_targets",
                            TARGETS_FLAG: opponent.get_cards_in_play(),
                            DISPLAY_FLAG: opponent.get_cards_in_play(),
                            ALLOW_REPEAT: True},
                        )
                    ]
                },
            )
        else:
            for char in chars:
                assert(isinstance(char, AVGECharacterCard))
                packet.append(
                    AVGECardHPChange(
                        char,
                        20,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.CHOIR,
                        ActionTypes.ATK_1,
                        card,
                    )
                )
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, HappyRuthJara)))
        return card.generate_response()
