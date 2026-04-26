from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard


class BettySolomon(AVGECharacterCard):
    _ATK_1_KEY = 'bettysolomon_outreach_choice'
    _COIN_KEY_0 = 'bettysolomon_coin_0'
    _COIN_KEY_1 = 'bettysolomon_coin_1'

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.WOODWIND, 1, 1, 3)
        self.atk_1_name = 'Outreach'
        self.atk_2_name = 'Multiphonics'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        deck = card.player.cardholders[Pile.DECK]
        character_cards = [c for c in deck if isinstance(c, AVGECharacterCard)]

        missing = object()
        chosen_card = card.env.cache.get(card, BettySolomon._ATK_1_KEY, missing, True)
        if chosen_card is missing and len(character_cards) > 0:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [BettySolomon._ATK_1_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                'Outreach: Search for any character card and put it on top of your deck.',
                                character_cards,
                                list(deck),
                                False,
                                False,
                            )
                        )
                    ]),
            )

        if isinstance(chosen_card, AVGECharacterCard) and chosen_card in deck:
            card.propose(
                AVGEPacket([
                    TransferCard(chosen_card, deck, deck, ActionTypes.ATK_1, card, None, 0)
                ], AVGEEngineID(card, ActionTypes.ATK_1, BettySolomon))
            )

        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        r0 = card.env.cache.get(card, BettySolomon._COIN_KEY_0, None, True)
        r1 = card.env.cache.get(card, BettySolomon._COIN_KEY_1, None, True)
        if r0 is None or r1 is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [BettySolomon._COIN_KEY_0, BettySolomon._COIN_KEY_1],
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            CoinflipData('Multiphonics: Flip 2 coins.')
                        )
                    ]),
            )

        heads = int(r0) + int(r1)

        def generate_packet() -> PacketType:
            packet: PacketType = []
            if heads == 2:
                for target in card.player.opponent.cardholders[Pile.BENCH]:
                    if isinstance(target, AVGECharacterCard):
                        packet.append(
                            AVGECardHPChange(
                                target,
                                50,
                                AVGEAttributeModifier.SUBSTRACTIVE,
                                CardType.WOODWIND,
                                ActionTypes.ATK_2,
                                None,
                                card,
                            )
                        )
            elif heads == 0:
                active = card.player.opponent.get_active_card()
                if isinstance(active, AVGECharacterCard):
                    packet.append(
                        AVGECardHPChange(
                            active,
                            100,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.WOODWIND,
                            ActionTypes.ATK_2,
                            None,
                            card,
                        )
                    )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, BettySolomon)))
        return self.generic_response(card, ActionTypes.ATK_2)
