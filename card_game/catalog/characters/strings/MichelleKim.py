from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange, PlayNonCharacterCard, TransferCard


class MichelleKim(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 2)
        self.atk_1_name = 'Open Strings'
        self.atk_2_name = 'VocaRock!!'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        def atk_active() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        packet: PacketType = [atk_active]

        deck = card.player.cardholders[Pile.DECK]
        hand = card.player.cardholders[Pile.HAND]
        discard = card.player.cardholders[Pile.DISCARD]

        def draw_and_maybe_use_item() -> PacketType:
            p: PacketType = []
            if len(deck) == 0:
                return p

            top = deck.peek()
            p.append(TransferCard(top, deck, hand, ActionTypes.ATK_1, card, None))
            if isinstance(top, AVGEItemCard):
                p.append(PlayNonCharacterCard(top, ActionTypes.ATK_1, card))
                p.append(TransferCard(top, hand, discard, ActionTypes.ATK_1, card, None))
            return p

        packet.append(draw_and_maybe_use_item)

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, MichelleKim)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        from card_game.catalog.items.MikuOtamatone import MikuOtamatone

        miku_used_this_turn = False
        chapter = card.env.round_id
        history_entries = card.env._engine.event_history.history.get(chapter, [])
        for event, _ in history_entries:
            if not isinstance(event, PlayNonCharacterCard):
                continue
            if isinstance(event.card, MikuOtamatone) and event.card.player == card.player:
                miku_used_this_turn = True
                break

        dmg = 80 if miku_used_this_turn else 30

        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            packet: PacketType = []
            if not isinstance(active, AVGECharacterCard):
                return packet
            packet.append(
                AVGECardHPChange(
                    active,
                    dmg,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_2,
                    None,
                    card,
                )
            )
            return packet

        card.propose(
            AVGEPacket([
                generate_packet
            ], AVGEEngineID(card, ActionTypes.ATK_2, MichelleKim))
        )

        return self.generic_response(card, ActionTypes.ATK_2)
