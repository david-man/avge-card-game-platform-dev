from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class CavinMaidBoostModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, CavinXue), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        
        if event.caller != self.owner_card:
            return False

        env = self.owner_card.env
        maid_count = 0
        for player in env.players.values():
            for c in player.get_cards_in_play():
                if len(c.statuses_attached[StatusEffect.MAID]) > 0:
                    maid_count += 1

        return maid_count > 0

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self.owner_card.env is None or self.owner_card.cardholder is None:
            self.invalidate()
            return
        if self.owner_card.cardholder.pile_type not in [Pile.ACTIVE, Pile.BENCH]:
            self.invalidate()

    def modify(self):
        from card_game.internal_events import AVGECardHPChange

        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)

        env = self.owner_card.env
        maid_count = 0
        for player in env.players.values():
            for c in player.get_cards_in_play():
                if len(c.statuses_attached[StatusEffect.MAID]) > 0:
                    maid_count += 1

        event.modify_magnitude(20 * maid_count)
        return Response(
            ResponseType.ACCEPT,
            Notify(
                f"{str(self.owner_card)} gained +{20 * maid_count} damage from \"Wait no... I'm not into femboys-\".",
                all_players,
                default_timeout,
            ),
        )


class CavinXue(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.PERCUSSION, 1, 1)
        self.atk_1_name = 'Cymbal Crash'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(CavinMaidBoostModifier(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        def generate() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet
        card.propose(
            AVGEPacket([generate], AVGEEngineID(card, ActionTypes.ATK_1, CavinXue))
        )

        return self.generic_response(card, ActionTypes.ATK_1)
