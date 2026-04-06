from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class MaggieLi(AVGECharacterCard):
    _ENERGY_REMOVAL_KEY = "maggieli_energy_removal_target"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.STRING, 2, 1, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        card.propose(
            AVGEPacket([
                AVGECardHPChange(
                    card,
                    20,
                    AVGEAttributeModifier.ADDITIVE,
                    CardType.STRING,
                    ActionTypes.ATK_1,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_1, MaggieLi))
        )

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange, AVGEEnergyTransfer, EmptyEvent

        opponent = card.player.opponent

        chosen_target = card.env.cache.get(card, MaggieLi._ENERGY_REMOVAL_KEY, None, True)
        if chosen_target is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [MaggieLi._ENERGY_REMOVAL_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {
                                "query_label": "maggie_li_snap_pizz",
                                "targets": opponent.get_cards_in_play(),
                            },
                        )
                    ]
                },
            )

        packet = [] + [
            AVGECardHPChange(
                opponent.get_active_card(),
                20,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.STRING,
                ActionTypes.ATK_2,
                card,
            )
        ]
        assert isinstance(chosen_target, AVGECharacterCard)
        if len(chosen_target.energy) < 2:
            packet.append(EmptyEvent("MaggieLi ATK2 target lacked enough energy.", ActionTypes.ATK_2, card))
        else:
            for token in list(chosen_target.energy)[:2]:
                packet.append(AVGEEnergyTransfer(token, chosen_target, chosen_target.player, ActionTypes.ATK_2, card))

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, MaggieLi)))
        return card.generate_response()
