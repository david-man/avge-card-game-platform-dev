from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange
from card_game.catalog.characters.pianos.DavidMan import DavidMan
from card_game.catalog.characters.pianos.LukeXu import LukeXu
from card_game.catalog.characters.woodwinds.EvelynWu import EvelynWu
from card_game.catalog.characters.percussion.BokaiBi import BokaiBi
from card_game.catalog.characters.guitars.RobertoGonzales import RobertoGonzales


class JennieWang(AVGECharacterCard):
    TARGET_CLASSES: tuple[type[AVGECharacterCard], ...] = (DavidMan, EvelynWu, BokaiBi, RobertoGonzales, LukeXu)

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 2, 2, 3)
        self.atk_1_name = 'Small Ensemble Committee'
        self.atk_2_name = 'Grand Piano'

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        count = 0
        for c in card.player.get_cards_in_play():
            if isinstance(c, JennieWang.TARGET_CLASSES):
                count += 1
        for c in card.player.opponent.get_cards_in_play():
            if isinstance(c, JennieWang.TARGET_CLASSES):
                count += 1

        per_target = min(10 * count, 30)
        if per_target <= 0:
            return self.generic_response(card, ActionTypes.ATK_1)

        def generate_packet() -> PacketType:
            packet: PacketType = []
            opp = card.player.opponent
            for c in opp.get_cards_in_play():
                if isinstance(c, AVGECharacterCard):
                    packet.append(
                        AVGECardHPChange(
                            c,
                            per_target,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.PIANO,
                            ActionTypes.ATK_1,
                            None,
                            card,
                        )
                    )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, JennieWang)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
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
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    active,
                    dmg,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_2,
                    None,
                    card,
                )
            )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, JennieWang)))

        return self.generic_response(card, ActionTypes.ATK_2)
