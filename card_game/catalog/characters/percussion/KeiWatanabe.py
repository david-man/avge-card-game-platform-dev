from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, AVGECardHPChange, PlayCharacterCard, AVGEEnergyTransfer


class KeiWatanabe(AVGECharacterCard):
    _ATK1_TARGET_KEY = "kei_atk1_target"
    _ATK2_COPY_KEY = "kei_atk2_copy_card"
    _ATK2_MOVE_KEY = "kei_atk2_move_choice"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PERCUSSION, 0, 1, 3)
        self.atk_1_name = 'Rudiments'
        self.atk_2_name = 'Drum Kid Workshop'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        opponent = card.player.opponent
        candidates = opponent.get_cards_in_play()
        missing = object()
        chosen = card.env.cache.get(card, KeiWatanabe._ATK1_TARGET_KEY, missing, True)
        if chosen is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [KeiWatanabe._ATK1_TARGET_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                'Rudiments: 10 damage to one opposing character',
                                list(candidates),
                                list(candidates),
                                False,
                                False,
                            )
                        )
                    ]),
            )
        if not isinstance(chosen, AVGECharacterCard):
            return self.generic_response(card, ActionTypes.ATK_1)

        def generate_damage() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    chosen,
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        card.propose(AVGEPacket([generate_damage], AVGEEngineID(card, ActionTypes.ATK_1, KeiWatanabe)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        in_play: list[AVGECharacterCard] = []
        for player in card.env.players.values():
            for c in player.get_cards_in_play():
                if isinstance(c, AVGECharacterCard):
                    in_play.append(c)

        candidates = [c for c in in_play if c.card_type == CardType.PERCUSSION]
        if len(candidates) == 0:
            return self.generic_response(card, ActionTypes.ATK_2)

        missing = object()
        chosen = card.env.cache.get(card, KeiWatanabe._ATK2_COPY_KEY, missing, True)

        if chosen is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [KeiWatanabe._ATK2_COPY_KEY],
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            CardSelectionQuery(
                                'Drum Kid Workshop: Choose a percussion character in play whose attack you\'d like to use.',
                                list(candidates),
                                list(candidates),
                                False,
                                False,
                            )
                        )
                    ]),
            )

        if not isinstance(chosen, AVGECharacterCard) or chosen not in candidates:
            return self.generic_response(card, ActionTypes.ATK_2)

        move_options: list[str] = []
        if chosen.atk_1_name is not None:
            move_options.append('ATK_1')
        if chosen.atk_2_name is not None and chosen != card:
            move_options.append('ATK_2')

        if len(move_options) == 0:
            return self.generic_response(card, ActionTypes.ATK_2)

        chosen_move = card.env.cache.get(card, KeiWatanabe._ATK2_MOVE_KEY, missing, True)
        if chosen_move is missing:
            display: list[str] = []
            if 'ATK_1' in move_options:
                display.append(f'{chosen.atk_1_name}')
            if 'ATK_2' in move_options:
                display.append(f'{chosen.atk_2_name}')

            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [KeiWatanabe._ATK2_MOVE_KEY],
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            StrSelectionQuery(
                                'Choose which attack to use',
                                move_options,
                                display,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        if not isinstance(chosen_move, str) or chosen_move not in move_options:
            return self.generic_response(card, ActionTypes.ATK_2)

        action_type = ActionTypes.ATK_1 if chosen_move == chosen.atk_1_name else ActionTypes.ATK_2

        def generate_transfer_packet() -> PacketType:
            packet : PacketType = []
            for token in list(card.energy):
                packet.append(AVGEEnergyTransfer(token, card, chosen, ActionTypes.ATK_2, card, None))
            return packet

        card.propose(AVGEPacket([PlayCharacterCard(chosen, action_type, ActionTypes.ATK_2, card)], AVGEEngineID(card, ActionTypes.ATK_2, KeiWatanabe)))
        card.propose(AVGEPacket([generate_transfer_packet], AVGEEngineID(card, ActionTypes.ATK_2, KeiWatanabe)), -1)
        return self.generic_response(card, ActionTypes.ATK_2)
