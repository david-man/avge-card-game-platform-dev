from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import TransferCard, PlayNonCharacterCard, AVGECardHPChange, InputEvent


class IrisYang(AVGECharacterCard):
    _SPIKE_SWITCH_KEY = 'irisyang_spike_switch_target'

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 3)
        self.atk_1_name = 'Open Strings'
        self.atk_2_name = 'Spike'

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        def atk_active() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        packet: PacketType = [atk_active]

        deck = card.player.cardholders[Pile.DECK]
        hand = card.player.cardholders[Pile.HAND]
        discard = card.player.cardholders[Pile.DISCARD]

        def draw_and_maybe_use_item() -> PacketType:
            p: PacketType = []
            if len(deck) == 0:
                return p

            top = deck.peek()
            p.append(TransferCard(top, deck, hand, ActionTypes.ATK_1, card, None))
            if isinstance(top, AVGEItemCard):
                # Open Strings requires immediate item play after drawing.
                p.append(PlayNonCharacterCard(top, ActionTypes.ATK_1, card))
                p.append(TransferCard(top, hand, discard, ActionTypes.ATK_1, card, None))
            return p

        packet.append(draw_and_maybe_use_item)

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, IrisYang)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        opponent = card.player.opponent
        opponent_bench = opponent.cardholders[Pile.BENCH]

        missing = object()
        selected_bench = card.env.cache.get(card, IrisYang._SPIKE_SWITCH_KEY, missing, True)
        if len(opponent_bench) > 0 and selected_bench is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                    InputEvent(
                        card.player,
                        [IrisYang._SPIKE_SWITCH_KEY],
                        lambda r: True,
                        ActionTypes.ATK_2,
                        card,
                        CardSelectionQuery(
                            'Spike: You may switch your opponent\'s Active character with one of their Benched characters.',
                            list(opponent_bench),
                            list(opponent_bench),
                            True,
                            False,
                        )
                    )
                ]),
            )

        def generate_damage() -> PacketType:
            packet: PacketType = []
            active = opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        30,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )
            return packet

        packet: PacketType = [generate_damage]

        if isinstance(selected_bench, AVGECharacterCard) and selected_bench in opponent_bench:
            def generate_switch() -> PacketType:
                p: PacketType = []
                active_holder = opponent.cardholders[Pile.ACTIVE]
                active = opponent.get_active_card()
                if not isinstance(active, AVGECharacterCard):
                    return p
                if selected_bench not in opponent_bench:
                    return p

                p.append(
                    TransferCard(
                        active,
                        active_holder,
                        opponent_bench,
                        ActionTypes.ATK_2,
                        card,
                        None,
                    )
                )
                p.append(
                    TransferCard(
                        selected_bench,
                        opponent_bench,
                        active_holder,
                        ActionTypes.ATK_2,
                        card,
                        None,
                    )
                )
                return p

            packet.append(generate_switch)

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, IrisYang)))
        return self.generic_response(card, ActionTypes.ATK_2)
