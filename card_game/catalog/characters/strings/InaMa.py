from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes


class InaMa(AVGECharacterCard):
    _ACTIVE_USED_KEY = "inama_active_used"
    _ENERGY_MOVE_SELECTION_KEY = "inama_energy_move_selection"
    _COIN_KEY_0 = "inama_coin_0"
    _COIN_KEY_1 = "inama_coin_1"
    _COIN_KEY_2 = "inama_coin_2"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = False
        self.has_active = True

    @staticmethod
    def can_play_active(card: AVGECharacterCard) -> bool:
        if card.env.player_turn != card.player:
            return False
        already_used = card.env.cache.get(card, InaMa._ACTIVE_USED_KEY, None)
        if card.env.round_id == already_used:
            return False
        for c in card.player.get_cards_in_play():
            if c.card_type == CardType.STRING and len(c.energy) >= 1 and c!= card:
                return True
        return False

    @staticmethod
    def active(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGEEnergyTransfer, InputEvent, EmptyEvent

        candidates = [c for c in card.player.get_cards_in_play() if c.card_type == CardType.STRING and len(c.energy) >= 1 and not c == card]
        if(len(candidates) == 0):
            return card.generate_response(data={MESSAGE_KEY: "No strings cards with energy!"})
        chosen = card.env.cache.get(card, InaMa._ENERGY_MOVE_SELECTION_KEY, None, True)
        
        if chosen is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [InaMa._ENERGY_MOVE_SELECTION_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ACTIVATE_ABILITY,
                            card,
                            {
                                LABEL_FLAG: "ina_ma_active",
                                TARGETS_FLAG: candidates,
                                DISPLAY_FLAG: card.player.get_cards_in_play()
                            },
                        )
                    ]
                },
            )
        assert isinstance(chosen, AVGECharacterCard)
        if len(chosen.energy) <= 0:
            return card.generate_response(data={MESSAGE_KEY: "InaMa card had no energy at resolve."})
        else:
            card.propose(
                AVGEPacket([
                    AVGEEnergyTransfer(chosen.energy[0], chosen, card, ActionTypes.ACTIVATE_ABILITY, card)
                ], AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, InaMa))
            )
        card.env.cache.set(card, InaMa._ACTIVE_USED_KEY, card.env.round_id)
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent

        r0 = card.env.cache.get(card, InaMa._COIN_KEY_0, None, True)
        r1 = card.env.cache.get(card, InaMa._COIN_KEY_1, None, True)
        r2 = card.env.cache.get(card, InaMa._COIN_KEY_2, None, True)
        if r0 is None or r1 is None or r2 is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [InaMa._COIN_KEY_0, InaMa._COIN_KEY_1, InaMa._COIN_KEY_2],
                            InputType.COIN,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {LABEL_FLAG: "ina_ma_triple_stop"},
                        )
                    ]
                },
            )

        heads = int(r0) + int(r1) + int(r2)
        if heads > 0:
            def generate_packet() -> PacketType:
                active = card.player.opponent.get_active_card()
                if not isinstance(active, AVGECharacterCard):
                    return []
                return [
                    AVGECardHPChange(
                        active,
                        40 * heads,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_1,
                        card,
                    )
                ]

            card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, InaMa)))

        return card.generate_response()
