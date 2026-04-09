from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import *


class MichelleKim(AVGECharacterCard):
    _MIKU_PLAYED_ROUND_KEY = "michellekim_miku_played_round"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 2)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, PlayNonCharacterCard, TransferCard
        def atk() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_1,
                    card,
                )
            ]
        packet : PacketType = [atk]

        deck = card.player.cardholders[Pile.DECK]
        hand = card.player.cardholders[Pile.HAND]
        discard = card.player.cardholders[Pile.DISCARD]

        if len(deck) == 0:
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, MichelleKim)))
            return card.generate_response()

        top = deck.peek()
        if isinstance(top, AVGEItemCard):
            packet.append(TransferCard(top, deck, hand, ActionTypes.ATK_1, card))
            packet.append(PlayNonCharacterCard(top, ActionTypes.ATK_1, card))
            packet.append(TransferCard(top, hand, discard, ActionTypes.ATK_1, card))
        else:
            packet.append(TransferCard(top, deck, hand, ActionTypes.ATK_1, card))
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, MichelleKim)))
        return card.generate_response()

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        owner_card = card

        class _MikuPlayReactor(AVGEReactor):
            def __init__(self):
                super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.ATK_1, MichelleKim), group=EngineGroup.EXTERNAL_REACTORS)
                self.owner_card = owner_card

            def event_match(self, event):
                from card_game.internal_events import PlayNonCharacterCard
                from card_game.catalog.items.MikuOtomatone import MikuOtomatone

                if not isinstance(event, PlayNonCharacterCard):
                    return False
                return isinstance(event.card, MikuOtomatone) and event.card.player == owner_card.player

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                return
            
            def react(self, args=None):
                if args is None:
                    args = {}
                env = owner_card.env
                env.cache.set(owner_card, MichelleKim._MIKU_PLAYED_ROUND_KEY, env.round_id)
                return self.generate_response()

        owner_card.add_listener(_MikuPlayReactor())
        return owner_card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        last_miku_round = card.env.cache.get(card, MichelleKim._MIKU_PLAYED_ROUND_KEY, None, True)
        dmg = 80 if (last_miku_round == card.env.round_id) else 30

        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            if not isinstance(active, AVGECharacterCard):
                return []
            return [
                AVGECardHPChange(
                    active,
                    dmg,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_2,
                    card,
                )
            ]

        card.propose(
            AVGEPacket([
                generate_packet
            ], AVGEEngineID(card, ActionTypes.ATK_2, MichelleKim))
        )

        return card.generate_response()
