from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import TransferCard

class HappyRuthJara(AVGECharacterCard):
    _COIN_KEY_0 = "happyruthjara_coin_0"
    _COIN_KEY_1 = "happyruthjara_coin_1"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.CHOIR, 1, 3)
        self.atk_1_name = 'Coloratura'
        self.active_name = 'Leave Rehearsal Early'
        self.has_active = True

    def can_play_active(self) -> bool:
        if self.env is None or self.player is None or self.cardholder is None:
            return False
        if self.env.player_turn != self.player:
            return False
        if self.cardholder.pile_type != Pile.BENCH:
            return False
        if len(self.tools_attached) > 0:
            return False

        _, played_from_hand_to_bench_idx = self.env.check_history(
            self.env.round_id,
            TransferCard,
            {
                'card': self,
                'pile_from': self.player.cardholders[Pile.HAND],
                'pile_to': self.player.cardholders[Pile.BENCH],
            },
        )
        if played_from_hand_to_bench_idx != -1:
            return False
        return True

    def active(self) -> Response:
        hand = self.player.cardholders[Pile.HAND]
        self.propose(
            AVGEPacket(
                [TransferCard(self, self.cardholder, hand, ActionTypes.ACTIVATE_ABILITY, self, None)],
                AVGEEngineID(self, ActionTypes.ACTIVATE_ABILITY, HappyRuthJara),
            )
        )
        return Response(ResponseType.CORE, Notify(f"{str(self)} left rehearsal early...", all_players, default_timeout))

    def atk_1(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange

        r0 = card.env.cache.get(card, HappyRuthJara._COIN_KEY_0, None, True)
        r1 = card.env.cache.get(card, HappyRuthJara._COIN_KEY_1, None, True)
        if r0 is None or r1 is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[InputEvent](
                    [
                        InputEvent(
                            card.player,
                            [HappyRuthJara._COIN_KEY_0, HappyRuthJara._COIN_KEY_1],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CoinflipData('Coloratura: Flip 2 coins.')
                        )
                    ]
                )
            )

        damage = 30 + (40 if int(r0) + int(r1) == 2 else 0)

        def generate_packet() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.CHOIR,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, HappyRuthJara)))
        return self.generic_response(card, ActionTypes.ATK_1)
