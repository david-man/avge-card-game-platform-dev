from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.catalog.items import ConcertProgram, ConcertTicket

class RachelChen(AVGECharacterCard):
    _ACTIVE_USE_KEY = "rachel_chen_active_used"
    _CARD_PICK_KEY = "rachel_chen_card_pick"
    _TARGET_BASE_KEY = "rachel_chen_satb_key"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.CHOIR, 1, 1)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = False
        self.has_active = True

    @staticmethod
    def can_play_active(card : AVGECharacterCard) -> bool:
        env = card.env
        # once per turn check
        if card.env.player_turn != card.player:
            return False
        last = env.cache.get(card, RachelChen._ACTIVE_USE_KEY, None)
        if last is not None and last == env.round_id:
            return False

        # check discard for ConcertProgram or ConcertTicket
        discard = card.player.cardholders[Pile.DISCARD]
        for c in discard:
            if isinstance(c, (ConcertTicket, ConcertProgram)):
                return True
        return False

    @staticmethod
    def active(card : AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, TransferCard
        discard = card.player.cardholders[Pile.DISCARD]
        hand = card.player.cardholders[Pile.HAND]

        # collect candidate items in discard
        candidates = [c for c in list(discard) if isinstance(c, (ConcertProgram, ConcertTicket))]
        chosen = card.env.cache.get(card, RachelChen._CARD_PICK_KEY, None, True)
        if chosen is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [RachelChen._CARD_PICK_KEY],
                            InputType.SELECTION,
                            lambda r : True,
                            ActionTypes.ACTIVATE_ABILITY,
                            card,
                            {LABEL_FLAG: "rachel_chen_retrieve_item", 
                             TARGETS_FLAG: candidates,
                             DISPLAY_FLAG: list(discard),
                             ALLOW_NONE: True},
                        )
                    ]
                },
            )
        if(isinstance(chosen, AVGECard)):
            card.propose(
                AVGEPacket(
                    [TransferCard(chosen, discard, hand, ActionTypes.ACTIVATE_ABILITY, card)],
                    AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, RachelChen),
                )
            )
            # mark used this round
            card.env.cache.set(card, RachelChen._ACTIVE_USE_KEY, card.env.round_id)

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

        packet : PacketType = []
        # ask player to pick `choir_count` targets (allow repeats)
        keys = [RachelChen._TARGET_BASE_KEY + str(i) for i in range(choir_count)]
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
                            lambda r : True,
                            ActionTypes.ATK_1,
                            card,
                            {LABEL_FLAG: "rachel_chen_atk1_targets",
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
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, RachelChen)))
        return card.generate_response()