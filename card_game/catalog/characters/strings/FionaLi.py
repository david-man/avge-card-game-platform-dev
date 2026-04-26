from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import *
from card_game.internal_events import AVGECardStatusChange, TransferCard, AVGECardHPChange


class _BenchMaidReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, FionaLi), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def update_status(self):
        return

    def event_match(self, event):
        if not isinstance(event, TransferCard):
            return False
        if self.owner_card.player is None:
            return False

        moved_to_bench = (
            event.card == self.owner_card
            and event.pile_to.pile_type == Pile.BENCH
            and event.pile_to.player == self.owner_card.player
        )
        moved_from_bench = (
            event.card == self.owner_card
            and event.pile_from.pile_type == Pile.BENCH
            and event.pile_from.player == self.owner_card.player
        )
        if moved_to_bench or moved_from_bench:
            return True

        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type != Pile.BENCH:
            return False

        return (
            event.pile_from.pile_type == Pile.ACTIVE
            and event.pile_from.player == self.owner_card.player
            and isinstance(event.card, AVGECharacterCard)
        ) or (
            event.pile_to.pile_type == Pile.ACTIVE
            and event.pile_to.player == self.owner_card.player
            and isinstance(event.card, AVGECharacterCard)
        )

    def react(self, args=None) -> Response:
        if args is None:
            args = {}
        event = self.attached_event
        assert isinstance(event, TransferCard)

        owner = self.owner_card
        packet: PacketType = []

        moved_to_bench = (
            event.card == owner
            and event.pile_to.pile_type == Pile.BENCH
            and event.pile_to.player == owner.player
        )
        moved_from_bench = (
            event.card == owner
            and event.pile_from.pile_type == Pile.BENCH
            and event.pile_from.player == owner.player
        )

        if moved_to_bench:
            active = owner.player.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardStatusChange(
                        StatusEffect.MAID,
                        StatusChangeType.ADD,
                        active,
                        ActionTypes.PASSIVE,
                        owner,
                        None,
                    )
                )
        elif moved_from_bench:
            active = owner.player.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardStatusChange(
                        StatusEffect.MAID,
                        StatusChangeType.ERASE,
                        active,
                        ActionTypes.PASSIVE,
                        owner,
                        None,
                    )
                )
        else:
            if (
                event.pile_from.pile_type == Pile.ACTIVE
                and event.pile_from.player == owner.player
                and isinstance(event.card, AVGECharacterCard)
            ):
                packet.append(
                    AVGECardStatusChange(
                        StatusEffect.MAID,
                        StatusChangeType.ERASE,
                        event.card,
                        ActionTypes.PASSIVE,
                        owner,
                        None,
                    )
                )
            if (
                event.pile_to.pile_type == Pile.ACTIVE
                and event.pile_to.player == owner.player
                and isinstance(event.card, AVGECharacterCard)
            ):
                packet.append(
                    AVGECardStatusChange(
                        StatusEffect.MAID,
                        StatusChangeType.ADD,
                        event.card,
                        ActionTypes.PASSIVE,
                        owner,
                        None,
                    )
                )

        if len(packet) > 0:
            owner.propose(AVGEPacket(packet, AVGEEngineID(owner, ActionTypes.PASSIVE, FionaLi)))

        return Response(ResponseType.ACCEPT, Notify('Getting Dressed: Active card gets the maid status', all_players, default_timeout))


class FionaLi(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.STRING, 1, 1)
        self.atk_1_name = 'Vibrato'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(_BenchMaidReactor(self))

        if self.cardholder is not None and self.cardholder.pile_type == Pile.BENCH:
            active = self.player.get_active_card()
            if isinstance(active, AVGECharacterCard):
                def apply_initial_maid() -> PacketType:
                    packet: PacketType = []
                    packet.append(
                        AVGECardStatusChange(
                            StatusEffect.MAID,
                            StatusChangeType.ADD,
                            active,
                            ActionTypes.PASSIVE,
                            self,
                            None,
                        )
                    )
                    return packet

                self.propose(AVGEPacket([apply_initial_maid], AVGEEngineID(self, ActionTypes.PASSIVE, FionaLi)))
                return Response(ResponseType.CORE, Notify('Getting Dressed: Active card gets the maid status', all_players, default_timeout))

        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:

        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            packet: PacketType = []
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        40,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, FionaLi)))

        return self.generic_response(card, ActionTypes.ATK_1)
