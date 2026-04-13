from __future__ import annotations

from random import randint

from card_game.avge_abstracts import *
from card_game.catalog.items.AVGEBirb import AVGEBirb
from card_game.constants import *
from card_game.constants import ActionTypes
from card_game.engine.engine_constants import EngineGroup


class _SophiaAtk2KnockoutReactor(AVGEReactor):
    _ACTIVE = "sophiaatk2bouncing"
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.ATK_2, SophiaYWang), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card
        self.owner_card.env.cache.set(self.owner_card, _SophiaAtk2KnockoutReactor._ACTIVE, 1)

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
        if(self.owner_card.env.cache.get(self.owner_card, _SophiaAtk2KnockoutReactor._ACTIVE, 1) == 0):
            self.owner_card.env.cache.delete(self.owner_card, _SophiaAtk2KnockoutReactor._ACTIVE)
            self.invalidate()

    def react(self, args=None):
        from card_game.internal_events import AVGECardHPChange

        assert isinstance(self.attached_event, AVGECardHPChange)
        assert isinstance(self.attached_event.final_change, int)
        owner = self.owner_card
        
        if(self.attached_event.final_change == 0):
            def splash_remaining() -> PacketType:
                s = cast(int, self.owner_card.env.cache.get(self.owner_card, _SophiaAtk2KnockoutReactor._ACTIVE, 1))
                self.owner_card.env.cache.set(self.owner_card, _SophiaAtk2KnockoutReactor._ACTIVE, s - 1)
                targets = [
                    target
                    for target in owner.player.opponent.get_cards_in_play()
                    if isinstance(target, AVGECharacterCard) and target.hp > 0
                ]
                splashes_left = self.owner_card.env.cache.get(self.owner_card, _SophiaAtk2KnockoutReactor._ACTIVE, 1)
                assert isinstance(splashes_left, int)
                self.owner_card.env.cache.set(self.owner_card, _SophiaAtk2KnockoutReactor._ACTIVE, splashes_left + len(targets))
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

            self.propose(AVGEPacket([splash_remaining], AVGEEngineID(owner, ActionTypes.ATK_2, SophiaYWang)))
        else:
            s = cast(int, self.owner_card.env.cache.get(self.owner_card, _SophiaAtk2KnockoutReactor._ACTIVE, 1))
            self.owner_card.env.cache.set(self.owner_card, _SophiaAtk2KnockoutReactor._ACTIVE, s - 1)
        return self.generate_response()

class SophiaYWang(AVGECharacterCard):
    _GACHA_GAMING_DRAW_KEY = "sophiaywang_gacha_gaming_draw"
    _GACHA_GAMING_DRAWN_CARDS = "sophiaywang_gacha_gaming_cards_drawn"
    _ENERGY_REMOVAL_KEY = "sophiaywang_energy_removal"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard

        env = card.env

        deck = card.player.cardholders[Pile.DECK]
        current_cards= env.cache.get(card, SophiaYWang._GACHA_GAMING_DRAWN_CARDS, [])
        assert isinstance(current_cards, list)
        if len(deck) == 0 or card.hp <= 20:
            packet : PacketType = []
            for transferred_card in current_cards:
                assert isinstance(transferred_card, AVGECard)
                def put_back(c=transferred_card) -> PacketType:
                    return [
                        TransferCard(
                            c,
                            c.cardholder,
                            card.player.cardholders[Pile.DECK],
                            ActionTypes.ATK_1,
                            card,
                            randint(0, len(deck)),
                        )
                    ]
                packet.append(
                    put_back
                )
            env.cache.delete(card, SophiaYWang._GACHA_GAMING_DRAWN_CARDS)
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, SophiaYWang)))
            return card.generate_response()

        draw = env.cache.get(card, SophiaYWang._GACHA_GAMING_DRAW_KEY, None, True)
        if draw is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [SophiaYWang._GACHA_GAMING_DRAW_KEY],
                            InputType.BINARY,
                            lambda l: True,
                            ActionTypes.ATK_1,
                            card,
                            {LABEL_FLAG: "sophia_y_wang_gacha_gaming_draw_next"},
                        )
                    ]
                },
            )

        if draw:
            next_card = deck.peek()
            if isinstance(next_card, AVGEBirb):
                env.cache.delete(card, SophiaYWang._GACHA_GAMING_DRAWN_CARDS)
                card.propose(
                    AVGEPacket([
                        AVGECardHPChange(
                            card,
                            card.max_hp,
                            AVGEAttributeModifier.SET_STATE,
                            CardType.STRING,
                            ActionTypes.ATK_1,
                            card,
                        )
                    ], AVGEEngineID(card, ActionTypes.ATK_1, SophiaYWang))
                )
                
                card.propose(
                AVGEPacket([
                    TransferCard(next_card, deck, card.player.cardholders[Pile.HAND], ActionTypes.ATK_1, card)
                ], AVGEEngineID(card, ActionTypes.ATK_1, SophiaYWang))
                )
                return card.generate_response()
            else:
                env.cache.set(card, SophiaYWang._GACHA_GAMING_DRAWN_CARDS, current_cards + [next_card])
                return card.generate_response(
                    ResponseType.INTERRUPT,
                    {
                        INTERRUPT_KEY: [
                            TransferCard(next_card, deck, card.player.cardholders[Pile.HAND], ActionTypes.ATK_1, card),
                            AVGECardHPChange(
                                card,
                                20,
                                AVGEAttributeModifier.SUBSTRACTIVE,
                                CardType.STRING,
                                ActionTypes.ATK_1,
                                card,
                            )
                        ]
                    },
                )
        else:
            packet : PacketType = []
            for transferred_card in current_cards:
                assert isinstance(transferred_card, AVGECard)
                def put_back(c=transferred_card) -> PacketType:
                    return [
                        TransferCard(
                            c,
                            c.cardholder,
                            card.player.cardholders[Pile.DECK],
                            ActionTypes.ATK_1,
                            card,
                            randint(0, len(deck)),
                        )
                    ]
                packet.append(
                    put_back
                )
            env.cache.delete(card, SophiaYWang._GACHA_GAMING_DRAWN_CARDS)
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, SophiaYWang)))
            return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        card.add_listener(_SophiaAtk2KnockoutReactor(card))

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

        card.propose(AVGEPacket([atk], AVGEEngineID(card, ActionTypes.ATK_2, SophiaYWang)))
        return card.generate_response()