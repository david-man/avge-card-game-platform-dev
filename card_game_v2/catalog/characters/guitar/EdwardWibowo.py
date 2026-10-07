from __future__ import annotations

from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventModifier
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer, TransferCard
from ....core.AVGEIOManager import CoinflipData, BroadcastIO, Notification

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment


class EdwardWibowo(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 110

    def base_max_hp(self) -> int:
        return 110

    def base_card_type(self) -> CardType:
        return CardType.GUITAR

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._PacketLoss(), ActionTypes.ATK_2: self._Distortion()}), **({})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _PacketLoss(Attack):
        def __init__(self):
            super().__init__(
                name="Packet Loss",
                description="Flip a coin for each energy on the opposing active. Remove that many energy from it (one per head).",
                action_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            opp_active = env.get_player_active(opponent)
            n = len(opp_active.energy_tokens)
            _id = AVGEEngineID(card, self.action_type, EdwardWibowo)
            if n <= 0:
                await env.report(Notification(
                    card.owner, "Packet Loss, but there was no energy to remove...", default_timeout,
                ), _id)
                return

            heads = 0
            for _ in range(n):
                heads += await env.report(CoinflipData(card.owner, "Packet Loss: Flip a coin!"), _id)

            if heads <= 0:
                await env.report(Notification(
                    card.owner, "Packet Loss and got 0 heads...", default_timeout,
                ), _id)
                return

            removable = min(heads, len(opp_active.energy_tokens))
            events: list[Event | Generator] = [
                AVGEEnergyTransfer(_id, opp_active, env, env) for _ in range(removable)
            ]
            env.push_packet(Packet(_id, events))

    class _Distortion(Attack):
        def __init__(self):
            super().__init__(
                name="Distortion",
                description="Deal 40 damage to the opposing active. Your next GUITAR attack on your own following turn deals +40 damage.",
                action_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, EdwardWibowo)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, 40, AVGEAttributeModifier.SUBSTRACTIVE, CardType.GUITAR, env,
            )]))
            card.add_listener(EdwardWibowo._GuitarBoost(card.owner, env))

    class _GuitarBoost(AVGEEventModifier):
        '''+40 damage on the owner's own GUITAR attacks during the owner's own next
        turn. Same idiom as RobertoGonzales's Distortion buff (independently
        implemented, per policy) - no fire-once self-invalidation, matching v1's
        `_EdwardGuitarBoost` (no `on_packet_completion` override).'''

        def __init__(self, owner: User, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, EdwardWibowo), env, EngineGroup.EXTERNAL_MODIFIERS_2)
            self.owner = owner
            self.round_active = env.round + 2

        def match(self, event: Event) -> bool:
            if self.env.round > self.round_active:
                self.cleanup()
                return False
            if self.env.round != self.round_active:
                return False
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.modifier_type) or callable(event.change_type) or callable(event.target_card):
                return False
            if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                return False
            if event.change_type != CardType.GUITAR:
                return False
            return (event.id.calling_card is not None and event.id.calling_card.owner == self.owner
                    and event.target_card.owner != self.owner)

        async def modify(self, event: Event) -> None:
            assert isinstance(event, AVGECardHPChangeEvent)
            event.modify_magnitude(40)
            await self.env.broadcast(BroadcastIO("Distortion: +40 damage!", default_timeout))
