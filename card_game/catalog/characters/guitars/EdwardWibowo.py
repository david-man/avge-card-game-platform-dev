from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class _EdwardGuitarBoost(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard, round_active: int):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, EdwardWibowo), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card
        self.round_active = round_active

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if not isinstance(event.caller_card, AVGECharacterCard):
            return False
        if event.caller_card.player != self.owner_card.player:
            return False
        if event.change_type != CardType.GUITAR:
            return False
        if self.owner_card.env.round_id != self.round_active:
            return False
        return True

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self.owner_card.env.round_id > self.round_active:
            self.invalidate()

    def modify(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import AVGECardHPChange

        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        event.modify_magnitude(40)
        return self.generate_response()


class EdwardWibowo(AVGECharacterCard):
    _ATK1_COIN_BASE = "edward_atk1_coin_"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.GUITAR, 2, 2, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGEEnergyTransfer

        opp_active = card.player.opponent.get_active_card()
        n = len(opp_active.energy)
        if n <= 0:
            return card.generate_response(data={MESSAGE_KEY: "Opponent active card has no energy attached"})

        coin_keys = [EdwardWibowo._ATK1_COIN_BASE + str(i) for i in range(n)]
        coin_vals = [card.env.cache.get(card, key, None, True) for key in coin_keys]
        if coin_vals[0] is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            coin_keys,
                            InputType.COIN,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {LABEL_FLAG: "edward_wibowo_atk_1"},
                        )
                    ]
                },
            )
        heads = sum(int(v) for v in coin_vals if v is not None)
        if heads <= 0:
            return card.generate_response()
        def generate_packet() -> PacketType:
            removable = min(heads, len(opp_active.energy))
            packet : PacketType = []
            packet = [
                AVGEEnergyTransfer(token, opp_active, opp_active.player, ActionTypes.ATK_1, card)
                for token in list(opp_active.energy)[:removable]
            ]
            return packet
        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, EdwardWibowo)))

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_2,
                    card,
                )
            ]
        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_2, EdwardWibowo))
        )
        card.add_listener(_EdwardGuitarBoost(card, card.player.get_next_turn()))

        return card.generate_response()
