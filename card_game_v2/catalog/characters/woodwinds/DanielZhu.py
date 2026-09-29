from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import D6Input, IntInput, BroadcastIO, Notification

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class DanielZhu(AVGECharacterCard):
    '''v1's atk_1 is internally mistagged as `ActionTypes.ATK_2` throughout (its id, its
    interrupt key, its damage event) despite `atk_2` not existing at all - this looks
    like a copy-paste leftover with no coherent purpose, not an intentional design, so
    it's fixed here rather than faithfully reproduced: this migration tags it ATK_1
    like every other single-attack card.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._share_pain: DanielZhu._SharePainModifier | None = None

    def base_hp(self) -> int:
        return 120

    def base_max_hp(self) -> int:
        return 120

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._HyperVentilation()}), **({ActionTypes.PASSIVE: self._SharePainPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _SharePainPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Share the Pain",
                description="When a teammate takes damage, redirect up to 30 (capped by your own remaining HP) onto Daniel instead.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, DanielZhu)
            if card._share_pain is None:
                card._share_pain = DanielZhu._SharePainModifier(card, card.env)
                card.add_listener(card._share_pain)

    class _SharePainModifier(AVGEEventModifier):
        def __init__(self, owner_card: DanielZhu, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, DanielZhu), env, EngineGroup.EXTERNAL_MODIFIERS_2)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.modifier_type) or callable(event.change_type) or callable(event.target_card):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.change_type == CardType.ALL:
                return False
            if event.target_card is self.owner_card:
                return False
            if event.target_card.owner != self.owner_card.owner:
                return False
            if self.owner_card.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                return False
            return self.owner_card.hp > 1

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            assert not callable(event.magnitude)
            owner = self.owner_card
            env = self.env

            incoming_damage = event.magnitude
            max_redirect = min(30, incoming_damage, owner.hp - 1)
            if max_redirect <= 0:
                return

            redirect_damage = await env.report(IntInput(
                owner.owner,
                f"Share the Pain: Redirect 0-{max_redirect} damage to Daniel",
                0,
                max_redirect,
            ), event.id)
            redirect_damage = max(0, min(max_redirect, redirect_damage))
            if redirect_damage <= 0:
                await env.report(Notification(
                    owner.owner, "Share the Pain: Redirected 0 damage to Daniel Zhu.", default_timeout,
                ), event.id)
                return

            event.modify_magnitude(-redirect_damage)
            await env.broadcast(BroadcastIO(
                f"Share the Pain: Redirected {redirect_damage} damage to Daniel Zhu.", default_timeout,
            ))
            event.push_event([AVGECardHPChangeEvent(
                event.id, owner, redirect_damage, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
            )])

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
            _id = AVGEEngineID(card, self.action_type, DanielZhu)

            roll = await env.report(D6Input(card.owner, "Hyper-Ventilation!: Roll a D6."), _id)
            damage = 30 + (10 * roll)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, damage, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
            )]))
