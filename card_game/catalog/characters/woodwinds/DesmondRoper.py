from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.constants import ActionTypes

class DesmondRoper(AVGECharacterCard):
    _PLAYED_ROUND_KEY = "desmond_played_round"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 1, 2, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        owner_card = card

        class _DesmondPlayTracker(AVGEReactor):
            def __init__(self):
                super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.ATK_2, DesmondRoper), group=EngineGroup.EXTERNAL_REACTORS)

            def event_match(self, event):
                from card_game.internal_events import TransferCard

                if not isinstance(event, TransferCard):
                    return False
                if event.card != owner_card:
                    return False
                return event.pile_to.pile_type == Pile.ACTIVE

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                return

            def react(self, args=None):
                if args is None:
                    args = {}
                owner_card.env.cache.set(owner_card, DesmondRoper._PLAYED_ROUND_KEY, owner_card.env.round_id)
                return self.generate_response()

        owner_card.add_listener(_DesmondPlayTracker())
        return owner_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        def hit() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                ),
                AVGECardHPChange(
                    card,
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                ),
            ]
        card.propose(
            AVGEPacket([hit], AVGEEngineID(card, ActionTypes.ATK_1, DesmondRoper))
        )
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        damage = 40
        played_round = card.env.cache.get(card, DesmondRoper._PLAYED_ROUND_KEY, None, True)
        if played_round == card.env.round_id:
            damage = 100

        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                return [
                    AVGECardHPChange(
                        active,
                        damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_2,
                        card,
                    )
                ]
            return []

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, DesmondRoper)))
        return card.generate_response()
