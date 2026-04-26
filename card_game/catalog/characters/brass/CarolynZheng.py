from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import *
from card_game.constants import ActionTypes

class _CarolynAttackModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, CarolynZheng), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if event.caller != self.owner_card:
            return False
        if event.target_card.player != self.owner_card.player.opponent:
            return False
        if event.magnitude == 0:
            return False
        if self.owner_card.env is None:
            return False

        previous_round = self.owner_card.player.get_last_turn()
        # On opening turn there is no previous turn, so this condition should apply.
        if previous_round < 0:
            return True
        _, atk1_idx = self.owner_card.env.check_history(
            previous_round,
            PlayCharacterCard,
            {
                "caller": self.owner_card,
                "card_action": ActionTypes.ATK_1
            },
        )
        _, atk2_idx = self.owner_card.env.check_history(
            previous_round,
            PlayCharacterCard,
            {
                "caller": self.owner_card,
                "card_action": ActionTypes.ATK_2
            },
        )
        attacked = (atk1_idx != -1) or (atk2_idx != -1)
        return not attacked

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def on_packet_completion(self):
        return
    
    def modify(self, args=None):
        assert(isinstance(self.attached_event, AVGECardHPChange))
        event : AVGECardHPChange = self.attached_event
        # If this character did not attack during the previous turn, deal +30 damage.
        event.modify_magnitude(30)
        return Response(ResponseType.ACCEPT, Notify("Carolyn Zheng buffed her own attack by 30 damage!", all_players, default_timeout))


class CarolynZheng(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.BRASS, 1, 0)
        self.atk_1_name = 'Blast'
        self.has_passive = True

    def passive(self) -> Response:
        # Static damage modifier checks previous turn history at runtime.
        self.add_listener(_CarolynAttackModifier(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        def generate_packet() -> PacketType:
            return [AVGECardHPChange(
                card.player.opponent.get_active_card(),
                70,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.BRASS,
                ActionTypes.ATK_1,
                None,
                card,
            )]
        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, CarolynZheng)))
        return self.generic_response(card, ActionTypes.ATK_1)

