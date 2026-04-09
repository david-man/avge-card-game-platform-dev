from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class JuliaCiacerelli(AVGECharacterCard):
    _ATK1_ITEM_KEY = "julia_atk1_item"
    _ENERGY_REMOVAL_KEY = "julia_energy_removal_target"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, PlayNonCharacterCard, EmptyEvent

        opp_hand = card.player.opponent.cardholders[Pile.HAND]
        items = [c for c in opp_hand if isinstance(c, AVGEItemCard)]

        missing = object()
        chosen = card.env.cache.get(card, JuliaCiacerelli._ATK1_ITEM_KEY, missing, True)
        if chosen is missing:
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
                                "display": list(opp_hand),
                                "allow_none": True
                            },
                        )
                    ]
                },
            )
        if(chosen is not None):
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
                                "display": opponent.get_cards_in_play()
                            },
                        )
                    ]
                },
            )

        packet : PacketType = [
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
        def mill_energy() -> PacketType:
            if(len(chosen_target.energy) == 0):
                return []
            else:
                return [AVGEEnergyTransfer(chosen_target.energy[0], chosen_target, chosen_target.env, ActionTypes.ATK_2, card)]
        packet.append(mill_energy)
        packet.append(mill_energy)
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, JuliaCiacerelli)))
        return card.generate_response()
