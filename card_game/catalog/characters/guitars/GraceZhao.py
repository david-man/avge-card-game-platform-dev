from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.catalog.tools import AVGEShowcaseSticker, AVGETShirt


class _GraceTurnEndReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, GraceZhao), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import TurnEnd

        if not isinstance(event, TurnEnd):
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type not in [Pile.ACTIVE, Pile.BENCH]:
            return False
        if self.owner_card.player is None or self.owner_card.player.opponent is None:
            return False
        if event.env.player_turn == self.owner_card.player.opponent:
            return False

        opponent = self.owner_card.player.opponent
        for c in opponent.get_cards_in_play():
            for t in c.tools_attached:
                if isinstance(t, (AVGEShowcaseSticker, AVGETShirt)):
                    return True
        return False

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def react(self):
        from card_game.internal_events import InputEvent, AVGECardHPChange

        opponent = self.owner_card.player.opponent
        candidates = []
        for c in opponent.get_cards_in_play():
            for t in c.tools_attached:
                if isinstance(t, (AVGEShowcaseSticker, AVGETShirt)):
                    candidates.append(c)
                    break
        missing = object()
        selected_card = self.owner_card.env.cache.get(self.owner_card, GraceZhao._TARGET_KEY, missing, True)
        if selected_card is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            self.owner_card.player,
                            [GraceZhao._TARGET_KEY],
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            self.owner_card,
                            CardSelectionQuery("Royalties: Deal 10 damage to an opposing card", candidates, opponent.get_cards_in_play(), False, False)
                        )
                    ]),
            )
        if isinstance(selected_card, AVGECharacterCard):
            def gen() -> PacketType:
                packet: PacketType = []
                packet.append(
                    AVGECardHPChange(
                        selected_card,
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.GUITAR,
                        ActionTypes.PASSIVE,
                        None,
                        self.owner_card,
                    )
                )
                return packet
            self.propose(
                AVGEPacket([gen], AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, GraceZhao)),
                1
            )
        return Response(ResponseType.ACCEPT, Data())


class GraceZhao(AVGECharacterCard):
    _TARGET_KEY = "grace-target-key-atk1"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.GUITAR, 2, 2)
        self.atk_1_name = 'Feedback Loop'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(_GraceTurnEndReactor(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        def gen_1() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        def gen_2() -> PacketType:
            packet : PacketType = []
            for c in card.player.cardholders[Pile.BENCH]:
                if isinstance(c, AVGECharacterCard) and c.card_type == CardType.GUITAR:
                    packet.append(
                        AVGECardHPChange(
                            c,
                            10,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.GUITAR,
                            ActionTypes.ATK_1,
                            None,
                            card,
                        )
                    )
            return packet
        card.propose(AVGEPacket([gen_1, gen_2], AVGEEngineID(card, ActionTypes.ATK_1, GraceZhao)))
        return self.generic_response(card, ActionTypes.ATK_1)
