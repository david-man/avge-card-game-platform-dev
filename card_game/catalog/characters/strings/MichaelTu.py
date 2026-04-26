from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, AVGEEnergyTransfer, TransferCard, AVGECardHPChange, ReorderCardholder, EmptyEvent


class MichaelTu(AVGECharacterCard):
    _ATK1_TARGET = 'michaeltu_atk1_target'

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 2)
        self.atk_1_name = '440 Hz'
        self.atk_2_name = 'Synchro Summon'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        player = card.player
        if len(player.energy) <= 0:
            return Response(ResponseType.CORE, Notify('440 Hz failed: no energy to attach.', all_players, default_timeout))

        bench = list(player.cardholders[Pile.BENCH])
        if len(bench) == 0:
            return Response(ResponseType.CORE, Notify('440 Hz failed: no benched characters.', all_players, default_timeout))

        chosen = card.env.cache.get(card, MichaelTu._ATK1_TARGET, None, True)
        if chosen is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            player,
                            [MichaelTu._ATK1_TARGET],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                '440 Hz: Choose one benched character to attach 1 energy.',
                                bench,
                                bench,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        if not isinstance(chosen, AVGECharacterCard) or chosen not in player.cardholders[Pile.BENCH]:
            return Response(ResponseType.CORE, Notify('440 Hz failed: selected card is not a valid benched character.', all_players, default_timeout))

        card.propose(
            AVGEPacket([
                AVGEEnergyTransfer(player.energy[0], card.env, chosen, ActionTypes.ATK_1, card, None)
            ], AVGEEngineID(card, ActionTypes.ATK_1, MichaelTu))
        )

        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        player = card.player
        deck = player.cardholders[Pile.DECK]
        hand = player.cardholders[Pile.HAND]

        revealed: list[AVGECard] = []
        first_char: AVGECharacterCard | None = None
        for c in deck:
            revealed.append(c)
            if isinstance(c, AVGECharacterCard):
                first_char = c
                break

        packet: PacketType = []
        packet.append(
            EmptyEvent(
                ActionTypes.ATK_2,
                card,
                ResponseType.CORE,
                RevealCards('Synchro Summon: Revealed cards', all_players, default_timeout, revealed),
            )
        )

        if first_char is not None and first_char.card_type != CardType.STRING:
            packet.append(
                TransferCard(
                    first_char,
                    deck,
                    hand,
                    ActionTypes.ATK_2,
                    card,
                    None,
                )
            )
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    30,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_2,
                    None,
                    card,
                )
            )

        def shuffle_deck() -> PacketType:
            p: PacketType = []
            if len(deck) > 1:
                p.append(
                    ReorderCardholder(
                        deck,
                        random.sample(deck.get_order(), len(deck)),
                        ActionTypes.ATK_2,
                        card,
                        None,
                    )
                )
            return p

        packet.append(shuffle_deck)

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, MichaelTu)))
        return self.generic_response(card, ActionTypes.ATK_2)
