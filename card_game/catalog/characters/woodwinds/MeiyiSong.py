from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange, InputEvent, PlayNonCharacterCard, TransferCard

class MeiyiSong(AVGECharacterCard):
    _ATK1_ITEM_KEY = 'meiyisong_atk1_item_choice'

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.WOODWIND, 1, 2, 2)
        self.atk_1_name = 'Reed Replenishment'
        self.atk_2_name = 'Clarinet Solo'

    def _get_played_items_this_turn(self, card: AVGECharacterCard) -> list[AVGEItemCard]:
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

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        played_items = self._get_played_items_this_turn(card)
        retrievable_items = [
            i for i in played_items
            if i.cardholder is not None and i.cardholder != card.player.cardholders[Pile.HAND]
        ]

        missing = object()
        chosen = card.env.cache.get(card, MeiyiSong._ATK1_ITEM_KEY, missing, True)
        if chosen is missing and len(retrievable_items) > 0:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                    InputEvent(
                        card.player,
                        [MeiyiSong._ATK1_ITEM_KEY],
                        lambda r: True,
                        ActionTypes.ATK_1,
                        card,
                        CardSelectionQuery(
                            'Reed Replenishment: You may put an Item card you played this turn into your hand.',
                            retrievable_items,
                            retrievable_items,
                            True,
                            False,
                        ),
                    )
                ]),
            )

        def gen() -> PacketType:
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
                        card.player.cardholders[Pile.HAND],
                        ActionTypes.ATK_1,
                        card,
                        None,
                    )
                )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, MeiyiSong))
        )
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        all_characters = card.player.get_cards_in_play() + card.player.opponent.get_cards_in_play()
        other_ww_count = sum(
            1
            for character in all_characters
            if isinstance(character, AVGECharacterCard) and character != card and character.card_type == CardType.WOODWIND
        )
        total_damage = 20 + (50 if other_ww_count == 0 else 0)

        def gen() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        total_damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
            )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_2, MeiyiSong))
        )

        return self.generic_response(card, ActionTypes.ATK_2)
