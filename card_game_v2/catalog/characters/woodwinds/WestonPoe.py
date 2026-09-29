from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class WestonPoe(AVGECharacterCard):
    '''"Right Back At You!" reflects the *actual* post-modifier HP lost (recomputed
    from `original_hp`/`final_change`), not the event's raw pre-modifier `magnitude` -
    the important detail SYSTEM_ARCHITECTURE.md's stale illustration of this card
    gets wrong (see that doc's known-stale note in Section 5). v1 also runs a cheaper
    `magnitude >= 60` pre-filter before its own precise re-check; v2 skips the
    redundant pre-filter and just computes the real value once, since both the
    engine's own post-act-reactor-timing and history preserve `original_hp`/
    `final_change` by the time this reactor runs.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._right_back: WestonPoe._RightBackAtYouReactor | None = None

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._Overblow()}), **({ActionTypes.PASSIVE: self._RightBackAtYouPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _RightBackAtYouPassive(Ability):
        def __init__(self):
            super().__init__(
                name="Right Back At You!",
                description="Reflect any single attack hit of 60+ actual damage back onto the attacker.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, WestonPoe)
            if card._right_back is None:
                card._right_back = WestonPoe._RightBackAtYouReactor(card, card.env)
                card.add_listener(card._right_back)

    class _RightBackAtYouReactor(AVGEEventReactor):
        def __init__(self, owner_card: WestonPoe, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, WestonPoe), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            # No live deck_type/cleanup gate here (unlike most other permanent
            # listeners in this migration): by the time this EXTERNAL_REACTORS
            # listener sees a *lethal* hit, the engine's own INTERNAL_4 discard flow
            # has already moved the owner out of play - gating on "still in play"
            # would wrongly block reflection on the exact hit that KO'd them, which
            # defeats the whole point of a last-stand reflection effect.
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.target_card) or callable(event.modifier_type):
                return False
            if event.target_card is not self.owner_card:
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.id.calling_action not in (ActionTypes.ATK_1, ActionTypes.ATK_2):
                return False
            attacker = event.id.calling_card
            if not isinstance(attacker, AVGECharacterCard):
                return False
            if attacker.owner != self.env.get_opponent(self.owner_card.owner).id:
                return False
            if event.original_hp is None or event.final_change is None:
                return False
            hp_lost = max(0, event.original_hp - event.final_change)
            return hp_lost >= 60

        async def react(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            assert event.original_hp is not None and event.final_change is not None
            attacker = event.id.calling_card
            assert isinstance(attacker, AVGECharacterCard)

            hp_lost = max(0, event.original_hp - event.final_change)
            _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, WestonPoe)
            await self.env.broadcast(BroadcastIO(
                "Weston Poe: Right Back At You! Reflected damage equal to HP lost.", default_timeout,
            ))
            event.push_event([AVGECardHPChangeEvent(
                _id, attacker, hp_lost, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, self.env,
            )])

    class _Overblow(Attack):
        def __init__(self):
            super().__init__(
                name="Overblow",
                description="Deal 50 damage to the opposing active. Deal 10 recoil damage to yourself.",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, WestonPoe)

            env.push_packet(Packet(_id, [
                AVGECardHPChangeEvent(_id, target, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env),
                AVGECardHPChangeEvent(_id, card, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env),
            ]))
