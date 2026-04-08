from __future__ import annotations

from card_game.avge_abstracts import *

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
    def passive(card: AVGECharacterCard) -> Response:
        owner_card = card

        class _SasDiscardReactor(AVGEReactor):
            def __init__(self):
                super().__init__(
                    identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, SasMajumder),
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
                assert(isinstance(self.attached_event, TransferCard))
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
                                    {"query_label": "sas_majumder_passive"},
                                )
                            ]
                        },
                    )
                if choice:
                    owner_card.propose(
                        AVGEPacket([
                            TransferCard(
                                event.card,
                                owner_card.player.opponent.cardholders[Pile.BENCH],
                                owner_card.player.opponent.cardholders[Pile.DECK],
                                ActionTypes.PASSIVE,
                                owner_card,
                                0,
                            )
                        ], AVGEEngineID(owner_card, ActionTypes.PASSIVE, SasMajumder))
                    )
                    owner_card.env.cache.set(owner_card, SasMajumder._LAST_ROUND_USED_KEY, owner_card.env.round_id)

                return self.generate_response()

        owner_card.add_listener(_SasDiscardReactor())
        return owner_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import TransferCard, AVGECardHPChange, EmptyEvent
        def gen_1() -> PacketType:
            return [AVGECardHPChange(
                card.player.opponent.get_active_card(),
                10,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.PERCUSSION,
                ActionTypes.ATK_2,
                card,
            )]
        packet : PacketType = ([gen_1] * 4)
        if len(card.player.cardholders[Pile.DECK]) > 0:
            def gen_2() -> PacketType:
                return [
                    TransferCard(
                        card.player.cardholders[Pile.DECK].peek(),
                        card.player.cardholders[Pile.DECK],
                        card.player.cardholders[Pile.HAND],
                        ActionTypes.ATK_2,
                        card,
                    )
                ]
            packet.append(
                gen_2
            )
        else:
            packet.append(
                EmptyEvent(
                    ActionTypes.ATK_2,
                    card,
                    response_data={MESSAGE_KEY: "No more cards to draw from deck"}
                )
            )
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, SasMajumder)))

        return card.generate_response()
