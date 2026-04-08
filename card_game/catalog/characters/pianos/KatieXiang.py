from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class KatieTurnEndReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, KatieXiang), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import TurnEnd

        return isinstance(event, TurnEnd) and event.env.player_turn == self.owner_card.player.opponent and self.owner_card.hp < 70

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "KatieXiang turn-end reactor"

    def react(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import AVGECardHPChange

        owner = self.owner_card

        def generate_packet() -> PacketType:
            packet: PacketType = []
            for player in owner.env.players.values():
                for c in player.get_cards_in_play():
                    if c != owner:
                        packet.append(
                            AVGECardHPChange(
                                c,
                                20,
                                AVGEAttributeModifier.ADDITIVE,
                                CardType.ALL,
                                ActionTypes.PASSIVE,
                                owner,
                            )
                        )
            return packet

        self.propose(AVGEPacket([generate_packet], AVGEEngineID(owner, ActionTypes.PASSIVE, KatieXiang)))
        return self.generate_response()


class KatieXiang(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PIANO, 1, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 3
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        card.add_listener(KatieTurnEndReactor(card))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
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
                    ActionTypes.ATK_1,
                    card,
                )
            ]

        card.propose(
            AVGEPacket([
                generate_packet
            ], AVGEEngineID(card, ActionTypes.ATK_1, KatieXiang))
        )

        return card.generate_response()
