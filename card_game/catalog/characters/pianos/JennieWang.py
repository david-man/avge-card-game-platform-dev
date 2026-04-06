from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *
from card_game.catalog.characters.pianos import DavidMan, LukeXu
from card_game.catalog.characters.woodwinds import EvelynWu
from card_game.catalog.characters.percussion import BokaiBi
from card_game.catalog.characters.guitars import RobertoGonzales


class JennieWang(AVGECharacterCard):
    TARGET_CLASSES: tuple = (DavidMan, EvelynWu, BokaiBi, RobertoGonzales, LukeXu)

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PIANO, 1, 2, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        count = 0
        for c in card.player.get_cards_in_play():
            if isinstance(c, JennieWang.TARGET_CLASSES) or isinstance(c, JennieWang):
                count += 1

        if count <= 0:
            return card.generate_response()

        per_target = min(20 * count, 40)

        def generate_packet():
            packets = []
            opp = card.player.opponent
            packets.append(
                AVGECardHPChange(
                    opp.get_active_card(),
                    per_target,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_1,
                    card,
                )
            )
            for bc in opp.cardholders[Pile.BENCH]:
                assert isinstance(bc, AVGECharacterCard)
                packets.append(
                    AVGECardHPChange(
                        bc,
                        per_target,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PIANO,
                        ActionTypes.ATK_1,
                        card,
                    )
                )
            return AVGEPacket(packets, AVGEEngineID(card, ActionTypes.ATK_1, JennieWang))

        card.propose(generate_packet())
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChangeCreator
        from card_game.catalog.stadiums.AlumnaeHall import AlumnaeHall
        from card_game.catalog.stadiums.FriedmanHall import FriedmanHall
        from card_game.catalog.stadiums.RileyHall import RileyHall
        from card_game.catalog.stadiums.MainHall import MainHall

        dmg = 60
        if len(card.env.stadium_cardholder) > 0:
            stadium = card.env.stadium_cardholder.peek()
            if isinstance(stadium, (AlumnaeHall, FriedmanHall, RileyHall, MainHall)):
                dmg = 80

        card.propose(
            AVGEPacket([
                AVGECardHPChangeCreator(
                    lambda: card.player.opponent.get_active_card(),
                    dmg,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_2,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_2, JennieWang))
        )

        return card.generate_response()
