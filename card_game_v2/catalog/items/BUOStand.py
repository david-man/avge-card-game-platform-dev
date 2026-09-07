from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard
from ...avge_abstracts.AVGEDeck import AVGEDeck
from ...avge_abstracts.AVGEEventListener import AVGEEventModifier
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, EngineGroup, AVGEAttributeModifier, StatusEffect, User, default_timeout
from ...core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard
from ...core.AVGEIOManager import BroadcastIO
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

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        active = env.get_player_active(self.owner)
        if len(active.energy_tokens) == 0:
            await env.broadcast(BroadcastIO("BUOStand: No energy on active character :(", default_timeout))
            return

        self.add_listener(BUOStand._FirstAttackDamageBuff(self.owner, env))

        _id = AVGEEngineID(self, ActionTypes.NONCHAR, BUOStand)
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
