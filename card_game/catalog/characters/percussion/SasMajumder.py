from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class SasMajumder(AVGECharacterCard):
    _LAST_ROUND_USED_KEY = "sas_passive_last_round"
    _INPUT_DISCARD = "sas_passive_input"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PERCUSSION, 2, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        owner_card = card

        class _SasDiscardReactor(AVGEReactor):
            def __init__(self):
                super().__init__(
                    identifier=(owner_card, AVGEEventListenerType.PASSIVE),
                    group=EngineGroup.EXTERNAL_REACTORS,
                )

            def event_match(self, event):
                from card_game.internal_events import TransferCard

                if not isinstance(event, TransferCard):
                    return False
                if event.pile_to.pile_type != Pile.BENCH:
                    return False
                if event.card.player != owner_card.player.opponent:
                    return False

                env = owner_card.env
                if env.player_turn != owner_card.player.opponent:
                    return False

                last_round_used = env.cache.get(owner_card, SasMajumder._LAST_ROUND_USED_KEY, None)
                if last_round_used is not None and env.round_id == last_round_used:
                    return False
                return True

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                return

            def make_announcement(self) -> bool:
                return True

            def package(self):
                return "Sas Majumder Transfer Reactor"

            def react(self, args=None) -> Response:
                if args is None:
                    args = {}
                from card_game.internal_events import TransferCard, InputEvent

                event: TransferCard = self.attached_event
                choice = owner_card.env.cache.get(owner_card, SasMajumder._INPUT_DISCARD, None, True)
                if choice is None:
                    return owner_card.generate_response(
                        ResponseType.INTERRUPT,
                        {
                            INTERRUPT_KEY: [
                                InputEvent(
                                    owner_card.player,
                                    [SasMajumder._INPUT_DISCARD],
                                    InputType.BINARY,
                                    lambda r: True,
                                    ActionTypes.PASSIVE,
                                    owner_card,
                                    {"query_label": "sas-passive"},
                                )
                            ]
                        },
                    )
                if choice:
                    owner_card.propose(
                        TransferCard(
                            event.card,
                            owner_card.player.opponent.cardholders[Pile.BENCH],
                            owner_card.player.opponent.cardholders[Pile.DECK],
                            ActionTypes.PASSIVE,
                            owner_card,
                            0,
                        )
                    )
                    owner_card.env.cache.set(owner_card, SasMajumder._LAST_ROUND_USED_KEY, owner_card.env.round_id)

                return self.generate_response()

        owner_card.add_listener(_SasDiscardReactor())
        return owner_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import TransferCard, AVGECardHPChange

        packet = [
            AVGECardHPChange(
                lambda: card.player.opponent.get_active_card(),
                10,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.PERCUSSION,
                ActionTypes.ATK_1,
                card,
            ) for _ in range(4)
        ]
        if len(card.player.cardholders[Pile.DECK]) > 0:
            packet.append(
                TransferCard(
                    lambda: card.player.cardholders[Pile.DECK].peek(),
                    card.player.cardholders[Pile.DECK],
                    card.player.cardholders[Pile.HAND],
                    ActionTypes.ATK_1,
                    card,
                )
            )
        card.propose(packet)

        return card.generate_response()
