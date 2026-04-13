from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.avge_abstracts.AVGECards import AVGECharacterCard
from card_game.constants import *
from card_game.constants import ActionTypes, Response
from card_game.engine.engine_constants import EngineGroup


class _MaggieTurnBeginReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, MaggieLi), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import PhasePickCard

        if not isinstance(event, PhasePickCard):
            return False
        if self.owner_card.cardholder is None:
            return False
        if self.owner_card.cardholder.pile_type not in [Pile.ACTIVE, Pile.BENCH]:
            return False
        if self.owner_card.hp >= self.owner_card.max_hp:
            return False
        return event.player == self.owner_card.player

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def react(self, args=None):
        from card_game.internal_events import InputEvent, AVGECardHPChange

        owner = self.owner_card
        env = owner.env
        heal_choice = env.cache.get(owner, MaggieLi._HEAL_CHOICE_KEY, None, True)
        if heal_choice is None:
            return owner.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            owner.player,
                            [MaggieLi._HEAL_CHOICE_KEY],
                            InputType.BINARY,
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            owner,
                            {LABEL_FLAG: "maggie_li_turn_heal_choice"},
                        )
                    ]
                },
            )

        if heal_choice:
            self.propose(
                AVGEPacket(
                    [
                        AVGECardHPChange(
                            owner,
                            10,
                            AVGEAttributeModifier.ADDITIVE,
                            CardType.STRING,
                            ActionTypes.PASSIVE,
                            owner,
                        )
                    ],
                    AVGEEngineID(owner, ActionTypes.PASSIVE, MaggieLi),
                ),
                1,
            )

        return self.generate_response()

class MaggieLi(AVGECharacterCard):
    _ENERGY_REMOVAL_KEY = "maggieli_energy_removal_target"
    _HEAL_CHOICE_KEY = "maggieli_turn_heal_choice"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.STRING, 2, 3)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        card.add_listener(_MaggieTurnBeginReactor(card))
        return card.generate_response()
    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange, AVGEEnergyTransfer, EmptyEvent

        opponent = card.player.opponent

        targets = [card for card in opponent.get_cards_in_play() if isinstance(card, AVGECharacterCard) and len(card.energy) > 0]
        if(len(targets) == 0):
            return card.generate_response(data={MESSAGE_KEY: "No cards to discard energy from!"})
        chosen_target = card.env.cache.get(card, MaggieLi._ENERGY_REMOVAL_KEY, None, True)
        if chosen_target is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [MaggieLi._ENERGY_REMOVAL_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {
                                LABEL_FLAG: "maggie_li_snap_pizz",
                                TARGETS_FLAG: targets,
                                DISPLAY_FLAG:opponent.get_cards_in_play()
                            },
                        )
                    ]
                },
            )
        def atk() -> PacketType:
            return [
                AVGECardHPChange(
                    opponent.get_active_card(),
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_2,
                    card,
                )
            ]
        packet : PacketType = [atk]
        assert isinstance(chosen_target, AVGECharacterCard)
        def gen() -> PacketType:
            k : PacketType = []
            for token in list(chosen_target.energy)[:2]:
                k.append(AVGEEnergyTransfer(token, chosen_target, chosen_target.env, ActionTypes.ATK_2, card))
            return k
        packet.append(gen)

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, MaggieLi)))
        return card.generate_response()
