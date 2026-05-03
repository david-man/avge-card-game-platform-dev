from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, InputEvent


class FelixSynesthesiaModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, FelixChen), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.change_type == CardType.ALL:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_1]:
            return False
        if not isinstance(event.caller, AVGECharacterCard):
            return False
        if event.caller.player != self.owner_card.player.opponent:
            return False
        if event.target_card.player != self.owner_card.player:
            return False

        types = [c.card_type for c in self.owner_card.player.get_cards_in_play()]
        return len(types) == len(set(types))

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def modify(self, args=None):
        if args is None:
            args = {}
        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        event.modify_magnitude(-10)
        return Response(ResponseType.ACCEPT, Notify('Synesthesia: Damage from opponent attacks reduced by 10.', all_players, default_timeout))
    
    def __str__(self):
        return "Felix Chen: Synesthesia Debuff"


class FelixChen(AVGECharacterCard):
    _COIN_KEY_0 = 'felixchen_coin_0'
    _COIN_KEY_1 = 'felixchen_coin_1'

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.WOODWIND, 1, 3, 0)
        self.has_passive = True
        self.atk_1_name = 'Multiphonics'

    def passive(self) -> Response:
        self.add_listener(FelixSynesthesiaModifier(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        opponent = card.player.opponent
        roll0 = card.env.cache.get(card, FelixChen._COIN_KEY_0, None, True)
        roll1 = card.env.cache.get(card, FelixChen._COIN_KEY_1, None, True)
        if roll0 is None or roll1 is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [FelixChen._COIN_KEY_0, FelixChen._COIN_KEY_1],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CoinflipData('Multiphonics: Flip 2 coins.')
                        )
                    ]),
            )

        heads = int(roll0) + int(roll1)

        def generate_packet() -> PacketType:
            packet: PacketType = []
            if heads == 2:
                for target in opponent.cardholders[Pile.BENCH]:
                    if isinstance(target, AVGECharacterCard):
                        packet.append(
                            AVGECardHPChange(
                                target,
                                50,
                                AVGEAttributeModifier.SUBSTRACTIVE,
                                CardType.WOODWIND,
                                ActionTypes.ATK_1,
                                None,
                                card,
                            )
                        )
            elif heads == 0:
                active = opponent.get_active_card()
                if isinstance(active, AVGECharacterCard):
                    packet.append(
                        AVGECardHPChange(
                            active,
                            100,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.WOODWIND,
                            ActionTypes.ATK_1,
                            None,
                            card,
                        )
                    )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, FelixChen)))
        return self.generic_response(card, ActionTypes.ATK_1)
