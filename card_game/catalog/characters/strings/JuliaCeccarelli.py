from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import InputEvent, PlayNonCharacterCard, EmptyEvent, AVGECardHPChange

class _JuliaAtk2KnockoutReactor(AVGEReactor):
    _PENDING_HITS_KEY = 'julia_ricochet_pending_hits'

    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.ATK_2, JuliaCeccarelli), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card
        # Start armed for the initial 50-damage hit from Ricochet.
        self.owner_card.env.cache.set(self.owner_card, _JuliaAtk2KnockoutReactor._PENDING_HITS_KEY, 1)

    def _get_pending_hits(self) -> int:
        pending = self.owner_card.env.cache.get(self.owner_card, _JuliaAtk2KnockoutReactor._PENDING_HITS_KEY, 0)
        if isinstance(pending, int):
            return pending
        return 0

    def _set_pending_hits(self, value: int):
        self.owner_card.env.cache.set(self.owner_card, _JuliaAtk2KnockoutReactor._PENDING_HITS_KEY, value)

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.caller != self.owner_card:
            return False
        if event.catalyst_action != ActionTypes.ATK_2:
            return False
        if not isinstance(event.target_card, AVGECharacterCard):
            return False
        if event.target_card.player != self.owner_card.player.opponent:
            return False
        return self._get_pending_hits() > 0

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self._get_pending_hits() <= 0:
            self.owner_card.env.cache.delete(self.owner_card, _JuliaAtk2KnockoutReactor._PENDING_HITS_KEY)
            self.invalidate()

    def react(self, args=None):
        if args is None:
            args = {}
        assert isinstance(self.attached_event, AVGECardHPChange)
        assert isinstance(self.attached_event.final_change, int)
        owner = self.owner_card
        self._set_pending_hits(self._get_pending_hits() - 1)

        if self.attached_event.final_change == 0:
            knocked_out = self.attached_event.target_card

            def splash_remaining() -> PacketType:
                packet: PacketType = []
                targets = [
                    target
                    for target in owner.player.opponent.cardholders[Pile.BENCH]
                    if isinstance(target, AVGECharacterCard) and target.hp > 0 and target != knocked_out
                ]
                for target in targets:
                    packet.append(
                        AVGECardHPChange(
                            target,
                            30,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.STRING,
                            ActionTypes.ATK_2,
                            None,
                            owner,
                        )
                    )
                self._set_pending_hits(self._get_pending_hits() + len(packet))
                return packet

            self.propose(AVGEPacket([splash_remaining], AVGEEngineID(owner, ActionTypes.ATK_2, JuliaCeccarelli)))
            return Response(ResponseType.ACCEPT, Notify('Ricochet: Knockout confirmed, 30 damage to each remaining opposing character on the bench.', all_players, default_timeout))

        return Response(ResponseType.ACCEPT, Data())
    def __str__(self):
        return "Julia Ceccarelli: Ricochet"

class JuliaCeccarelli(AVGECharacterCard):
    _ATK1_ITEM_KEY = "julia_atk1_item"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 3)
        self.atk_1_name = 'Photograph'
        self.atk_2_name = 'Ricochet'

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        opp_hand = card.player.opponent.cardholders[Pile.HAND]
        items = [c for c in opp_hand if isinstance(c, AVGEItemCard)]

        missing = object()
        chosen = card.env.cache.get(card, JuliaCeccarelli._ATK1_ITEM_KEY, missing, True)
        if chosen is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        EmptyEvent(
                            ActionTypes.ATK_1,
                            card,
                            ResponseType.CORE,
                            RevealCards(
                                'Photograph: Opponent hand',
                                [card.player.unique_id],
                                default_timeout,
                                list(opp_hand),
                            ),
                        ),
                        InputEvent(
                            card.player,
                            [JuliaCeccarelli._ATK1_ITEM_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                'Photograph: Choose an item to copy as this attack (or None).',
                                items,
                                list(opp_hand),
                                True,
                                False,
                            )
                        )
                    ]),
            )

        if chosen is not None and isinstance(chosen, AVGEItemCard) and chosen in opp_hand:
            card.propose(AVGEPacket([PlayNonCharacterCard(chosen, ActionTypes.ATK_1, card)], AVGEEngineID(card, ActionTypes.ATK_1, JuliaCeccarelli)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        card.add_listener(_JuliaAtk2KnockoutReactor(card))

        def atk() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        50,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([atk], AVGEEngineID(card, ActionTypes.ATK_2, JuliaCeccarelli)))
        return self.generic_response(card, ActionTypes.ATK_2)
