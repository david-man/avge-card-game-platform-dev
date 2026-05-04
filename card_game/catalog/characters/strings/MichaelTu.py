from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import TransferCard, AVGECardHPChange, ReorderCardholder, EmptyEvent


class MichaelTu(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 2, 3)
        self.atk_1_name = 'Synchro Summon'
        self.atk_2_name = 'Electric Cello'

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        player = card.player
        deck = player.cardholders[Pile.DECK]
        hand = player.cardholders[Pile.HAND]

        revealed: list[AVGECard] = []
        first_char: AVGECharacterCard | None = None
        for c in deck:
            revealed.append(c)
            if isinstance(c, AVGECharacterCard):
                first_char = c
                break

        packet: PacketType = []
        packet.append(
            EmptyEvent(
                ActionTypes.ATK_1,
                card,
                ResponseType.CORE,
                RevealCards('Synchro Summon: Revealed cards', all_players, default_timeout, revealed),
            )
        )

        if first_char is not None and first_char.card_type != CardType.STRING:
            packet.append(
                TransferCard(
                    first_char,
                    deck,
                    hand,
                    ActionTypes.ATK_1,
                    card,
                    None,
                )
            )
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    30,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )

        def shuffle_deck() -> PacketType:
            p: PacketType = []
            if len(deck) > 1:
                p.append(
                    ReorderCardholder(
                        deck,
                        random.sample(deck.get_order(), len(deck)),
                        ActionTypes.ATK_1,
                        card,
                        None,
                    )
                )
            return p

        packet.append(shuffle_deck)

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, MichaelTu)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        from card_game.catalog.stadiums.AlumnaeHall import AlumnaeHall
        from card_game.catalog.stadiums.SalomonDECI import SalomonDECI
        from card_game.catalog.stadiums.RileyHall import RileyHall
        from card_game.catalog.stadiums.MainHall import MainHall

        dmg = 60
        if len(card.env.stadium_cardholder) > 0:
            stadium = card.env.stadium_cardholder.peek()
            if isinstance(stadium, (AlumnaeHall, SalomonDECI, RileyHall, MainHall)):
                dmg = 80

        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            packet: PacketType = []
            if isinstance(active, AVGECharacterCard):
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

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, MichaelTu)))
        return self.generic_response(card, ActionTypes.ATK_2)
