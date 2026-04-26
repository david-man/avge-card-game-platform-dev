from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange, InputEvent, PlayCharacterCard, TransferCard


class IzzyChen(AVGECharacterCard):
    _ACTIVE_STADIUM_CHOICE = 'izzy_stadium_choice'

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.WOODWIND, 2, 2)
        self.active_name = 'BAI Wrangler'
        self.atk_1_name = 'Overblow'

    def can_play_active(self) -> bool:
        if self.env is None or self.player is None:
            return False
        if self.env.player_turn != self.player:
            return False

        discard = self.player.cardholders[Pile.DISCARD]
        if len([c for c in discard if isinstance(c, AVGEStadiumCard)]) == 0:
            return False

        _, used_idx = self.env.check_history(
            self.env.round_id,
            PlayCharacterCard,
            {
                'card': self,
                'card_action': ActionTypes.ACTIVATE_ABILITY,
                'caller': self,
            },
        )
        return used_idx == -1

    def active(self) -> Response:
        player = self.player
        discard = player.cardholders[Pile.DISCARD]
        deck = player.cardholders[Pile.DECK]
        stadiums = [c for c in discard if isinstance(c, AVGEStadiumCard)]

        missing = object()
        chosen_stadium = self.env.cache.get(self, IzzyChen._ACTIVE_STADIUM_CHOICE, missing, True)
        if chosen_stadium is missing:
            display_cards = list(discard)
            valid_targets = list(stadiums)
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                    InputEvent(
                        player,
                        [IzzyChen._ACTIVE_STADIUM_CHOICE],
                        lambda r: True,
                        ActionTypes.ACTIVATE_ABILITY,
                        self,
                        CardSelectionQuery(
                            'BAI Wrangler: You may put a Stadium card from your discard pile on top of your deck.',
                            valid_targets,
                            display_cards,
                            True,
                            False,
                        ),
                    )
                ]),
            )

        if chosen_stadium is None:
            return self.generic_response(self, ActionTypes.ACTIVATE_ABILITY)

        if not isinstance(chosen_stadium, AVGEStadiumCard) or chosen_stadium not in discard:
            return Response(ResponseType.CORE, Data())

        def generate_packet() -> PacketType:
            return [
                TransferCard(
                    chosen_stadium,
                    discard,
                    deck,
                    ActionTypes.ACTIVATE_ABILITY,
                    self,
                    None,
                    0,
                )
            ]

        self.propose(AVGEPacket([generate_packet], AVGEEngineID(self, ActionTypes.ACTIVATE_ABILITY, IzzyChen)))
        return self.generic_response(self, ActionTypes.ACTIVATE_ABILITY)

    def atk_1(self, card: AVGECharacterCard) -> Response:
        def generate_packet() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        50,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            packet.append(
                AVGECardHPChange(
                    card,
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, IzzyChen)))
        return self.generic_response(card, ActionTypes.ATK_1)