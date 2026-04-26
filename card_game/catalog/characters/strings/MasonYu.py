from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, AVGECardStatusChange, TransferCard, PlayCharacterCard, AVGEEnergyTransfer


class MasonYu(AVGECharacterCard):
    _ATK1_TARGET = 'mason_atk1_target'
    _ATK2_TARGET_1 = 'mason_atk2_target_1'
    _ATK2_TARGET_2 = 'mason_atk2_target_2'
    _ATK2_RANDOM_SELECTED = 'mason_atk2_random_selected'
    _ATK2_OTHER = 'mason_atk2_other'
    _ATK2_ATTACK_CHOICE = 'mason_atk2_attack_choice'

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 3, 3)
        self.atk_1_name = 'Arrangement'
        self.atk_2_name = 'We Play God'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        bench = card.player.cardholders[Pile.BENCH]
        if len(bench) == 0:
            return Response(ResponseType.CORE, Notify('Arrangement failed: no benched characters on your side.', all_players, default_timeout))

        chosen = card.env.cache.get(card, MasonYu._ATK1_TARGET, None, True)
        if chosen is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [MasonYu._ATK1_TARGET],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                'Arrangement: Choose one benched character to give Arranger status.',
                                list(bench),
                                list(bench),
                                False,
                                False,
                            )
                        )
                    ]),
            )

        if not isinstance(chosen, AVGECharacterCard) or chosen not in bench:
            return Response(ResponseType.CORE, Notify('Arrangement failed: selected card is not a valid benched character.', all_players, default_timeout))

        def arrange_packet() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardStatusChange(
                    StatusEffect.ARRANGER,
                    StatusChangeType.ADD,
                    chosen,
                    ActionTypes.ATK_1,
                    card,
                    None,
                )
            )
            return packet

        card.propose(AVGEPacket([arrange_packet], AVGEEngineID(card, ActionTypes.ATK_1, MasonYu)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        if len(card.energy) == 0:
            return Response(ResponseType.CORE, Notify('We Play God failed: Mason Yu has no energy to discard.', all_players, default_timeout))

        chars_in_play = [c for p in [card.player, card.player.opponent] for c in p.get_cards_in_play() if isinstance(c, AVGECharacterCard)]

        chosen_1 = card.env.cache.get(card, MasonYu._ATK2_TARGET_1, None, True)
        chosen_2 = card.env.cache.get(card, MasonYu._ATK2_TARGET_2, None, True)
        if chosen_1 is None or chosen_2 is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [MasonYu._ATK2_TARGET_1, MasonYu._ATK2_TARGET_2],
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            CardSelectionQuery(
                                'We Play God: Choose any two characters in play.',
                                chars_in_play,
                                chars_in_play,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        random_selected = card.env.cache.get(card, MasonYu._ATK2_RANDOM_SELECTED, None)
        other = card.env.cache.get(card, MasonYu._ATK2_OTHER, None)
        if random_selected is None or other is None:
            random_selected = random.choice([chosen_1, chosen_2])
            other = chosen_2 if random_selected == chosen_1 else chosen_1
            card.env.cache.set(card, MasonYu._ATK2_RANDOM_SELECTED, random_selected)
            card.env.cache.set(card, MasonYu._ATK2_OTHER, other)

        assert isinstance(other, AVGECharacterCard)
        available_attacks: list[str] = []
        attack_labels: list[str] = []
        if other.atk_1_name is not None:
            available_attacks.append('atk_1')
            attack_labels.append(other.atk_1_name)
        if other.atk_2_name is not None:
            available_attacks.append('atk_2')
            attack_labels.append(other.atk_2_name)


        attack_choice = card.env.cache.get(card, MasonYu._ATK2_ATTACK_CHOICE, None, True)
        if attack_choice is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [MasonYu._ATK2_ATTACK_CHOICE],
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            StrSelectionQuery(
                                f'We Play God: Choose an attack from {str(other)}.',
                                available_attacks,
                                attack_labels,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        action_type = ActionTypes.ATK_1 if attack_choice == 'atk_1' else ActionTypes.ATK_2
        assert isinstance(random_selected, AVGECharacterCard)

        def play_god_packet() -> PacketType:
            packet: PacketType = []

            # Discard one energy from Mason as the attack cost effect.
            packet.append(
                AVGEEnergyTransfer(
                    card.energy[0],
                    card,
                    card.env,
                    ActionTypes.ATK_2,
                    card,
                    None,
                )
            )

            selected_holder = random_selected.cardholder
            if selected_holder is not None:
                active_holder = random_selected.player.cardholders[Pile.ACTIVE]
                current_active = random_selected.player.get_active_card()

                if selected_holder != active_holder:
                    packet.append(
                        TransferCard(
                            random_selected,
                            selected_holder,
                            active_holder,
                            ActionTypes.ATK_2,
                            card,
                            None,
                        )
                    )
                    packet.append(
                        TransferCard(
                            current_active,
                            active_holder,
                            selected_holder,
                            ActionTypes.ATK_2,
                            card,
                            None,
                        )
                    )

            packet.append(
                PlayCharacterCard(
                    other,
                    action_type,
                    ActionTypes.ATK_2,
                    card,
                )
            )
            return packet

        card.propose(AVGEPacket([play_god_packet], AVGEEngineID(card, ActionTypes.ATK_2, MasonYu)))
        card.env.cache.delete(card, MasonYu._ATK2_RANDOM_SELECTED)
        card.env.cache.delete(card, MasonYu._ATK2_OTHER)
        return self.generic_response(card, ActionTypes.ATK_2)
