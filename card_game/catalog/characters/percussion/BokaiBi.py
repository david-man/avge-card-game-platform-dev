from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class BokaiBi(AVGECharacterCard):
    _D6_KEY = "bokaibi_d6_roll"
    _PASSIVE_DAMAGE_CHOICE_KEY = "bokaibi_passive_damage_choice"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PERCUSSION, 2, 2)
        self.atk_1_name = 'Rimshot'
        self.has_passive = True

    def passive(self) -> Response:
        class _BokaiTransferReactor(AVGEReactor):
            def __init__(self, owner_card: AVGECharacterCard):
                super().__init__(
                    identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, BokaiBi),
                    group=EngineGroup.EXTERNAL_REACTORS,
                )
                self.owner_card = owner_card
                self._matched_hand_card: AVGECard | None = None

            def _find_matching_hand_card(self, target_card: AVGECard) -> AVGECard | None:
                for hand_card in self.owner_card.player.cardholders[Pile.HAND]:
                    if type(hand_card) == type(target_card):
                        return hand_card
                return None

            def _is_play_like_hand_transfer(self, event: AVGEEvent) -> bool:
                from card_game.internal_events import TransferCard

                if not isinstance(event, TransferCard):
                    return False
                if event.pile_from.pile_type != Pile.HAND:
                    return False
                return event.pile_to.pile_type in (Pile.BENCH, Pile.ACTIVE, Pile.TOOL, Pile.STADIUM)

            def event_match(self, event):
                from card_game.internal_events import TransferCard, PlayNonCharacterCard

                self._matched_hand_card = None
                if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type not in [Pile.ACTIVE, Pile.BENCH]:
                    return False
                if isinstance(event, TransferCard):
                    if not self._is_play_like_hand_transfer(event):
                        return False
                    if event.card.player != self.owner_card.player.opponent:
                        return False
                    overlap = self._find_matching_hand_card(event.card)
                    if overlap is None:
                        return False
                    self._matched_hand_card = overlap
                    return True
                elif isinstance(event, PlayNonCharacterCard):
                    if event.card.player != self.owner_card.player.opponent:
                        return False
                    overlap = self._find_matching_hand_card(event.card)
                    if overlap is None:
                        return False
                    self._matched_hand_card = overlap
                    return True
                return False

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                return

            def react(self) -> Response:
                from card_game.internal_events import AVGECardHPChange, InputEvent, PlayNonCharacterCard, TransferCard

                assert isinstance(self.attached_event, (TransferCard, PlayNonCharacterCard))
                overlap = self._matched_hand_card if self._matched_hand_card is not None else self._find_matching_hand_card(self.attached_event.card)
                if overlap is None:
                    self._matched_hand_card = None
                    return Response(ResponseType.CORE, Data())

                choice = self.owner_card.env.cache.get(self.owner_card, BokaiBi._PASSIVE_DAMAGE_CHOICE_KEY, None, True)
                if choice is None:
                    return Response(
                        ResponseType.INTERRUPT,
                        Interrupt[AVGEEvent]([
                                InputEvent(
                                    self.owner_card.player,
                                    [BokaiBi._PASSIVE_DAMAGE_CHOICE_KEY],
                                    lambda r: True,
                                    ActionTypes.PASSIVE,
                                    self.owner_card,
                                    StrSelectionQuery(
                                        "Algorithm: Reveal matching hand card to deal 20 damage?",
                                        ["Yes", "No"],
                                        ["Yes", "No"],
                                        False,
                                        False,
                                    )
                                )
                            ]),
                    )

                if choice == "Yes":
                    def gen() -> PacketType:
                        packet: PacketType = []
                        revealed_cards: list[AVGECard] = [overlap]
                        packet.append(
                            AVGECardHPChange(
                                self.owner_card.player.opponent.get_active_card(),
                                20,
                                AVGEAttributeModifier.SUBSTRACTIVE,
                                CardType.PERCUSSION,
                                ActionTypes.PASSIVE,
                                RevealCards("Algorithm: revealed matching hand card", all_players, default_timeout, revealed_cards),
                                self.owner_card,
                            )
                        )
                        return packet
                    self.owner_card.propose(
                        AVGEPacket([gen], AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, BokaiBi))
                    )

                self._matched_hand_card = None
                return Response(ResponseType.CORE, Data())

        reactor = _BokaiTransferReactor(self)
        self.add_listener(reactor)
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange

        roll = card.env.cache.get(card, BokaiBi._D6_KEY, None, True)
        if roll is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [BokaiBi._D6_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            D6Data("Rimshot: Roll a d6")
                        )
                    ]),
            )
        val = int(roll)
        if val <= 4:
            def generate() -> PacketType:
                packet: PacketType = []
                packet.append(AVGECardHPChange(
                        card.player.opponent.get_active_card(),
                        60,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PERCUSSION,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    ))
                return packet
            card.propose(
                AVGEPacket([
                    generate
                ], AVGEEngineID(card, ActionTypes.ATK_1, BokaiBi))
            )

        return self.generic_response(card, ActionTypes.ATK_1)
