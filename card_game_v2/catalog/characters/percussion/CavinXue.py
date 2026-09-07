from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, StatusEffect, User, default_timeout
from ....engine.event import Event, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment


class CavinXue(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._maid_boost: CavinXue._MaidBoost | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.PERCUSSION

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._CymbalCrash()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.PASSIVE: self._WaitNoImNotIntoFemboys()}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _WaitNoImNotIntoFemboys(Ability):
        def __init__(self):
            super().__init__(
                name='"Wait no... I\'m not into femboys-"',
                description="This character's own attacks deal +20 damage per other character carrying MAID, anywhere in play.",
                ability_type=ActionTypes.PASSIVE,
            )

        def can_play(self, card: AVGECharacterCard) -> bool:
            return True

        async def __call__(self, card: AVGECharacterCard) -> None:
            assert isinstance(card, CavinXue)
            if card._maid_boost is None:
                card._maid_boost = CavinXue._MaidBoost(card, card.env)
                card.add_listener(card._maid_boost)

    class _MaidBoost(AVGEEventModifier):
        def __init__(self, owner_card: CavinXue, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.NONCHAR, CavinXue), env, EngineGroup.EXTERNAL_MODIFIERS_2)
            self.owner_card = owner_card

        def _other_maid_count(self) -> int:
            count = 0
            for player in self.env.players.values():
                for pile in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                    for c in player.card_piles[pile]:
                        if isinstance(c, AVGECharacterCard) and c is not self.owner_card and len(c.statuses_attached[StatusEffect.MAID]) > 0:
                            count += 1
            return count

        def match(self, event: Event) -> bool:
            if self.owner_card.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                return False
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.modifier_type):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.id.calling_card is not self.owner_card:
                return False
            return self._other_maid_count() > 0

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            boost = 20 * self._other_maid_count()
            event.modify_magnitude(boost)
            await self.env.broadcast(BroadcastIO(
                f"Cavin Xue gained +{boost} damage from \"Wait no... I'm not into femboys-\".", default_timeout,
            ))

    class _CymbalCrash(Attack):
        def __init__(self):
            super().__init__(name="Cymbal Crash", description="Deal 20 damage to the opposing active.", atk_type=ActionTypes.ATK_1, cost=1)

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), CavinXue)
            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, env,
            )]))
