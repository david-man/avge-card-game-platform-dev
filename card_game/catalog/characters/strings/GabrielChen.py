from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, AVGECardHPChange

class GabrielChen(AVGECharacterCard):
    _COIN_KEY_0 = "gabrielchen_coin_0"
    _COIN_KEY_1 = "gabrielchen_coin_1"
    _ATK1_SELECTION_KEY = "gabrielchen_atk1_target"
    _ATK2_SELECTION_BASE_KEY = "gabrielchen_atk2_targets"
    _ATK2_MODE_KEY = "gabrielchen_atk2_mode"

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.STRING, 1, 1, 2)
        self.atk_1_name = 'You know what it is'
        self.atk_2_name = 'Harmonics'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        if card.hp != 60:
            return self.generic_response(card, ActionTypes.ATK_1)

        targets = [c for c in card.player.opponent.get_cards_in_play() if isinstance(c, AVGECharacterCard)]
        if len(targets) == 0:
            return self.generic_response(card, ActionTypes.ATK_1)

        chosen = card.env.cache.get(card, GabrielChen._ATK1_SELECTION_KEY, None, True)
        if chosen is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [GabrielChen._ATK1_SELECTION_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                'You know what it is: Deal 70 damage to one opposing character',
                                targets,
                                targets,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        def generate_packet() -> PacketType:
            packet: PacketType = []
            if isinstance(chosen, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        chosen,
                        70,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, GabrielChen)))

        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        r0 = card.env.cache.get(card, GabrielChen._COIN_KEY_0, None)
        r1 = card.env.cache.get(card, GabrielChen._COIN_KEY_1, None)
        if r0 is None or r1 is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [GabrielChen._COIN_KEY_0, GabrielChen._COIN_KEY_1],
                            lambda res: True,
                            ActionTypes.ATK_2,
                            card,
                            CoinflipData('Harmonics: Flip two coins.')
                        )
                    ]),
            )

        heads = int(r0) + int(r1)
        if heads != 2:
            card.env.cache.delete(card, GabrielChen._COIN_KEY_0)
            card.env.cache.delete(card, GabrielChen._COIN_KEY_1)
            return self.generic_response(card, ActionTypes.ATK_2)

        mode = card.env.cache.get(card, GabrielChen._ATK2_MODE_KEY, None)
        if mode is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [GabrielChen._ATK2_MODE_KEY],
                            lambda r : True,
                            ActionTypes.ATK_2,
                            card,
                            StrSelectionQuery(
                                'Harmonics: Choose one effect',
                                ['Deal 60 to three opposing characters', 'Deal 70 to two opposing characters'],
                                ['Deal 60 to three opposing characters', 'Deal 70 to two opposing characters'],
                                False,
                                False,
                            )
                        )
                    ]),
            )

        targets = [c for c in card.player.opponent.get_cards_in_play() if isinstance(c, AVGECharacterCard)]
        req_count = 3 if mode == 'Deal 60 to three opposing characters' else 2
        count = min(req_count, len(targets))
        if count == 0:
            card.env.cache.delete(card, GabrielChen._ATK2_MODE_KEY)
            card.env.cache.delete(card, GabrielChen._COIN_KEY_0)
            card.env.cache.delete(card, GabrielChen._COIN_KEY_1)
            return self.generic_response(card, ActionTypes.ATK_2)

        keys = [GabrielChen._ATK2_SELECTION_BASE_KEY + str(i) for i in range(count)]
        chosen = [card.env.cache.get(card, key, None, True) for key in keys]
        if chosen[0] is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            keys,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            CardSelectionQuery(
                                'Harmonics: Choose opposing targets',
                                targets,
                                targets,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        dmg_amt = 60 if mode == 'Deal 60 to three opposing characters' else 70

        def generate_packet() -> PacketType:
            packet: PacketType = []
            for tgt in chosen:
                if isinstance(tgt, AVGECharacterCard):
                    packet.append(
                        AVGECardHPChange(
                            tgt,
                            dmg_amt,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.STRING,
                            ActionTypes.ATK_2,
                            None,
                            card,
                        )
                    )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, GabrielChen)))
        card.env.cache.delete(card, GabrielChen._ATK2_MODE_KEY)
        card.env.cache.delete(card, GabrielChen._COIN_KEY_0)
        card.env.cache.delete(card, GabrielChen._COIN_KEY_1)
        return self.generic_response(card, ActionTypes.ATK_2)
