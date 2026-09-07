from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, StatusEffect, AVGEStatusModifier, User, default_timeout
from ....engine.event import Event, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGECardStatusChange, TransferCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID


class FionaLi(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._maid_reactor: FionaLi._BenchMaidReactor | None = None

    def base_hp(self) -> int:
        return 90

    def base_max_hp(self) -> int:
        return 90

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 1

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._Vibrato()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.PASSIVE: self._GettingDressedPassive()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _GettingDressedPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Getting Dressed",
                description="While benched, whichever character is your active always carries MAID.",
                ability_type=ActionTypes.PASSIVE,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            return True

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, FionaLi)
            if card._maid_reactor is None:
                card._maid_reactor = FionaLi._BenchMaidReactor(card, card.env)
                card.add_listener(card._maid_reactor)

            if card.deck_type != DeckType.BENCH:
                return
            env = card.env
            active = env.get_player_active(card.owner)
            _id = AVGEEngineID(card, ActionTypes.PASSIVE, FionaLi)
            await env.broadcast(BroadcastIO("Getting Dressed: Active card gets the MAID status.", default_timeout))
            env.push_packet(Packet(_id, [AVGECardStatusChange(
                _id, active, card, StatusEffect.MAID, AVGEStatusModifier.ADD, env,
            )]))

    class _BenchMaidReactor(AVGEEventReactor):
        def __init__(self, owner_card: FionaLi, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, FionaLi), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def _own_bench_move(self, event: TransferCard) -> tuple[bool, bool]:
            assert not callable(event.card) and not callable(event.deck_from) and not callable(event.deck_to)
            owner = self.owner_card
            if event.card is not owner:
                return False, False
            moved_to_bench = (
                event.deck_to.deck_type == DeckType.BENCH and event.deck_to.deck_owner.id == owner.owner
            )
            moved_from_bench = (
                event.deck_from.deck_type == DeckType.BENCH and event.deck_from.deck_owner.id == owner.owner
            )
            return moved_to_bench, moved_from_bench

        def match(self, event: Event) -> bool:
            if not isinstance(event, TransferCard):
                return False
            if callable(event.card) or callable(event.deck_from) or callable(event.deck_to):
                return False
            if not isinstance(event.card, AVGECharacterCard):
                return False

            owner = self.owner_card
            moved_to_bench, moved_from_bench = self._own_bench_move(event)
            if moved_to_bench or moved_from_bench:
                return True

            if owner.deck_type != DeckType.BENCH:
                return False
            if event.card is owner:
                return False

            moved_to_active = event.deck_to.deck_type == DeckType.ACTIVE_CARD and event.deck_to.deck_owner.id == owner.owner
            moved_from_active = event.deck_from.deck_type == DeckType.ACTIVE_CARD and event.deck_from.deck_owner.id == owner.owner
            return moved_to_active or moved_from_active

        async def react(self, event: Event) -> None:
            assert isinstance(event, TransferCard)
            assert not callable(event.card) and not callable(event.deck_from) and not callable(event.deck_to)
            owner = self.owner_card
            env = self.env
            _id = AVGEEngineID(owner, ActionTypes.PASSIVE, FionaLi)

            moved_to_bench, moved_from_bench = self._own_bench_move(event)
            if moved_to_bench:
                active = env.get_player_active(owner.owner)
                await env.broadcast(BroadcastIO("Getting Dressed: Active card gets the MAID status.", default_timeout))
                event.push_event([AVGECardStatusChange(
                    _id, active, owner, StatusEffect.MAID, AVGEStatusModifier.ADD, env,
                )])
                return
            if moved_from_bench:
                active = env.get_player_active(owner.owner)
                event.push_event([AVGECardStatusChange(
                    _id, active, owner, StatusEffect.MAID, AVGEStatusModifier.REMOVE, env,
                )])
                return

            assert isinstance(event.card, AVGECharacterCard)
            if event.deck_to.deck_type == DeckType.ACTIVE_CARD and event.deck_to.deck_owner.id == owner.owner:
                await env.broadcast(BroadcastIO("Getting Dressed: Active card gets the MAID status.", default_timeout))
                event.push_event([AVGECardStatusChange(
                    _id, event.card, owner, StatusEffect.MAID, AVGEStatusModifier.ADD, env,
                )])
            elif event.deck_from.deck_type == DeckType.ACTIVE_CARD and event.deck_from.deck_owner.id == owner.owner:
                event.push_event([AVGECardStatusChange(
                    _id, event.card, owner, StatusEffect.MAID, AVGEStatusModifier.REMOVE, env,
                )])

    class _Vibrato(Attack):
        def __init__(self):
            super().__init__(name="Vibrato", description="Deal 40 damage to the opposing active.", atk_type=ActionTypes.ATK_1, cost=2)

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), FionaLi)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 40, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
            )]))
