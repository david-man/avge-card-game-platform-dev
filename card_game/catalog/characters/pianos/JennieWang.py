from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.catalog.characters.pianos.DavidMan import DavidMan
from card_game.catalog.characters.pianos.LukeXu import LukeXu
from card_game.catalog.characters.woodwinds.EvelynWu import EvelynWu
from card_game.catalog.characters.percussion.BokaiBi import BokaiBi
from card_game.catalog.characters.guitars.RobertoGonzales import RobertoGonzales


class JennieWang(AVGECharacterCard):
    TARGET_CLASSES: tuple[type[AVGECharacterCard], ...] = (DavidMan, EvelynWu, BokaiBi, RobertoGonzales, LukeXu)

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PIANO, 1, 2, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        count = 0
        for c in card.player.get_cards_in_play():
            if isinstance(c, JennieWang.TARGET_CLASSES):
                count += 1

        if count <= 0:
            return card.generate_response(data={MESSAGE_KEY: "No other SE members in play!"})

        per_target = min(20 * count, 40)

        def generate_packet() -> PacketType:
            packet: PacketType = []
            opp = card.player.opponent
            active = opp.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        per_target,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PIANO,
                        ActionTypes.ATK_1,
                        card,
                    )
                )
            return packet
        def generate_packet_bench() -> PacketType:
            packet : PacketType = []
            opp = card.player.opponent
            for bc in opp.cardholders[Pile.BENCH]:
                assert isinstance(bc, AVGECharacterCard)
                packet.append(
                    AVGECardHPChange(
                        bc,
                        per_target,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PIANO,
                        ActionTypes.ATK_1,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, JennieWang)))
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        from card_game.catalog.stadiums.AlumnaeHall import AlumnaeHall
        from card_game.catalog.stadiums.FriedmanHall import FriedmanHall
        from card_game.catalog.stadiums.RileyHall import RileyHall
        from card_game.catalog.stadiums.MainHall import MainHall

        dmg = 60
        if len(card.env.stadium_cardholder) > 0:
            stadium = card.env.stadium_cardholder.peek()
            if isinstance(stadium, (AlumnaeHall, FriedmanHall, RileyHall, MainHall)):
                dmg = 80

        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            return [
                AVGECardHPChange(
                    active,
                    dmg,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_2,
                    card,
                )
            ]

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, JennieWang)))

        return card.generate_response()
