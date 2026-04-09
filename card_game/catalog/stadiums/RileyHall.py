from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class RileyHallStartTurnBenchGapDamageReactor(AVGEReactor):
    def __init__(self, owner_card: AVGEStadiumCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, RileyHall), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import PhasePickCard
        return self.owner_card._is_active_stadium() and isinstance(event, PhasePickCard)

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if(not self.owner_card._is_active_stadium()):
            self.invalidate()

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "RileyHall Reactor"

    def react(self, args=None):
        from card_game.internal_events import AVGECardHPChange,  PhasePickCard

        event = self.attached_event
        assert isinstance(event, PhasePickCard)
        target_player = event.player

        empty_bench_slots = max(0, max_bench_size - len(target_player.cardholders[Pile.BENCH]))
        if(empty_bench_slots == 0):
            return self.generate_response()

        damage_per_character = 10 * empty_bench_slots
        packet = []

        for character in target_player.get_cards_in_play():
            current_hp = character.hp
            if current_hp < damage_per_character:
                continue
            packet.append(
                AVGECardHPChange(
                    character,
                    damage_per_character,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.ALL,
                    ActionTypes.NONCHAR,
                    self.owner_card,
                )
            )

        if(len(packet) > 0):
            self.propose(AVGEPacket(packet, AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, RileyHall)), 1)
        return self.generate_response()


class RileyHall(AVGEStadiumCard):
    def __init__(self, unique_id):
        super().__init__(unique_id)

    def play_card(self) -> Response:
        self.add_listener(RileyHallStartTurnBenchGapDamageReactor(self))
        return self.generate_response()
