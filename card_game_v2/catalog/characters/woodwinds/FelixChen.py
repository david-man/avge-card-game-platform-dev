from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import CoinflipData, BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class FelixChen(AVGECharacterCard):
    '''v1's passive `event_match` checks `catalyst_action not in [ATK_1, ATK_1]` - an
    obvious copy-paste typo for `[ATK_1, ATK_2]` (there is no plausible reading where
    excluding ATK_2 specifically was intended), so it silently never reduced ATK_2
    damage in v1. Fixed here rather than faithfully reproduced, per "fix bugs on
    sight" - this migration reduces both ATK_1 and ATK_2 damage. Note: SYSTEM_ARCHITECTURE.md's
    illustration of this card is stale/wrong (uses an older API shape and gets the
    atk_1 TT-effect target wrong) - the real v1 `.py` file is the only source of truth
    here.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._synesthesia: FelixChen._SynesthesiaModifier | None = None

    def base_hp(self) -> int:
        return 90

    def base_max_hp(self) -> int:
        return 90

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Multiphonics()}), **({ActionTypes.PASSIVE: self._SynesthesiaPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        if (deck_from.deck_type in (DeckType.ACTIVE_CARD, DeckType.BENCH)
                and deck_to.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH)
                and self._synesthesia is not None):
            self._synesthesia.cleanup()
            self._synesthesia = None

    class _SynesthesiaPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Synesthesia",
                description="While your characters in play all have different types, each takes 10 less damage from attacks.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, FelixChen)
            if card._synesthesia is None:
                card._synesthesia = FelixChen._SynesthesiaModifier(card, card.env)
                card.add_listener(card._synesthesia)

    class _SynesthesiaModifier(AVGEEventModifier):
        def __init__(self, owner_card: FelixChen, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, FelixChen), env, EngineGroup.EXTERNAL_MODIFIERS_2)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if self.owner_card.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                return False
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.modifier_type) or callable(event.change_type) or callable(event.target_card):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.id.calling_action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return False
            attacker = event.id.calling_card
            if not isinstance(attacker, AVGECharacterCard):
                return False
            if event.target_card.owner != self.owner_card.owner:
                return False

            player = self.env.players[self.owner_card.owner]
            own_chars = [
                c for c in player.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            types = [c.card_type for c in own_chars]
            return len(types) == len(set(types))

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            event.modify_magnitude(-10)
            await self.env.broadcast(BroadcastIO(
                "Synesthesia: Attack damage reduced by 10.", default_timeout,
            ))

    class _Multiphonics(Attack):
        def __init__(self):
            super().__init__(
                name="Multiphonics",
                description="Flip 2 coins. Both heads: 50 damage to all opposing bench. Both tails: 100 damage to the opposing active. Split: nothing.",
                action_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            _id = AVGEEngineID(card, self.action_type, FelixChen)

            heads = 0
            for _ in range(2):
                heads += await env.report(CoinflipData(card.owner, "Multiphonics: Flip 2 coins."), _id)

            events: list[Event | Generator] = []
            if heads == 2:
                bench_targets = [c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)]
                for target in bench_targets:
                    events.append(AVGECardHPChangeEvent(
                        _id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
                    ))
            elif heads == 0:
                target = env.get_player_active(opponent)
                events.append(AVGECardHPChangeEvent(
                    _id, target, 100, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
                ))

            if events:
                env.push_packet(Packet(_id, events))
