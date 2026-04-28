from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, AVGECardHPChange, PlayCharacterCard

class CocoZeng(AVGECharacterCard):
    _ATK2_COIN_BASE = "cocozeng_atk2_coin_"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 2, 2, 3)
        self.atk_1_name = 'Glissando'
        self.atk_2_name = 'Inventory Management'

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        _, used_last_turn_idx = card.env.check_history(
            card.player.get_last_turn(),
            PlayCharacterCard,
            {
                'card': card,
                'card_action': ActionTypes.ATK_1,
                'caller': card,
            },
        )
        if used_last_turn_idx != -1:
            return Response(
                ResponseType.CORE,
                Notify('Glissando cannot be used this turn.', [card.player.unique_id], default_timeout),
            )

        def gen() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, CocoZeng))
        )

        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        n = len(card.player.cardholders[Pile.HAND])
        if n <= 0:
            return Response(ResponseType.CORE, Notify(f"{str(card)} used Inventory Management, but there was no inventory to manage...", all_players, default_timeout))

        coin_keys = [CocoZeng._ATK2_COIN_BASE + str(i) for i in range(n)]
        missing = object()
        vals = [card.env.cache.get(card, key, missing, True) for key in coin_keys]
        if any(v is missing for v in vals):
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            coin_keys,
                            lambda res: True,
                            ActionTypes.ATK_2,
                            card,
                            CoinflipData('Inventory Management: Flip a coin for each card in your hand')
                        )
                    ]),
            )

        heads = sum(int(v) for v in vals if isinstance(v, int))
        if heads <= 0:
            return self.generic_response(card, ActionTypes.ATK_2)

        def gen() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    30 * heads,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_2,
                    None,
                    card,
                )
            )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_2, CocoZeng))
        )

        return self.generic_response(card, ActionTypes.ATK_2)
