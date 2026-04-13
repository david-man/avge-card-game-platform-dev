from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class _JuliaAtk2KnockoutReactor(AVGEReactor):
    _ACTIVE = "juliaatk2bouncing"
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.ATK_2, JuliaCiacerelli), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card
        self.owner_card.env.cache.set(self.owner_card, _JuliaAtk2KnockoutReactor._ACTIVE, 1)

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.caller_card != self.owner_card:
            return False
        if event.catalyst_action != ActionTypes.ATK_2:
            return False
        
        return isinstance(event.target_card, AVGECharacterCard)

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if(self.owner_card.env.cache.get(self.owner_card, _JuliaAtk2KnockoutReactor._ACTIVE, 1) == 0):
            self.invalidate()

    def react(self, args=None):
        from card_game.internal_events import AVGECardHPChange

        assert isinstance(self.attached_event, AVGECardHPChange)
        assert isinstance(self.attached_event.final_change, int)
        owner = self.owner_card
        
        if(self.attached_event.final_change == 0):
            def splash_remaining() -> PacketType:
                s = cast(int, self.owner_card.env.cache.get(self.owner_card, _JuliaAtk2KnockoutReactor._ACTIVE, 1))
                self.owner_card.env.cache.set(self.owner_card, _JuliaAtk2KnockoutReactor._ACTIVE, s - 1)
                targets = [
                    target
                    for target in owner.player.opponent.get_cards_in_play()
                    if isinstance(target, AVGECharacterCard) and target.hp > 0
                ]
                splashes_left = self.owner_card.env.cache.get(self.owner_card, _JuliaAtk2KnockoutReactor._ACTIVE, 1)
                assert isinstance(splashes_left, int)
                self.owner_card.env.cache.set(self.owner_card, _JuliaAtk2KnockoutReactor._ACTIVE, splashes_left + len(targets))
                return [
                    AVGECardHPChange(
                        target,
                        30,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_2,
                        owner,
                    )
                    for target in targets
                ]

            self.propose(AVGEPacket([splash_remaining], AVGEEngineID(owner, ActionTypes.ATK_2, JuliaCiacerelli)))
        else:
            s = cast(int, self.owner_card.env.cache.get(self.owner_card, _JuliaAtk2KnockoutReactor._ACTIVE, 1))
            self.owner_card.env.cache.set(self.owner_card, _JuliaAtk2KnockoutReactor._ACTIVE, s - 1)
        return self.generate_response()

class JuliaCiacerelli(AVGECharacterCard):
    _ATK1_ITEM_KEY = "julia_atk1_item"
    _ENERGY_REMOVAL_KEY = "julia_energy_removal_target"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, PlayNonCharacterCard, EmptyEvent

        opp_hand = card.player.opponent.cardholders[Pile.HAND]
        items = [c for c in opp_hand if isinstance(c, AVGEItemCard)]

        missing = object()
        chosen = card.env.cache.get(card, JuliaCiacerelli._ATK1_ITEM_KEY, missing, True)
        if chosen is missing:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [JuliaCiacerelli._ATK1_ITEM_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {
                                LABEL_FLAG: "julia_ciacerelli_atk1",
                                TARGETS_FLAG: items,
                                DISPLAY_FLAG: list(opp_hand),
                                ALLOW_NONE: True
                            },
                        )
                    ]
                },
            )
        if(chosen is not None):
            card.propose(
                AVGEPacket([
                    PlayNonCharacterCard(chosen, ActionTypes.ATK_1, card)
                ], AVGEEngineID(card, ActionTypes.ATK_1, JuliaCiacerelli))
            )
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        card.add_listener(_JuliaAtk2KnockoutReactor(card))

        def atk() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_2,
                    card,
                )
            ]

        card.propose(AVGEPacket([atk], AVGEEngineID(card, ActionTypes.ATK_2, JuliaCiacerelli)))
        return card.generate_response()
