from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import InputEvent, AVGECardHPChange
class _VincentHealReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=(owner_card, AVGEEventListenerType.ATK_2), group=EngineGroup.EXTERNAL_REACTORS)
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
        self.attached_event : AVGECardHPChange
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
                AVGECardHPChange(
                    chosen,
                    heal_amt,
                    AVGEAttributeModifier.ADDITIVE,
                    ActionTypes.ATK_2,
                    CardType.ALL,
                    self.owner_card,
                )
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
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        card.propose(
            AVGECardHPChange(
                lambda : card.player.opponent.get_active_card(),
                20,
                AVGEAttributeModifier.SUBSTRACTIVE,
                ActionTypes.ATK_1,
                CardType.ALL,
                card,
            )
        )

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange
        # attach reactor to heal one benched character for the same amount dealt
        card.add_listener(_VincentHealReactor(card))

        card.propose(AVGECardHPChange(
                lambda : card.player.opponent.get_active_card(),
                40,
                AVGEAttributeModifier.SUBSTRACTIVE,
                ActionTypes.ATK_2,
                CardType.BRASS,
                card,
            ))
        return card.generate_response()
