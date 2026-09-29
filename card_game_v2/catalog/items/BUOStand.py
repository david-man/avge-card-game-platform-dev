from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck
from ...avge_abstracts.AVGEEventListener import AVGEEventModifier
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, EngineGroup, AVGEAttributeModifier, StatusEffect, User, default_timeout
from ...core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard
from ...core.AVGEIOManager import BroadcastIO, Notification
from ...engine.event import Event, Generator, Packet

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment


class BUOStand(AVGEItemCard):
    '''Discard 1 energy from your own active character; in exchange, add +20 (or +30 if
    the attacker has GOON) to your own next attack against the opponent this turn, then
    self-invalidates - either by firing once, or by the turn passing without a
    qualifying attack. Cannot be played if the active has no energy to discard.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="BUOStand",
                description=BUOStand.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
            active = acting_card.env.get_player_active(acting_card.owner)
            return len(active.energy_tokens) > 0

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, BUOStand):
                raise TypeError("BUOStand action requires its defining card")
            env = acting_card.env
            active = env.get_player_active(acting_card.owner)
            _id = AVGEEngineID(acting_card, self.action_type, BUOStand)
            if len(active.energy_tokens) == 0:
                await env.report(Notification(
                    acting_card.owner, "BUOStand: No energy on active character :(", default_timeout,
                ), _id)
                return

            acting_card.add_listener(BUOStand._FirstAttackDamageBuff(acting_card.owner, env))
            events: list[Event | Generator] = [AVGEEnergyTransfer(_id, active, env, env)]
            env.push_packet(Packet(_id, events))


    class _FirstAttackDamageBuff(AVGEEventModifier):
        def __init__(self, owner: User, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, BUOStand), env, EngineGroup.EXTERNAL_MODIFIERS_2)
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
            if callable(event.modifier_type) or callable(event.target_card):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
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
                event.modify_magnitude(30)
                message = "BUO Stand: +20 (+10[GOON]) damage on your first attack this turn."
            else:
                event.modify_magnitude(20)
                message = "BUO Stand: +20 damage on your first attack this turn."
            self.cleanup()
            await self.env.broadcast(BroadcastIO(message, default_timeout))
