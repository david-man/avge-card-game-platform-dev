from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import AVGEReactor
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

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "PascalKim delayed end-of-opponent-turn damage"

    def react(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import AVGECardHPChangeCreator

        self.owner_card.propose(
            AVGEPacket([
                AVGECardHPChangeCreator(
                    lambda: self.owner_card.player.opponent.get_active_card(),
                    70,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.PASSIVE,
                    self.owner_card,
                )
            ], AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, PascalKim))
        )
        self.invalidate()
        return self.generate_response()


class PascalKim(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PERCUSSION, 2, 2, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChangeCreator

        hp = card.hp
        if hp <= 20:
            dmg = 100
        elif hp <= 50:
            dmg = 50
        else:
            dmg = 20

        card.propose(
            AVGEPacket([
                AVGECardHPChangeCreator(
                    lambda: card.player.opponent.get_active_card(),
                    dmg,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.ATK_1,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_1, PascalKim))
        )

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import TransferCard, ReorderCardholderCreator

        deck = card.player.cardholders[Pile.DECK]
        packet = []

        src = card.cardholder
        packet.append(TransferCard(card, src, deck, ActionTypes.ATK_2, card, None))
        packet.append(
            ReorderCardholderCreator(
                deck,
                lambda: random.sample(deck.get_order(), len(deck)),
                ActionTypes.ATK_2,
                card,
            )
        )

        trigger_round = card.player.opponent.get_next_turn()
        card.add_listener(_PascalDelayedReactor(card, trigger_round))

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, PascalKim)))
        return card.generate_response()
