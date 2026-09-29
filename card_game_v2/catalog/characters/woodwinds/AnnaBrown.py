from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventRegulator
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, ResponseStatus, default_timeout
from ....engine.event import Event, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import D6Input, BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class AnnaBrown(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._shield: AnnaBrown._DoNotDisturbShield | None = None

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._HyperVentilation()}), **({ActionTypes.PASSIVE: self._DoNotDisturbPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _DoNotDisturbPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Do Not Disturb",
                description="While benched, ignores all damage from opponent attacks.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, AnnaBrown)
            if card._shield is None:
                card._shield = AnnaBrown._DoNotDisturbShield(card, card.env)
                card.add_listener(card._shield)

    class _DoNotDisturbShield(AVGEEventRegulator):
        '''A regulator (not a modifier) so it can REGULATE_IGNORE the whole event outright -
        matching the same fix shape as AVGEMaidDamageShieldRegulator (catalog/status_effects/
        Maid.py). The old modifier only zeroed the magnitude, so a later additive modifier
        (e.g. a +10 buff) in a subsequent group could still revive the damage. Registered at
        EXTERNAL_MODIFIERS_1 - the earliest group, before INTERNAL_1's weakness/crit
        calculation - since this immunity is unconditional (blocks regardless of magnitude), so
        there's no reason to prompt the attacker's crit coinflip for a hit that's blocked either
        way.'''
        def __init__(self, owner_card: AnnaBrown, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, AnnaBrown), env, EngineGroup.EXTERNAL_MODIFIERS_1)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.change_type) or callable(event.modifier_type) or callable(event.target_card):
                return False
            if event.change_type == CardType.ALL:
                return False
            if event.target_card is not self.owner_card:
                return False
            if self.owner_card.deck_type != DeckType.BENCH:
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.id.calling_action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return False
            attacker = event.id.calling_card
            if not isinstance(attacker, AVGECharacterCard):
                return False
            return attacker.owner == self.env.get_opponent(self.owner_card.owner).id

        async def respond(self, event: Event) -> ResponseStatus:
            await self.env.broadcast(BroadcastIO(
                "Do Not Disturb: Benched Anna Brown ignores damage from opponent attacks.", default_timeout,
            ))
            return ResponseStatus.REGULATE_IGNORE

    class _HyperVentilation(Attack):
        def __init__(self):
            super().__init__(
                name="Hyper-Ventilation!",
                description="Roll a D6. Deal 30 + 10 per pip damage to the opposing active.",
                action_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, AnnaBrown)

            roll = await env.report(D6Input(card.owner, "Hyper-Ventilation!: Roll a D6."), _id)
            damage = 30 + (10 * roll)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, damage, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
            )]))
