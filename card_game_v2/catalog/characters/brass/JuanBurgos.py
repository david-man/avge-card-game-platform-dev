from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEDeck import AVGEDeck
    from ....constants import User


class JuanBurgos(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._bench_boost: JuanBurgos._BenchAttackBoost | None = None

    def base_hp(self) -> int:
        return 90

    def base_max_hp(self) -> int:
        return 90

    def base_card_type(self) -> CardType:
        return CardType.BRASS

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._ConcertPitch()}), **({ActionTypes.PASSIVE: self._BakingBuff()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        # Entering play is handled globally by TransferCard's own passive-trigger special case.
        entering_play = deck_to.deck_type in (DeckType.ACTIVE_CARD, DeckType.BENCH)
        was_in_play = deck_from.deck_type in (DeckType.ACTIVE_CARD, DeckType.BENCH)
        if was_in_play and not entering_play and self._bench_boost is not None:
            self._bench_boost.cleanup()
            self._bench_boost = None

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

    class _BenchAttackBoost(AVGEEventModifier):
        '''While Juan Burgos is benched, friendly Brass characters' attacks deal 10 more damage.'''

        def __init__(self, owner_card: JuanBurgos):
            super().__init__(
                AVGEEngineID(owner_card, ActionTypes.PASSIVE, JuanBurgos),
                owner_card.env,
                EngineGroup.EXTERNAL_MODIFIERS_2,
            )
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if not isinstance(event.id.calling_card, AVGECharacterCard):
                return False
            if event.id.calling_card.owner != self.owner_card.owner:
                return False
            if self.owner_card.deck_type != DeckType.BENCH:
                return False
            if event.id.calling_card.card_type != CardType.BRASS:
                return False
            return True

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            event.modify_magnitude(10)
            await self.env.broadcast(BroadcastIO(
                "Baking Buff! +10 damage",
                default_timeout,
            ))

    # ------------------------------------------------------------------
    # Abilities
    # ------------------------------------------------------------------

    class _BakingBuff(Ability):
        def __init__(self):
            super().__init__(
                name="Baking Buff",
                description="While Juan Burgos is on your bench, your Brass characters' attacks deal 10 more damage.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, JuanBurgos)
            if card._bench_boost is None:
                card._bench_boost = JuanBurgos._BenchAttackBoost(card)
                card.add_listener(card._bench_boost)

    # ------------------------------------------------------------------
    # Attacks
    # ------------------------------------------------------------------

    class _ConcertPitch(Attack):
        def __init__(self):
            super().__init__(
                name="Concert Pitch",
                description="Deal 30 damage, plus 20 more for each Brass character on your bench.",
                action_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)

            player = env.players[card.owner]
            brass_count = sum(
                1 for c in player.card_piles[DeckType.BENCH]
                if isinstance(c, AVGECharacterCard) and c.card_type == CardType.BRASS
            )
            damage = 30 + 20 * brass_count

            _id = AVGEEngineID(card, self.action_type, JuanBurgos)
            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(
                    _id,
                    target,
                    damage,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    env,
                )
            ]

            env.push_packet(Packet(_id, events))
