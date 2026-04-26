from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange



class _JuanBenchAttackBoost(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, JuanBurgos), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if not isinstance(event.caller, AVGECharacterCard):
            return False
        if event.caller != self.owner_card.player.get_active_card():
            return False
        if self.owner_card.cardholder.pile_type != Pile.BENCH:
            return False
        if event.caller.card_type != CardType.BRASS:
            return False
        return True

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def modify(self, args=None):
        assert isinstance(self.attached_event, AVGECardHPChange)
        event : AVGECardHPChange = self.attached_event
        # add +20 damage to the attack
        event.modify_magnitude(20)
        return Response(ResponseType.ACCEPT, Notify("Baking Buff! +20 damage", all_players, default_timeout))


class JuanBurgos(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.BRASS, 1, 3)
        self.atk_1_name = 'Concert Pitch'
        self.has_passive = True
    def passive(self) -> Response:
        # attach bench boost modifier globally while in play
        self.add_listener(_JuanBenchAttackBoost(self))
        return Response(ResponseType.ACCEPT, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        opponent = card.player.opponent
        def generate_packet() -> PacketType:
        # count brass characters on your bench
            bench = card.player.cardholders[ Pile.BENCH ]
            brass_count = 0
            for c in bench:
                assert isinstance(c, AVGECharacterCard)
                if c.card_type == CardType.BRASS:
                    brass_count += 1

            extra = 20 * brass_count
            damage = 40 + extra

            return [AVGECardHPChange(
                    opponent.get_active_card(),
                    damage,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )]
        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, JuanBurgos)))
        return self.generic_response(card, ActionTypes.ATK_1)
