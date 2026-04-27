from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import TransferCard, InputEvent, AVGECardHPChange, PlayCharacterCard

class EmilyWang(AVGECharacterCard):
    _COIN_KEY_0 = "emilywang_coin_0"
    _COIN_KEY_1 = "emilywang_coin_1"
    _COIN_KEY_2 = "emilywang_coin_2"
    _TOOL_DISCARD_KEY = "emilywang_tool_discard"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 3)
        self.atk_1_name = 'Triple Stop'
        self.active_name = 'Profit Margins'

    def can_play_active(self) -> bool:
        if self.env is None or self.player is None:
            return False
        if self.env.player_turn != self.player:
            return False
        if len(self.tools_attached) == 0:
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
        return already_used_idx == -1

    def active(self) -> Response:
        tool = self.env.cache.get(self, EmilyWang._TOOL_DISCARD_KEY, None, True)
        available_tools = list(self.tools_attached)
        if tool is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            self.player,
                            [EmilyWang._TOOL_DISCARD_KEY],
                            lambda r: True,
                            ActionTypes.ACTIVATE_ABILITY,
                            self,
                            CardSelectionQuery(
                                'Profit Margins: Choose a tool attached to this character to discard.',
                                available_tools,
                                available_tools,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        if not isinstance(tool, AVGECard) or tool not in self.tools_attached:
            return Response(ResponseType.CORE, Data())

        discard = self.player.cardholders[Pile.DISCARD]
        packet: PacketType = []
        packet.append(
            TransferCard(
                tool,
                tool.cardholder,
                discard,
                ActionTypes.ACTIVATE_ABILITY,
                self,
                None,
            )
        )

        deck = self.player.cardholders[Pile.DECK]
        hand = self.player.cardholders[Pile.HAND]
        def draw_top() -> PacketType:
            ret: PacketType = []
            if len(deck) > 0:
                ret.append(
                    TransferCard(
                        deck.peek(),
                        deck,
                        hand,
                        ActionTypes.ACTIVATE_ABILITY,
                        self,
                        None,
                    )
                )
            return ret

        packet.append(draw_top)

        self.propose(AVGEPacket(packet, AVGEEngineID(self, ActionTypes.ACTIVATE_ABILITY, EmilyWang)))
        return self.generic_response(self, ActionTypes.ACTIVATE_ABILITY)

    def atk_1(self, card: AVGECharacterCard) -> Response:
        r0 = card.env.cache.get(card, EmilyWang._COIN_KEY_0, None, True)
        r1 = card.env.cache.get(card, EmilyWang._COIN_KEY_1, None, True)
        r2 = card.env.cache.get(card, EmilyWang._COIN_KEY_2, None, True)
        if r0 is None or r1 is None or r2 is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [EmilyWang._COIN_KEY_0, EmilyWang._COIN_KEY_1, EmilyWang._COIN_KEY_2],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CoinflipData('Triple Stop: Flip 3 coins.')
                        )
                    ]),
            )

        heads = int(r0) + int(r1) + int(r2)
        packet: PacketType = []
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

            packet.append(generate_packet)

        if len(packet) > 0:
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, EmilyWang)))

        return self.generic_response(card, ActionTypes.ATK_1)
