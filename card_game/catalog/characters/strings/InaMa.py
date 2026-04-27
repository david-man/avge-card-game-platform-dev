from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGEEnergyTransfer, InputEvent, AVGECardHPChange, PlayCharacterCard, EmptyEvent


class InaMa(AVGECharacterCard):
    _ENERGY_MOVE_SELECTION_KEY = "inama_energy_move_selection"
    _COIN_KEY_0 = "inama_coin_0"
    _COIN_KEY_1 = "inama_coin_1"
    _COIN_KEY_2 = "inama_coin_2"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 2, 3)
        self.atk_1_name = 'Triple Stop'
        self.active_name = 'Borrow a Bow'

    def can_play_active(self) -> bool:
        if self.env is None or self.player is None:
            return False
        if self.env.player_turn != self.player:
            return False

        _, already_used_idx = self.env.check_history(
            self.env.round_id,
            PlayCharacterCard,
            {
                'card': self,
                'card_action': ActionTypes.ACTIVATE_ABILITY,
                'caller': self,
            },
        )
        if already_used_idx != -1:
            return False

        for c in self.player.get_cards_in_play():
            if isinstance(c, AVGECharacterCard) and c.card_type == CardType.STRING and c != self and len(c.energy) >= 1:
                return True
        return False

    def active(self) -> Response:
        candidates = [
            c for c in self.player.get_cards_in_play()
            if isinstance(c, AVGECharacterCard) and c.card_type == CardType.STRING and c != self and len(c.energy) >= 1
        ]

        chosen = self.env.cache.get(self, InaMa._ENERGY_MOVE_SELECTION_KEY, None, True)
        if chosen is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            self.player,
                            [InaMa._ENERGY_MOVE_SELECTION_KEY],
                            lambda r: True,
                            ActionTypes.ACTIVATE_ABILITY,
                            self,
                            CardSelectionQuery(
                                'Borrow a Bow: Move 1 energy from one of your String characters to this character',
                                candidates,
                                candidates,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        assert isinstance(chosen, AVGECharacterCard)
        if len(chosen.energy) <= 0:
            return Response(ResponseType.CORE, Data())

        self.propose(
            AVGEPacket([
                AVGEEnergyTransfer(chosen.energy[0], chosen, self, ActionTypes.ACTIVATE_ABILITY, self, None)
            ], AVGEEngineID(self, ActionTypes.ACTIVATE_ABILITY, InaMa))
        )
        return self.generic_response(self, ActionTypes.ACTIVATE_ABILITY)

    def atk_1(self, card: AVGECharacterCard) -> Response:
        r0 = card.env.cache.get(card, InaMa._COIN_KEY_0, None, True)
        r1 = card.env.cache.get(card, InaMa._COIN_KEY_1, None, True)
        r2 = card.env.cache.get(card, InaMa._COIN_KEY_2, None, True)
        if r0 is None or r1 is None or r2 is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [InaMa._COIN_KEY_0, InaMa._COIN_KEY_1, InaMa._COIN_KEY_2],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CoinflipData('Triple Stop: Flip 3 coins.')
                        )
                    ]),
            )

        heads = int(r0) + int(r1) + int(r2)
        if(heads == 0):
            card.propose(AVGEPacket([
                EmptyEvent(
                    ActionTypes.ATK_1,
                    card,
                    ResponseType.CORE,
                    self.generic_response(card, ActionTypes.ATK_1).data
                )
            ], AVGEEngineID(card, ActionTypes.ATK_1, InaMa)))
        for _ in range(max(0, heads)):
            def generate_packet() -> PacketType:
                active = card.player.opponent.get_active_card()
                ret: PacketType = []
                if isinstance(active, AVGECharacterCard):
                    ret.append(
                        AVGECardHPChange(
                            active,
                            40,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.STRING,
                            ActionTypes.ATK_1,
                            None,
                            card,
                        )
                    )
                return ret

            card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, InaMa)))

        return self.generic_response(card, ActionTypes.ATK_1)
