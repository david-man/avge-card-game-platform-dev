from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class RileyHallStartTurnBenchGapDamageReactor(AVGEReactor):
    def __init__(self, owner_card: AVGEStadiumCard):
        super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_REACTORS)
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

    def react(self, args={}):
        from card_game.internal_events import AVGECardAttributeChange,  PhasePickCard

        event : PhasePickCard= self.attached_event
        target_player = event.player

        empty_bench_slots = max(0, max_bench_size - len(target_player.cardholders[Pile.BENCH]))
        if(empty_bench_slots == 0):
            return self.generate_response()

        damage_per_character = 10 * empty_bench_slots
        packet = []

        for character in target_player.get_cards_in_play():
            current_hp = int(character.attributes.get(AVGECardAttribute.HP, 0))
            if current_hp < damage_per_character:
                continue
            packet.append(
                AVGECardAttributeChange(
                    character,
                    AVGECardAttribute.HP,
                    damage_per_character,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    ActionTypes.NONCHAR,
                    self.owner_card,
                    None,
                )
            )

        if(len(packet) > 0):
            self.propose(packet)
        return self.generate_response()


class RileyHall(AVGEStadiumCard):
    def __init__(self, unique_id):
        super().__init__(unique_id)

    def play_card(self, parent_event: AVGEEvent) -> Response:
        self.add_listener(RileyHallStartTurnBenchGapDamageReactor(self))
        return self.generate_response()
