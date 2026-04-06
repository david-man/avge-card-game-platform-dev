from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class JuliaCiacerelli(AVGECharacterCard):
    _ATK1_ITEM_KEY = "julia_atk1_item"
    _ENERGY_REMOVAL_KEY = "julia_energy_removal_target"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, PlayNonCharacterCard

        opp_hand = card.player.opponent.cardholders[Pile.HAND]
        items = [c for c in opp_hand if isinstance(c, AVGEItemCard)]
        if len(items) == 0:
            return card.generate_response()

        chosen = card.env.cache.get(card, JuliaCiacerelli._ATK1_ITEM_KEY, None, True)
        if chosen is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [JuliaCiacerelli._ATK1_ITEM_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {
                                "query_label": "julia_ciacerelli_atk1",
                                "targets": items,
                            },
                        )
                    ]
                },
            )

        card.propose(
            AVGEPacket([
                PlayNonCharacterCard(chosen, ActionTypes.ATK_1, card)
            ], AVGEEngineID(card, ActionTypes.ATK_1, JuliaCiacerelli))
        )
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange, AVGEEnergyTransfer, EmptyEvent

        opponent = card.player.opponent

        chosen_target = card.env.cache.get(card, JuliaCiacerelli._ENERGY_REMOVAL_KEY, None, True)
        if chosen_target is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [JuliaCiacerelli._ENERGY_REMOVAL_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {
                                "query_label": "julia_ciacerelli_snap_pizz",
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
            packet.append(EmptyEvent("JuliaCiacerelli ATK2 target lacked enough energy.", ActionTypes.ATK_2, card))
        else:
            for token in list(chosen_target.energy)[:2]:
                packet.append(AVGEEnergyTransfer(token, chosen_target, chosen_target.player, ActionTypes.ATK_2, card))

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, JuliaCiacerelli)))
        return card.generate_response()
