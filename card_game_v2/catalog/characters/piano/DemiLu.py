from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, PlayCharacterCard, TransferCard
from ....core.AVGEIOManager import BroadcastIO
from ....catalog.stadiums.SteinertBasement import SteinertBasement
from ....catalog.stadiums.SteinertPracticeRoom import SteinertPracticeRoom

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class DemiLu(AVGECharacterCard):
    '''"Steinert Warrior": while benched under either Steinert stadium, immune to
    opponent attack damage, and exempt from that stadium's own +1 attack-energy-cost
    surcharge (relevant only for a forced/borrowed attack while benched - a normal
    player-chosen attack always comes from the active slot). v2's `AVGEConstrainer`
    can't see per-event "which event is this attached to" context the way v1's could
    (confirmed via LukeXu's `_NullifyConstraint` precedent, flagged in
    SteinertBasement/SteinertPracticeRoom's `_AttackExtraCostModifier` docstrings), so
    rather than trying to disable those modifiers via a constrainer, this card just
    runs its own compensating modifier afterward (`EXTERNAL_MODIFIERS_3`, strictly
    later than the Steinert modifiers' `EXTERNAL_MODIFIERS_1`) that adds the energy
    back for itself specifically - same net effect, no shared helper with the
    stadiums' own listener classes.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._damage_block: DemiLu._DamageBlockModifier | None = None
        self._cost_exemption: DemiLu._CostExemptionModifier | None = None

    def base_hp(self) -> int:
        return 90

    def base_max_hp(self) -> int:
        return 90

    def base_card_type(self) -> CardType:
        return CardType.PIANO

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._FourHands()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.PASSIVE: self._SteinertWarriorPassive()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        entering_play = deck_to.deck_type in (DeckType.ACTIVE_CARD, DeckType.BENCH)
        was_in_play = deck_from.deck_type in (DeckType.ACTIVE_CARD, DeckType.BENCH)
        if was_in_play and not entering_play:
            if self._damage_block is not None:
                self._damage_block.cleanup()
                self._damage_block = None
            if self._cost_exemption is not None:
                self._cost_exemption.cleanup()
                self._cost_exemption = None

    @staticmethod
    def _steinert_stadium(env: AVGEEnvironment) -> SteinertBasement | SteinertPracticeRoom | None:
        if len(env.stadium_cardholder) == 0:
            return None
        stadium = env.stadium_cardholder.cards_holding[0]
        if isinstance(stadium, (SteinertBasement, SteinertPracticeRoom)):
            return stadium
        return None

    class _SteinertWarriorPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Steinert Warrior",
                description="While benched under a Steinert stadium, immune to opponent attack damage and exempt from that stadium's attack-cost surcharge.",
                ability_type=ActionTypes.PASSIVE,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            return True

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, DemiLu)
            if card._damage_block is None:
                card._damage_block = DemiLu._DamageBlockModifier(card, card.env)
                card.add_listener(card._damage_block)
            if card._cost_exemption is None:
                card._cost_exemption = DemiLu._CostExemptionModifier(card, card.env)
                card.add_listener(card._cost_exemption)

    class _DamageBlockModifier(AVGEEventModifier):
        def __init__(self, owner_card: DemiLu, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, DemiLu), env, EngineGroup.EXTERNAL_PRECHECK_1)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if self.owner_card.deck_type != DeckType.BENCH:
                return False
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.target_card) or callable(event.modifier_type) or callable(event.magnitude):
                return False
            if event.target_card is not self.owner_card:
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            assert isinstance(event.id, AVGEEngineID)
            if event.id.calling_action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return False
            attacker = event.id.calling_card
            if not isinstance(attacker, AVGECharacterCard):
                return False
            if attacker.owner == self.owner_card.owner:
                return False
            return DemiLu._steinert_stadium(self.env) is not None

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            assert not callable(event.magnitude)
            event.modify_magnitude(-event.magnitude)
            await self.env.broadcast(BroadcastIO(
                "Steinert Warrior: Demi Lu is immune to this attack.", default_timeout,
            ))

    class _CostExemptionModifier(AVGEEventModifier):
        '''Deliberately shares `EXTERNAL_MODIFIERS_1` with the Steinert stadiums' own
        `+1` cost surcharge modifiers (rather than a later group): the engine only
        guarantees a fixed cross-group order, and same-group ordering among multiple
        matching modifiers is resolved via `ListenerReorderIO` (arbitrary from this
        card's perspective) - but since this is a plain `+1`/`-1` pair, the net result
        is identical either way, and it must land before `INTERNAL_1`'s affordability
        check (which reads the already-modified `event.cost`), ruling out any later
        group.'''

        def __init__(self, owner_card: DemiLu, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, DemiLu), env, EngineGroup.EXTERNAL_MODIFIERS_1)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if self.owner_card.deck_type != DeckType.BENCH:
                return False
            if not isinstance(event, PlayCharacterCard):
                return False
            if callable(event.target_card) or callable(event.action) or callable(event.cost):
                return False
            if event.target_card is not self.owner_card:
                return False
            if event.action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return False
            stadium = DemiLu._steinert_stadium(self.env)
            if isinstance(stadium, SteinertPracticeRoom):
                return True
            if isinstance(stadium, SteinertBasement):
                assert isinstance(event.id, AVGEEngineID)
                return event.id.calling_action == ActionTypes.PLAYER_CHOICE
            return False

        async def modify(self, event: Event) -> None:
            assert isinstance(event, PlayCharacterCard)
            assert not callable(event.cost)
            event.cost = max(0, event.cost - 1)
            await self.env.broadcast(BroadcastIO(
                "Steinert Warrior: Demi Lu is not affected by 15 Minute Walk.", default_timeout,
            ))

    class _FourHands(Attack):
        def __init__(self):
            super().__init__(
                name="Four Hands",
                description="Deal 50 damage to the opposing active (80 instead if you have another PIANO character benched).",
                atk_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), DemiLu)

            def gen() -> list[Event | Generator]:
                bench_mates = [
                    c for c in env.players[card.owner].card_piles[DeckType.BENCH]
                    if isinstance(c, AVGECharacterCard) and c is not card
                ]
                found_piano = any(c.card_type == CardType.PIANO for c in bench_mates)
                dmg = 80 if found_piano else 50
                target = env.get_player_active(opponent)
                return [AVGECardHPChangeEvent(
                    _id, target, dmg, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PIANO, env,
                )]

            env.push_packet(Packet(_id, [gen]))
