from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, ReorderCardholder, EmptyEvent, AVGECardHPChange, AVGEEnergyTransfer

class AndreaCR(AVGECharacterCard):
    _REORDER_BASE_KEY = "andreacr_reorder_top"
    _BOTTOM_CARD_KEY = "andreacr_bottom_card"
    _ENERGY_REMOVAL_KEY = "andreacr_energy_removal_target"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 3)
        self.atk_1_name = 'Foresight'
        self.atk_2_name = 'Snap Pizz'

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        opponent_deck = card.player.opponent.cardholders[Pile.DECK]
        consider_count = min(3, len(opponent_deck))
        if consider_count <= 1:
            card.propose(
                AVGEPacket(
                    [
                        EmptyEvent(
                            ActionTypes.ATK_1,
                            card,
                            ResponseType.CORE,
                            Notify(
                                f"{str(card)} tried to use Foresight, but there were not enough cards in the opponent deck.",
                                all_players,
                                default_timeout,
                            ),
                        )
                    ],
                    AVGEEngineID(card, ActionTypes.ATK_1, AndreaCR),
                )
            )
            return Response(ResponseType.CORE, Data())

        top_cards = list(opponent_deck.peek_n(consider_count))
        missing = object()
        bottom_card: AVGECard | None = None

        if consider_count == 2:
            reorder_keys = [AndreaCR._REORDER_BASE_KEY + str(i) for i in range(2)]
            chosen_order_probe = [card.env.cache.get(card, key, missing, False) for key in reorder_keys]
            if any(selection is missing for selection in chosen_order_probe):
                return Response(
                    ResponseType.INTERRUPT,
                    Interrupt[AVGEEvent]([
                            InputEvent(
                                card.player,
                                reorder_keys,
                                lambda res : True,
                                ActionTypes.ATK_1,
                                card,
                                CardSelectionQuery(
                                    'Foresight: Reorder the top 2 cards of your opponent deck.',
                                    top_cards,
                                    top_cards,
                                    False,
                                    False,
                                )
                            )
                        ]),
                )

            chosen_order = [card.env.cache.get(card, key, missing, True) for key in reorder_keys]
            chosen_cards = [c for c in chosen_order if isinstance(c, AVGECard) and c in top_cards]
            if len(chosen_cards) != 2 or chosen_cards[0] == chosen_cards[1]:
                raise Exception('Foresight: invalid reorder selection for top 2 cards')
        else:
            bottom_card_probe = card.env.cache.get(card, AndreaCR._BOTTOM_CARD_KEY, missing, False)
            if bottom_card_probe is missing:
                return Response(
                    ResponseType.INTERRUPT,
                    Interrupt[AVGEEvent]([
                            InputEvent(
                                card.player,
                                [AndreaCR._BOTTOM_CARD_KEY],
                                lambda res : True,
                                ActionTypes.ATK_1,
                                card,
                                CardSelectionQuery(
                                    'Foresight: Choose one of the top 3 cards to send to the bottom of your opponent deck.',
                                    top_cards,
                                    top_cards,
                                    False,
                                    False,
                                )
                            )
                        ]),
                )

            if not isinstance(bottom_card_probe, AVGECard) or bottom_card_probe not in top_cards:
                raise Exception('Foresight: invalid bottom-card selection')

            remaining_top_cards = [c for c in top_cards if c != bottom_card_probe]
            reorder_keys = [AndreaCR._REORDER_BASE_KEY + str(i) for i in range(2)]
            chosen_order_probe = [card.env.cache.get(card, key, missing, False) for key in reorder_keys]
            if any(selection is missing for selection in chosen_order_probe):
                return Response(
                    ResponseType.INTERRUPT,
                    Interrupt[AVGEEvent]([
                            InputEvent(
                                card.player,
                                reorder_keys,
                                lambda res : True,
                                ActionTypes.ATK_1,
                                card,
                                CardSelectionQuery(
                                    'Foresight: Reorder the remaining 2 cards.',
                                    remaining_top_cards,
                                    remaining_top_cards,
                                    False,
                                    False,
                                )
                            )
                        ]),
                )

            bottom_card_value = card.env.cache.get(card, AndreaCR._BOTTOM_CARD_KEY, missing, True)
            if not isinstance(bottom_card_value, AVGECard) or bottom_card_value not in top_cards:
                raise Exception('Foresight: invalid bottom-card selection')
            bottom_card = bottom_card_value

            chosen_order = [card.env.cache.get(card, key, missing, True) for key in reorder_keys]
            chosen_cards = [c for c in chosen_order if isinstance(c, AVGECard) and c in remaining_top_cards]
            if len(chosen_cards) != 2 or chosen_cards[0] == chosen_cards[1]:
                raise Exception('Foresight: invalid reorder selection for remaining cards')

        original_order = list(opponent_deck.get_order())
        top_ids = [c.unique_id for c in top_cards]
        chosen_ids = [c.unique_id for c in chosen_cards]
        remaining_ids = [cid for cid in original_order if cid not in top_ids]

        if consider_count == 2:
            new_order = chosen_ids + remaining_ids
        else:
            if not isinstance(bottom_card, AVGECard):
                raise Exception('Foresight: missing bottom-card during reorder')
            new_order = chosen_ids + remaining_ids + [bottom_card.unique_id]

        card.propose(
            AVGEPacket(
                [
                    ReorderCardholder(
                        opponent_deck,
                        new_order,
                        ActionTypes.ATK_1,
                        card,
                        None,
                    )
                ],
                AVGEEngineID(card, ActionTypes.ATK_1, AndreaCR),
            )
        )
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        opponent = card.player.opponent
        chosen_target = card.env.cache.get(card, AndreaCR._ENERGY_REMOVAL_KEY, None, True)
        targets = [c for c in opponent.get_cards_in_play() if isinstance(c, AVGECharacterCard)]

        if chosen_target is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [AndreaCR._ENERGY_REMOVAL_KEY],
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            CardSelectionQuery(
                                'Snap Pizz: Choose one opposing character to remove up to 2 energy from',
                                targets,
                                targets,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        def gen() -> PacketType:
            packet: PacketType = []
            active = opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        20,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )
            return packet

        assert isinstance(chosen_target, AVGECharacterCard)

        def gen1() -> PacketType:
            k: PacketType = []
            for token in list(chosen_target.energy)[:min(2, len(chosen_target.energy))]:
                k.append(
                    AVGEEnergyTransfer(
                        token,
                        chosen_target,
                        chosen_target.env,
                        ActionTypes.ATK_2,
                        card,
                        None,
                    )
                )
            return k

        packet: PacketType = [gen, gen1]
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, AndreaCR)))
        return self.generic_response(card, ActionTypes.ATK_2)
