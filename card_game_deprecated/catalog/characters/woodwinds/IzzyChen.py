from __future__ import annotations

from random import randint

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange, InputEvent, PlayCharacterCard, TransferCard


class IzzyChen(AVGECharacterCard):
    _COIN_KEY = 'izzy_coin'
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

        # Keep the flip result available through the follow-up stadium query.
        # If consumed here, a heads path re-enters active() and asks for coin again.
        flip = self.env.cache.get(self, IzzyChen._COIN_KEY, None)
        if flip is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                    InputEvent(
                        player,
                        [IzzyChen._COIN_KEY],
                        lambda r: True,
                        ActionTypes.ACTIVATE_ABILITY,
                        self,
                        CoinflipData('BAI Wrangler: Flip a coin.'),
                    )
                ]),
            )

        if int(flip) != 1:
            self.env.cache.delete(self, IzzyChen._COIN_KEY)
            self.env.cache.delete(self, IzzyChen._ACTIVE_STADIUM_CHOICE)
            return Response(ResponseType.CORE, Notify('Izzy Chen used BAI Wrangler, but she did not roll heads...', all_players, default_timeout))

        missing = object()
        chosen_stadium = self.env.cache.get(self, IzzyChen._ACTIVE_STADIUM_CHOICE, missing, True)
        if chosen_stadium is missing:
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
                            'BAI Wrangler: Choose a stadium in your discard to shuffle into your deck.',
                            stadiums,
                            stadiums,
                            True,
                            False,
                        ),
                    )
                ]),
            )

        if not isinstance(chosen_stadium, AVGEStadiumCard):
            self.env.cache.delete(self, IzzyChen._COIN_KEY)
            return self.generic_response(self, ActionTypes.ACTIVATE_ABILITY)

        if chosen_stadium not in discard:
            self.env.cache.delete(self, IzzyChen._COIN_KEY)
            return Response(ResponseType.CORE, Notify('Izzy Chen used BAI Wrangler, but the selected stadium was not in discard.', all_players, default_timeout))

        def generate_packet() -> PacketType:
            return [
                TransferCard(
                    chosen_stadium,
                    discard,
                    deck,
                    ActionTypes.ACTIVATE_ABILITY,
                    self,
                    None,
                    randint(0, len(deck)),
                )
            ]

        self.propose(AVGEPacket([generate_packet], AVGEEngineID(self, ActionTypes.ACTIVATE_ABILITY, IzzyChen)))
        self.env.cache.delete(self, IzzyChen._COIN_KEY)
        self.env.cache.delete(self, IzzyChen._ACTIVE_STADIUM_CHOICE)
        return self.generic_response(self, ActionTypes.ACTIVATE_ABILITY)

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
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