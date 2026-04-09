from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes


class KeiWatanabe(AVGECharacterCard):
    _ATK1_TARGET_KEY = "kei_atk1_target"
    _ATK2_COPY_KEY = "kei_atk2_copy_card"
    _ATK2_MOVE_KEY = "kei_atk2_move_choice"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PERCUSSION, 2, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange

        opponent = card.player.opponent
        candidates = opponent.get_cards_in_play()
        chosen = card.env.cache.get(card, KeiWatanabe._ATK1_TARGET_KEY, None, True)
        if chosen is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [KeiWatanabe._ATK1_TARGET_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {
                                "query_label": "kei_watanabe_rudiments",
                                "targets": list(candidates),
                                "display": list(candidates)
                            },
                        )
                    ]
                },
            )

        card.propose(
            AVGEPacket([
                AVGECardHPChange(
                    chosen,
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.ATK_1,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_1, KeiWatanabe))
        )

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, PlayCharacterCard, AVGEEnergyTransfer, EmptyEvent

        candidates = [
            c for c in (card.player.get_cards_in_play() + card.player.opponent.get_cards_in_play())
            if c.card_type == CardType.PERCUSSION
        ]
        if len(candidates) == 0:
            return card.generate_response(data={MESSAGE_KEY: "No percussion on bench"})

        missing = object()
        chosen = card.env.cache.get(card, KeiWatanabe._ATK2_COPY_KEY, missing, True)
        action_type = card.env.cache.get(card, KeiWatanabe._ATK2_MOVE_KEY, missing, True)
        if chosen is missing:
            def _valid(result) -> bool:
                if len(result) != 2:
                    return False
                sel = result[0]
                action = result[1]
                if not isinstance(sel, AVGECharacterCard) or action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
                    return False
                if sel not in candidates:
                    return False
                if action == ActionTypes.ATK_1 and not sel.has_atk_1:
                    return False
                if action == ActionTypes.ATK_2 and not sel.has_atk_2:
                    return False
                return True

            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [KeiWatanabe._ATK2_COPY_KEY, KeiWatanabe._ATK2_MOVE_KEY],
                            InputType.DETERMINISTIC,
                            _valid,
                            ActionTypes.ATK_2,
                            card,
                            {
                                "query_label": "kei_watanabe_drumkidworkshop",
                                "targets": list(candidates),
                                "display": list(candidates),
                                "actions": [ActionTypes.ATK_1, ActionTypes.ATK_2],
                            },
                        )
                    ]
                },
            )
        assert isinstance(chosen, AVGECharacterCard)
        assert isinstance(action_type, ActionTypes)
        
        def generate_packet() -> PacketType:
            packet : PacketType = []
            if len(card.energy) == 0:
                packet.append(
                    EmptyEvent(
                        ActionTypes.ATK_2,
                        card,
                        response_data={MESSAGE_KEY: "KeiWatanabe copied attack, but has no energy to transfer"},
                    )
                )
                return packet
            for token in list(card.energy):
                packet.append(AVGEEnergyTransfer(token, card, chosen, ActionTypes.ATK_2, card))
            return packet
        card.propose(AVGEPacket([PlayCharacterCard(chosen, action_type, ActionTypes.ATK_2, card), generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, KeiWatanabe)))
        return card.generate_response()
