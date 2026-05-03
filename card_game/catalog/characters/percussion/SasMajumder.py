from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import InputEvent, TransferCard, AVGECardHPChange


class _SasDiscardReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(
            identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, SasMajumder),
            group=EngineGroup.EXTERNAL_REACTORS,
        )
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, TransferCard):
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type not in [Pile.ACTIVE, Pile.BENCH]:
            return False
        if self.owner_card.player is None or self.owner_card.player.opponent is None:
            return False
        if event.pile_to.pile_type != Pile.DISCARD:
            return False
        if event.card.player != self.owner_card.player:
            return False

        env = self.owner_card.env
        if env.player_turn != self.owner_card.player.opponent:
            return False

        _, prior_discard_idx = env.check_history(
            env.round_id,
            TransferCard,
            {'pile_to': self.owner_card.player.cardholders[Pile.DISCARD]},
        )
        if prior_discard_idx != -1:
            return False
        return True

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def react(self, args=None) -> Response:
        if args is None:
            args = {}
        assert isinstance(self.attached_event, TransferCard)
        event = self.attached_event

        choice = self.owner_card.env.cache.get(self.owner_card, SasMajumder._INPUT_DISCARD, None, True)
        if choice is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            self.owner_card.player,
                            [SasMajumder._INPUT_DISCARD],
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            self.owner_card,
                            StrSelectionQuery(
                                f'Cybersecurity: Put {str(event.card)} back on top of your deck?',
                                ['Yes', 'No'],
                                ['Yes', 'No'],
                                False,
                                False,
                            )
                        )
                    ]),
            )

        if choice == 'Yes':
            discard = self.owner_card.player.cardholders[Pile.DISCARD]
            deck = self.owner_card.player.cardholders[Pile.DECK]

            def transfer_top() -> PacketType:
                packet: PacketType = []
                if event.card in discard:
                    packet.append(
                        TransferCard(
                            event.card,
                            discard,
                            deck,
                            ActionTypes.PASSIVE,
                            self.owner_card,
                            Notify("Cybersecurity: Brought a card back", all_players, default_timeout),
                            0,
                        )
                    )
                return packet

            self.owner_card.propose(
                AVGEPacket([transfer_top], AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, SasMajumder))
            )
        return Response(ResponseType.ACCEPT, Data())
    
    def __str__(self):
        return "Sas Majumder: Cybersecurity"


class SasMajumder(AVGECharacterCard):
    _INPUT_DISCARD = "sas_passive_input"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PERCUSSION, 2, 3)
        self.atk_1_name = 'Four Mallets'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(_SasDiscardReactor(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        packet = []

        def make_hit(draw_card: bool = False):
            def hit() -> PacketType:
                p: PacketType = []
                p.append(
                    AVGECardHPChange(
                        card.player.opponent.get_active_card(),
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PERCUSSION,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
                if draw_card and len(card.player.cardholders[Pile.DECK]) > 0:
                    p.append(
                        TransferCard(
                            card.player.cardholders[Pile.DECK].peek(),
                            card.player.cardholders[Pile.DECK],
                            card.player.cardholders[Pile.HAND],
                            ActionTypes.ATK_1,
                            card,
                            None,
                        )
                    )
                return p
            return hit

        packet.extend([make_hit(), make_hit(), make_hit(), make_hit(draw_card=True)])

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, SasMajumder)))
        return self.generic_response(card, ActionTypes.ATK_1)
