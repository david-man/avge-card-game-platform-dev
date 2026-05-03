from __future__ import annotations

import random

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class _PascalDelayedReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard, trigger_round: int):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, PascalKim), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card
        self.trigger_round = trigger_round

    def event_match(self, event):
        from card_game.internal_events import TurnEnd

        return isinstance(event, TurnEnd) and self.owner_card.env.round_id == self.trigger_round

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self.owner_card.env.round_id > self.trigger_round:
            self.invalidate()

    def react(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import AVGECardHPChange

        def gen() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    self.owner_card.player.opponent.get_active_card(),
                    70,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.PASSIVE,
                    Notify("Ominous Chimes: 70 damage", all_players, default_timeout),
                    self.owner_card,
                )
            )
            return packet

        self.owner_card.propose(
            AVGEPacket([gen], AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, PascalKim)), 1
        )
        self.invalidate()
        return Response(ResponseType.ACCEPT, Data())
    
    def __str__(self):
        return "Pascal Kim: Ominous Chimes"


class PascalKim(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PERCUSSION, 2, 2, 3)
        self.atk_1_name = 'Ragebaited'
        self.atk_2_name = 'Ominous Chimes'

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        from card_game.internal_events import AVGECardHPChange

        hp = card.hp
        if hp <= 20:
            dmg = 90
        elif hp <= 50:
            dmg = 50
        else:
            dmg = 20

        def gen() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    dmg,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, PascalKim))
        )

        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        from card_game.internal_events import TransferCard, ReorderCardholder

        deck = card.player.cardholders[Pile.DECK]
        packet : PacketType = []

        for tool in list(card.tools_attached):
            packet.append(TransferCard(tool, card.tools_attached, deck, ActionTypes.ATK_2, card, None))

        src = card.cardholder
        assert src is not None
        packet.append(TransferCard(card, src, deck, ActionTypes.ATK_2, card, None))

        def gen() -> PacketType:
            p: PacketType = []
            p.append(
                ReorderCardholder(
                    deck,
                    random.sample(deck.get_order(), len(deck)),
                    ActionTypes.ATK_2,
                    card,
                    None,
                )
            )
            return p

        packet.append(gen)

        trigger_round = card.player.opponent.get_next_turn()
        card.env.add_listener(_PascalDelayedReactor(card, trigger_round))

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, PascalKim)))
        return self.generic_response(card, ActionTypes.ATK_2)
