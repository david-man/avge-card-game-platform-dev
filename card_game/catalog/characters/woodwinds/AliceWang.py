from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import AVGEReactor
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class AliceWang(AVGECharacterCard):
    _CARDS_TO_DISCARD_BASE_KEY = "alice_cards_to_discard_"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 1, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        owner_card = card

        class _OpponentHandEqualizer(AVGEReactor):
            def __init__(self):
                super().__init__(
                    identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, AliceWang),
                    group=EngineGroup.EXTERNAL_REACTORS,
                )

            def event_match(self, event):
                from card_game.internal_events import TurnEnd

                if not isinstance(event, TurnEnd):
                    return False
                return event.env.player_turn == owner_card.player

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                return

            def make_announcement(self) -> bool:
                return True

            def package(self):
                return "AliceWang Reactor"

            def react(self, args=None):
                if args is None:
                    args = {}
                from card_game.internal_events import InputEvent, TransferCard

                owner_hand = owner_card.player.cardholders[Pile.HAND]
                opponent_hand = owner_card.player.opponent.cardholders[Pile.HAND]
                opponent_discard = owner_card.player.opponent.cardholders[Pile.DISCARD]

                extra_cards = len(opponent_hand) - len(owner_hand)
                if extra_cards <= 0:
                    return self.generate_response()

                keys = [AliceWang._CARDS_TO_DISCARD_BASE_KEY + str(i) for i in range(extra_cards)]
                discarded_cards = [owner_card.env.cache.get(owner_card, key, None, True) for key in keys]
                if discarded_cards[0] is None:
                    return self.generate_response(
                        ResponseType.INTERRUPT,
                        {
                            INTERRUPT_KEY: [
                                InputEvent(
                                    owner_card.player.opponent,
                                    keys,
                                    InputType.SELECTION,
                                    lambda r: True,
                                    ActionTypes.PASSIVE,
                                    owner_card,
                                    {
                                        "query_label": "alicewang_discard_passive",
                                        "targets": list(opponent_hand),
                                    },
                                )
                            ]
                        },
                    )
                
                packet = [
                    TransferCard(
                        selected,
                        opponent_hand,
                        opponent_discard,
                        ActionTypes.PASSIVE,
                        owner_card,
                    )
                    for selected in discarded_cards if isinstance(selected, AVGECard)
                ]
                self.propose(AVGEPacket(packet, AVGEEngineID(owner_card, ActionTypes.PASSIVE, AliceWang)))
                return self.generate_response()

        owner_card.add_listener(_OpponentHandEqualizer())
        return owner_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChangeCreator

        card.propose(
            AVGEPacket([
                AVGECardHPChangeCreator(
                    lambda: card.player.opponent.get_active_card(),
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_1, AliceWang))
        )
        return card.generate_response()
