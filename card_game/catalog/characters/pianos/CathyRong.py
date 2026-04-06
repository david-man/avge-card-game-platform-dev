from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class CathyRong(AVGECharacterCard):
    _ENERGY_TARGET_KEY = "cathy_energy_target"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PIANO, 2, 2, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange, AVGEEnergyTransfer, EmptyEvent

        opponent = card.player.opponent
        bench_candidates = [c for c in opponent.cardholders[Pile.BENCH] if isinstance(c, AVGECharacterCard) and len(c.energy) >= 1]
        if len(bench_candidates) == 0:
            card.propose(
                AVGEPacket([
                    AVGECardHPChange(
                        opponent.get_active_card(),
                        20,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PIANO,
                        ActionTypes.ATK_1,
                        card,
                    )
                ], AVGEEngineID(card, ActionTypes.ATK_1, CathyRong))
            )
            return card.generate_response()

        chosen = card.env.cache.get(card, CathyRong._ENERGY_TARGET_KEY, None, True)
        if chosen is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [CathyRong._ENERGY_TARGET_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {
                                "query_label": "cathy_energy_target",
                                "targets": bench_candidates,
                                "allow_none": True,
                            },
                        )
                    ]
                },
            )

        base_damage = AVGECardHPChange(
            opponent.get_active_card(),
            20,
            AVGEAttributeModifier.SUBSTRACTIVE,
            CardType.PIANO,
            ActionTypes.ATK_1,
            card,
        )
        if chosen is None:
            card.propose(AVGEPacket([base_damage], AVGEEngineID(card, ActionTypes.ATK_1, CathyRong)))
            return card.generate_response()
        assert isinstance(chosen, AVGECharacterCard)
        card.propose(
            AVGEPacket([
                base_damage,
                AVGEEnergyTransfer(chosen.energy[0], chosen, chosen.player, ActionTypes.ATK_1, card),
            ], AVGEEngineID(card, ActionTypes.ATK_1, CathyRong))
        )
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChangeCreator

        dmg = 50
        bench = [c for c in card.player.cardholders[Pile.BENCH] if isinstance(c, AVGECharacterCard) and c != card and c.card_type == CardType.PIANO]
        if len(bench) > 0:
            dmg = 80

        card.propose(
            AVGEPacket([
                AVGECardHPChangeCreator(
                    lambda: card.player.opponent.get_active_card(),
                    dmg,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_2,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_2, CathyRong))
        )

        return card.generate_response()
