from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.catalog.items.ConcertProgram import ConcertProgram
from card_game.catalog.items.ConcertRoster import ConcertRoster
from card_game.catalog.items.ConcertTicket import ConcertTicket
from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard


class SarahChen(AVGECharacterCard):
    _DISCARD_SELECTION_KEY = 'sarahchen_discard_selection_'
    _TARGET_SELECTION_KEY = 'sarahchen_target_selection_'

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 1, 1, 3)
        self.atk_1_name = 'Double Tongue'
        self.atk_2_name = 'Artist Alley'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        def gen() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, SarahChen))
        )
        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, SarahChen))
        )
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        player = card.player
        hand = player.cardholders[Pile.HAND]
        discard = player.cardholders[Pile.DISCARD]
        opponent = player.opponent

        eligible_cards = [
            hand_card
            for hand_card in hand
            if isinstance(hand_card, (ConcertProgram, ConcertRoster, ConcertTicket))
        ]
        if len(eligible_cards) == 0:
            return self.generic_response(card, ActionTypes.ATK_2)

        discard_keys = [SarahChen._DISCARD_SELECTION_KEY + str(i) for i in range(len(eligible_cards))]
        missing = object()
        discard_probe = [card.env.cache.get(card, key, missing, False) for key in discard_keys]
        if discard_probe[0] is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            player,
                            discard_keys,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            CardSelectionQuery(
                                'Artist Alley: Choose any number of Concert Programs, Concert Rosters, or Concert Tickets to discard.',
                                eligible_cards,
                                list(hand),
                                True,
                                False,
                            )
                        )
                    ]),
            )

        packet: PacketType = []
        selected_keys = []
        for i, value in enumerate(discard_probe):
            if value is not None:
                selected_keys.append(SarahChen._TARGET_SELECTION_KEY + str(i))

        if len(selected_keys) > 0:
            targets_probe = [card.env.cache.get(card, key, missing, False) for key in selected_keys]
            if len(targets_probe) > 0 and targets_probe[0] is missing:
                possible_targets = [c for c in opponent.get_cards_in_play() if isinstance(c, AVGECharacterCard)]
                return Response(
                    ResponseType.INTERRUPT,
                    Interrupt[AVGEEvent]([
                            InputEvent(
                                player,
                                selected_keys,
                                lambda r: True,
                                ActionTypes.ATK_2,
                                card,
                                CardSelectionQuery(
                                    'Artist Alley: For each discarded card, choose one opposing character to take 40 damage.',
                                    possible_targets,
                                    possible_targets,
                                    False,
                                    True,
                                )
                            )
                        ]),
                )
            targets_vals = [card.env.cache.get(card, key, missing, True) for key in selected_keys]
        else:
            targets_vals = []

        discard_vals = [card.env.cache.get(card, key, missing, True) for key in discard_keys]
            
        for target in targets_vals:
            if isinstance(target, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        target,
                        40,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )

        for to_discard in discard_vals:
            if to_discard is not None and isinstance(to_discard, AVGECard) and to_discard in hand:
                packet.append(
                    TransferCard(
                        to_discard,
                        hand,
                        discard,
                        ActionTypes.ATK_2,
                        card,
                        None,
                    )
                )


        if len(packet) > 0:
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, SarahChen)))
            return self.generic_response(card, ActionTypes.ATK_2)
        else:
            return Response(ResponseType.CORE, Notify(f"{str(card)} used Artist Alley, but it didn't do anything...", all_players, default_timeout))
