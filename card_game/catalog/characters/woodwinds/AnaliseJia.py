from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange, AVGEEnergyTransfer, InputEvent, PlayNonCharacterCard, TransferCard


class AnaliseJia(AVGECharacterCard):
    _ATK1_ITEM_KEY = 'analisejia_atk1_item_choice'

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.WOODWIND, 1, 2, 3)
        self.atk_1_name = 'Reed Replenishment'
        self.atk_2_name = 'Banana Bread for Everyone!'

    def _get_played_items_this_turn(self, card: AVGECharacterCard) -> list[AVGEItemCard]:
        # Use repeated history search calls to collect this turn's played Item cards.
        played: list[AVGEItemCard] = []
        seen: set[int] = set()
        idx = 0
        while True:
            event, found_idx = card.env.check_history(card.env.round_id, PlayNonCharacterCard, {}, idx)
            if found_idx == -1 or event is None:
                break
            if not isinstance(event, PlayNonCharacterCard):
                idx = found_idx + 1
                continue
            if not isinstance(event.card, AVGEItemCard):
                idx = found_idx + 1
                continue
            if event.card.player != card.player:
                idx = found_idx + 1
                continue
            obj_id = id(event.card)
            if obj_id in seen:
                idx = found_idx + 1
                continue
            seen.add(obj_id)
            played.append(event.card)
            idx = found_idx + 1
        return played

    def atk_1(self, card: AVGECharacterCard) -> Response:
        played_items = self._get_played_items_this_turn(card)
        retrievable_items = [
            i for i in played_items
            if i.cardholder is not None and i.cardholder != card.player.cardholders[Pile.HAND]
        ]

        missing = object()
        chosen = card.env.cache.get(card, AnaliseJia._ATK1_ITEM_KEY, missing, True)
        if chosen is missing and len(retrievable_items) > 0:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [AnaliseJia._ATK1_ITEM_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                'Reed Replenishment: You may put an Item card you played this turn into your hand.',
                                retrievable_items,
                                retrievable_items,
                                True,
                                False,
                            )
                        )
                    ]),
            )

        hand = card.player.cardholders[Pile.HAND]

        def generate_packet() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )

            if isinstance(chosen, AVGEItemCard) and chosen in retrievable_items and chosen.cardholder is not None:
                packet.append(
                    TransferCard(
                        chosen,
                        chosen.cardholder,
                        hand,
                        ActionTypes.ATK_1,
                        card,
                        None,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, AnaliseJia)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        def packet() -> PacketType:
            p: PacketType = []
            for character in card.player.get_cards_in_play():
                if isinstance(character, AVGECharacterCard):
                    p.append(
                        AVGECardHPChange(
                            character,
                            30,
                            AVGEAttributeModifier.ADDITIVE,
                            CardType.ALL,
                            ActionTypes.ATK_2,
                            None,
                            card,
                        )
                    )
            if len(card.energy) > 0:
                p.append(
                    AVGEEnergyTransfer(
                        card.energy[0],
                        card,
                        card.env,
                        ActionTypes.ATK_2,
                        card,
                        None,
                    )
                )
            return p

        card.propose(AVGEPacket([packet], AVGEEngineID(card, ActionTypes.ATK_2, AnaliseJia)))
        return self.generic_response(card, ActionTypes.ATK_2)
