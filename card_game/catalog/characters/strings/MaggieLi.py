from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import InputEvent, AVGECardHPChange, AVGEEnergyTransfer


class _MaggieTurnBeginReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, MaggieLi), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import PhasePickCard

        if not isinstance(event, PhasePickCard):
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type not in [Pile.ACTIVE, Pile.BENCH]:
            return False
        return self.owner_card.player == self.owner_card.env.player_turn

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def react(self, args=None):
        if args is None:
            args = {}

        owner = self.owner_card
        if owner.hp >= owner.max_hp:
            return Response(
                ResponseType.ACCEPT, Data()
            )

        heal_choice = owner.env.cache.get(owner, MaggieLi._HEAL_CHOICE_KEY, None, True)
        if heal_choice is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            owner.player,
                            [MaggieLi._HEAL_CHOICE_KEY],
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            owner,
                            StrSelectionQuery(
                                'Midday Nap: Heal 10 damage from this character?',
                                ['Yes', 'No'],
                                ['Yes', 'No'],
                                False,
                                False,
                            )
                        )
                    ]),
            )

        if heal_choice != 'Yes':
            return Response(ResponseType.ACCEPT, Notify('Midday Nap used: chose not to heal.', all_players, default_timeout))

        def heal_packet() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    owner,
                    10,
                    AVGEAttributeModifier.ADDITIVE,
                    CardType.STRING,
                    ActionTypes.PASSIVE,
                    None,
                    owner,
                )
            )
            return packet

        self.propose(
            AVGEPacket([heal_packet], AVGEEngineID(owner, ActionTypes.PASSIVE, MaggieLi)),
            1,
        )
        return Response(ResponseType.ACCEPT, Notify('Midday Nap: Maggie Li healed 10 HP.', all_players, default_timeout))


class MaggieLi(AVGECharacterCard):
    _ENERGY_REMOVAL_KEY = 'maggieli_energy_removal_target'
    _HEAL_CHOICE_KEY = 'maggieli_turn_heal_choice'

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.STRING, 3, 3)
        self.atk_1_name = 'Snap Pizz'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(_MaggieTurnBeginReactor(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        opponent = card.player.opponent
        targets = [c for c in opponent.get_cards_in_play() if isinstance(c, AVGECharacterCard)]
        if len(targets) == 0:
            return Response(ResponseType.CORE, Notify('Snap Pizz failed: no opposing characters are in play.', all_players, default_timeout))

        chosen_target = card.env.cache.get(card, MaggieLi._ENERGY_REMOVAL_KEY, None, True)
        if chosen_target is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [MaggieLi._ENERGY_REMOVAL_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                'Snap Pizz: Choose one opposing character to remove up to 2 energy from.',
                                targets,
                                targets,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        def generate_packet() -> PacketType:
            packet: PacketType = []
            active = opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        20,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )

            if isinstance(chosen_target, AVGECharacterCard):
                for token in list(chosen_target.energy)[:2]:
                    packet.append(
                        AVGEEnergyTransfer(
                            token,
                            chosen_target,
                            chosen_target.env,
                            ActionTypes.ATK_1,
                            card,
                            None,
                        )
                    )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, MaggieLi)))
        return self.generic_response(card, ActionTypes.ATK_1)
