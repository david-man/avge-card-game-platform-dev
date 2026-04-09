from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class MaggieLi(AVGECharacterCard):
    _ENERGY_REMOVAL_KEY = "maggieli_energy_removal_target"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.STRING, 2, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
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
                                "display":opponent.get_cards_in_play()
                            },
                        )
                    ]
                },
            )
        def atk() -> PacketType:
            return [
                AVGECardHPChange(
                    opponent.get_active_card(),
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_2,
                    card,
                )
            ]
        packet : PacketType = [atk]
        assert isinstance(chosen_target, AVGECharacterCard)
        def gen() -> PacketType:
            k : PacketType = []
            if len(chosen_target.energy) == 0:
                k.append(EmptyEvent(ActionTypes.ATK_2, card, response_data = {MESSAGE_KEY:"Failed to discard any energy"}))
            else:
                for token in list(chosen_target.energy)[:2]:
                    k.append(AVGEEnergyTransfer(token, chosen_target, chosen_target.env, ActionTypes.ATK_2, card))
            return k
        packet.append(gen)

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, MaggieLi)))
        return card.generate_response()
