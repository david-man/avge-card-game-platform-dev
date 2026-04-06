from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import InputEvent, AVGECardHPChange, AVGECardHPChangeCreator
class _VincentHealReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.ATK_2, VincentChen), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        # only react to HP damage caused by this owner's ATK_2
        if event.catalyst_action != ActionTypes.ATK_2:
            return False
        if(not isinstance(event.caller_card, AVGECharacterCard)):
            return False
        if event.caller_card != self.owner_card:
            return False
        return True

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "VincentChen Heal Reactor"

    def react(self, args=None) -> Response:
        assert(isinstance(self.attached_event, AVGECardHPChange))
        heal_amt = self.attached_event.magnitude

        # collect benched friendly characters
        bench_chars = self.owner_card.player.cardholders[Pile.BENCH]
        if len(bench_chars) == 0:
            return self.generate_response()
        # ask player to choose
        chosen = self.owner_card.env.cache.get(self.owner_card, VincentChen._HEAL_PICK_KEY, None, True)
        if chosen is None:
            # interrupt to choose
            return self.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            self.owner_card.player,
                            [VincentChen._HEAL_PICK_KEY],
                            InputType.SELECTION,
                            lambda r : True,
                            ActionTypes.ATK_2,
                            self.owner_card,
                            {"query_label": "vincent_heal_pick", 
                             "targets": bench_chars},
                        )
                    ]
                },
            )
        self.propose(
                AVGEPacket([AVGECardHPChange(
                    chosen,
                    heal_amt,
                    AVGEAttributeModifier.ADDITIVE,
                    CardType.ALL,
                    ActionTypes.ATK_2,
                    self.owner_card,
                )], AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, VincentChen))
            )
        self.invalidate()
        return self.generate_response()


class VincentChen(AVGECharacterCard):
    _HEAL_PICK_KEY = "vincent_chen_heal_pick"
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.BRASS, 1, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        card.propose(
            AVGEPacket([AVGECardHPChangeCreator(
                lambda : card.player.opponent.get_active_card(),
                20,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.ALL,
                ActionTypes.ATK_1,
                card,
            )], AVGEEngineID(card, ActionTypes.ATK_1, VincentChen))
        )

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        # attach reactor to heal one benched character for the same amount dealt
        card.add_listener(_VincentHealReactor(card))

        card.propose(
            AVGEPacket([AVGECardHPChangeCreator(
                lambda : card.player.opponent.get_active_card(),
                40,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.BRASS,
                ActionTypes.ATK_2,
                card,
            )], AVGEEngineID(card, ActionTypes.ATK_2, VincentChen))
        )
        return card.generate_response()
