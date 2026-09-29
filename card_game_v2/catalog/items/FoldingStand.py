from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, CardType, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck
from ...avge_abstracts.AVGEEventListener import AVGEEventModifier
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, EngineGroup, AVGEAttributeModifier, StatusEffect, User, default_timeout
from ...core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ...core.AVGEIOManager import BroadcastIO
from ...engine.event import Event

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment


class FoldingStand(AVGEItemCard):
    '''Adds +10 (or +20 if the attacker has GOON) to the owner's own next attack
    against the opponent this turn, then self-invalidates - either by firing once, or
    by the turn passing without a qualifying attack. No cost.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="FoldingStand",
                description=FoldingStand.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, FoldingStand):
                raise TypeError("FoldingStand action requires its defining card")
            acting_card.add_listener(FoldingStand._FirstAttackDamageBuff(acting_card.owner, acting_card.env))


    class _FirstAttackDamageBuff(AVGEEventModifier):
        def __init__(self, owner: User, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, FoldingStand), env, EngineGroup.EXTERNAL_MODIFIERS_2)
            self.owner = owner
            self.round_played = env.round

        def match(self, event: Event) -> bool:
            if self.env.round > self.round_played:
                self.cleanup()
                return False
            if self.env.round != self.round_played:
                return False
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.modifier_type) or callable(event.change_type) or callable(event.target_card):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.change_type == CardType.ALL:
                return False
            if event.id.calling_action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return False
            if event.id.calling_card is not self.env.get_player_active(self.owner):
                return False
            return event.target_card.owner == self.env.get_opponent(self.owner).id

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            attacker = self.env.get_player_active(self.owner)
            if len(attacker.statuses_attached[StatusEffect.GOON]) > 0:
                event.modify_magnitude(20)
                message = "FoldingStand: +10 (+10[GOON]) damage on your first attack this turn."
            else:
                event.modify_magnitude(10)
                message = "FoldingStand: +10 damage on your first attack this turn."
            self.cleanup()
            await self.env.broadcast(BroadcastIO(message, default_timeout))
